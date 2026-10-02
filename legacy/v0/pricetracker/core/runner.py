import logging
import asyncio
from datetime import datetime
from typing import Optional
from playwright.async_api import Page
from sqlalchemy.orm import Session
from pricetracker.core.config import AppConfig
from pricetracker.core.browser import BrowserManager
from pricetracker.core.llm import LLMClient
from pricetracker.agent.agent import LLMAgent
from pricetracker.db.session import get_session_factory
from pricetracker.db.models import Run, Observation, Site, Product, ProductSiteQuery
from pricetracker.core.interfaces import ObservationDraft

logger = logging.getLogger(__name__)

class JobRunner:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = AppConfig.load(config_path)
        self.session_factory = get_session_factory(self.config.database.url)
        self.llm_client = LLMClient(self.config.agent)

    async def run(self, site_name: Optional[str] = None, product_name: Optional[str] = None):
        logger.info("Starting job run")
        async with BrowserManager(headless=False) as browser_manager:
            page = await browser_manager.get_page()
            # agent = LLMAgent(self.llm_client) # Defer creation until site loop or pass None initially

            with self.session_factory() as session:
                # Create Run record
                run_record = Run(status="running")
                session.add(run_record)
                session.commit()
                
                try:
                    await self._process_sites(session, run_record, page, site_name, product_name)
                    run_record.status = "success"
                    run_record.finished_at = datetime.now()
                except Exception as e:
                    logger.error(f"Job run failed: {e}", exc_info=True)
                    run_record.status = "failed"
                    run_record.notes = str(e)
                    run_record.finished_at = datetime.now()
                finally:
                    session.commit()

    async def _process_sites(self, session: Session, run_record: Run, page: Page, filter_site: str, filter_product: str):
        # Allow sites to be created/updated from config on the fly for v1
        # In a real app, this should be a sync step.
        
        for site_config in self.config.sites:
            if not site_config.enabled:
                continue
            if filter_site and site_config.name != filter_site:
                continue

            # Get or create site in DB
            site = session.query(Site).filter(Site.name == site_config.name).first()
            if not site:
                site = Site(name=site_config.name, base_url=site_config.base_url)
                session.add(site)
                session.commit()
            
            logger.info(f"Processing site: {site.name}")
            
            # Create agent for this site
            agent = LLMAgent(self.llm_client, site_config)
            
            for prod_config in self.config.products:
                if filter_product and prod_config.canonical_name != filter_product:
                    continue
                
                # Get or create product
                product = session.query(Product).filter(Product.canonical_name == prod_config.canonical_name).first()
                if not product:
                    product = Product(canonical_name=prod_config.canonical_name, brand=prod_config.brand)
                    session.add(product)
                    session.commit()

                # Determine search term
                search_term = prod_config.search_name if prod_config.search_name else prod_config.canonical_name
                if prod_config.sites and site.name in prod_config.sites:
                     s_conf = prod_config.sites[site.name]
                     if s_conf.search_term:
                         search_term = s_conf.search_term
                
                logger.info(f"Searching for {search_term} on {site.name}")

                try:
                    # Navigate
                    if site_config.search_url_pattern:
                        url = site_config.search_url_pattern.format(query=search_term)
                        try:
                            # Use domcontentloaded for faster/more resilient loading
                            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        except Exception as e:
                             logger.warning(f"Navigation to {url} timed out or failed, attempting to proceed anyway: {e}")

                        # Optional: Wait for body to be present to ensure at least some content
                        try:
                             await page.wait_for_selector("body", timeout=5000)
                        except:
                             pass
                        
                        # Scroll down to ensure lazy loaded items are visible
                        try:
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                            await page.wait_for_timeout(1000)
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            # Wait for either products OR "not found" message
                            try:
                                await page.wait_for_function(
                                    f"""() => {{
                                        const hasProducts = document.querySelector('{site_config.selectors["product_container"]}');
                                        const hasNotFound = document.body.innerText.includes('Não encontramos nenhum resultado para');
                                        return hasProducts || hasNotFound;
                                    }}""",
                                    timeout=10000
                                )
                            except Exception as e:
                                logger.warning(f"Timeout waiting for search results on {site_config.name}: {e}")

                            # Check for specific "not found" indicators (must be visible)
                            is_not_found = await page.evaluate("""() => {
                                const el = Array.from(document.querySelectorAll('*')).find(el => 
                                    el.innerText && 
                                    el.innerText.includes('Não encontramos nenhum resultado para') &&
                                    el.offsetParent !== null
                                );
                                return !!el;
                            }""")
                            
                            if is_not_found:
                                logger.info(f"No results found for {search_term} on {site_config.name}")
                                continue
                        except:
                            pass

                        # Use Agent to extract
                        # Ideally: Search -> List -> Select -> Detail -> Extract
                        # For v1: Search -> Assume first result logic (or search results page extraction)
                        # Let's ask agent to search (if on home page) or just extract if on search page.
                        
                        # Simpler flow: 
                        # 1. Agent.search to get list of results
                        constraints = prod_config.constraints
                        results = await agent.search(page, search_term, constraints, prod_config.canonical_name)
                        
                        if results:
                            # Sort by price ascending to get the cheapest option
                            valid_results = [r for r in results if r.price is not None]
                            if valid_results:
                                valid_results.sort(key=lambda x: x.price)
                                best_match = valid_results[0]
                                logger.info(f"Selected cheapest product: {best_match.title} at {best_match.price}")
                            else:
                                best_match = results[0] # Naive fallback if no prices parsing worked
                            # TODO: Agent logic to pick best match
                            
                            if best_match.url:
                                is_absolute = best_match.url.startswith("http") or best_match.url.startswith("file")
                                if not is_absolute:
                                    # Handle protocol-relative URLs (//www.example.com/...)
                                    if best_match.url.startswith("//"):
                                        best_match.url = f"https:{best_match.url}"
                                    # Handle www. URLs
                                    elif best_match.url.startswith("www."):
                                        best_match.url = f"https://{best_match.url}"
                                    # Handle relative paths
                                    else:
                                        base = site_config.base_url.rstrip("/")
                                        path = best_match.url.lstrip("/")
                                        best_match.url = f"{base}/{path}"
                                
                                need_extraction = True
                                if site_config.skip_detail_extraction and best_match.price is not None:
                                    # Skip detail page if we have a price and config says so
                                    need_extraction = False
                                    logger.info(f"Skipping detail extraction for {product.canonical_name} as price {best_match.price} was found in search")
                                    
                                    # Construct observation from search result
                                    observation = ObservationDraft(
                                        title=best_match.title,
                                        price=best_match.price,
                                        currency="BRL", # Default or need to infer?
                                        product_url=best_match.url,
                                        availability="in_stock", # Assume in stock if found in list with price
                                        confidence=best_match.confidence,
                                        fetch_type=best_match.fetch_type
                                    )
                                
                                if need_extraction:
                                    await page.goto(best_match.url, wait_until="domcontentloaded", timeout=30000)
                                    # await page.wait_for_load_state("domcontentloaded") # Redundant
                                    
                                    observation = await agent.extract(page)
                                
                                # Store
                                obs_record = Observation(
                                    run_id=run_record.id,
                                    product_id=product.id,
                                    site_id=site.id,
                                    site_name=site.name,
                                    canonical_name=product.canonical_name,
                                    observed_at=run_record.started_at,
                                    price=observation.price,
                                    currency=observation.currency,
                                    title=observation.title,
                                    product_url=observation.product_url,
                                    availability=observation.availability,
                                    fetch_type=observation.fetch_type,
                                    raw_json=observation.raw_json
                                )
                                session.add(obs_record)
                                session.commit()
                                logger.info(f"Recorded price {observation.price} for {product.canonical_name}")
                            else:
                                logger.warning(f"No URL found for product {product.canonical_name}")
                        else:
                            logger.warning(f"No results found for {product.canonical_name}")

                except Exception as e:
                    logger.error(f"Error processing {product.canonical_name} on {site.name}: {e}")

