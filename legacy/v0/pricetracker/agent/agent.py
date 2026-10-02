
import json
import logging
from typing import List, Dict, Any, Optional, Union
from playwright.async_api import Page
from pricetracker.core.interfaces import SiteAdapter, SearchResult, ObservationDraft
from pricetracker.core.llm import LLMClient
from pricetracker.agent.prompts import SEARCH_PROMPT, EXTRACTION_PROMPT

logger = logging.getLogger(__name__)

class LLMAgent(SiteAdapter):
    def __init__(self, llm_client: LLMClient, site_config: Optional['SiteConfig'] = None):
        self.llm = llm_client
        self.site_config = site_config

    async def _get_page_snapshot(self, page: Page, selectors: Optional[List[str]] = None) -> str:
        # Use html2text for better structure and density
        import html2text
        
        # Determine strict selectors logic
        if selectors:
            js_logic = f"""() => {{
                const selectors = {json.dumps(selectors)};
                for (const s of selectors) {{
                    const el = document.querySelector(s);
                    if (el) return el.outerHTML;
                }}
                return document.body.outerHTML;
            }}"""
        else:
             js_logic = "() => document.body.outerHTML"

        html = await page.evaluate(js_logic)
        
        # Configure converter
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.ignore_tables = False
        h.body_width = 0 # No wrapping
        
        # Convert
        text = h.handle(html)
        
        # Limit length, but increase it significantly (100k chars for larger context windows)
        return text[:100000]

    async def _try_deterministic_search(self, page: Page) -> List[SearchResult]:
        if not self.site_config or not self.site_config.selectors:
            return []
        
        selectors = self.site_config.selectors
        container_sel = selectors.get("product_container")
        title_sel = selectors.get("title")
        price_sel = selectors.get("price")
        link_sel = selectors.get("link") # Optional, might be container itself

        if not container_sel or not price_sel:
            return []

        logger.info(f"Attempting deterministic search with selectors: {selectors}")
        
        try:
            results_data = await page.evaluate(f"""() => {{
                const containers = document.querySelectorAll('{container_sel}');
                return Array.from(containers).map(c => {{
                    const titleEl = c.querySelector('{title_sel}');
                    const priceEl = c.querySelector('{price_sel}');
                    
                    let link = c.getAttribute('href');
                    if (!link) {{
                        if ('{link_sel}' !== 'undefined' && '{link_sel}' !== 'None') {{
                             const linkEl = c.querySelector('{link_sel}');
                             if (linkEl) link = linkEl.getAttribute('href');
                        }}
                        // Final fallback: if titleEl is an 'a' tag, use its href
                        if (!link && titleEl && titleEl.tagName === 'A') {{
                            link = titleEl.getAttribute('href');
                        }}
                    }}
                    
                    return {{
                        title: titleEl ? titleEl.innerText : null,
                        price: priceEl ? priceEl.innerText : null,
                        url: link
                    }};
                }});
            }}""") # Simple evaluation
            
            # Filter and convert
            results = []
            for r in results_data:
                cleaned_price = self._clean_price(r.get("price"))
                raw_url = r.get("url")
                logger.debug(f"Raw extracted URL: {raw_url}")
                if cleaned_price is not None and raw_url:
                    results.append(SearchResult(
                        title=r.get("title", "Unknown"),
                        url=raw_url,
                        price=cleaned_price,
                        confidence=1.0, # High confidence if selectors matched
                        fetch_type="deterministic"
                    ))
            
            logger.info(f"Deterministic search found {len(results)} valid results: {[r.title for r in results]}")
            return results

        except Exception as e:
            logger.warning(f"Deterministic search failed: {e}")
            return []

    # ... (clean_price remains same)


    def _clean_price(self, price_raw: Any) -> Optional[float]:
        if price_raw is None:
            return None
        if isinstance(price_raw, (int, float)):
            return float(price_raw)
        
        # String processing
        s = str(price_raw).strip()
        # Remove currency symbols and valid separators
        # Handle '7,79' (EU/BR) -> 7.79 and '1.000,00' -> 1000.00
        # Simple heuristic: remove everything except digits, comma, dot
        import re
        s_clean = re.sub(r'[^\d,.]', '', s)
        
        # If we have both . and , assume the last one is decimal separator
        if '.' in s_clean and ',' in s_clean:
            if s_clean.rfind('.') > s_clean.rfind(','):
                s_clean = s_clean.replace(',', '') # 1,000.00 -> 1000.00
            else:
                s_clean = s_clean.replace('.', '').replace(',', '.') # 1.000,00 -> 1000.00
        elif ',' in s_clean:
            # Assume comma is decimal if it's the only separator or looks like one
            s_clean = s_clean.replace(',', '.')
            
        try:
            return float(s_clean)
        except:
            logger.warning(f"Could not parse price: {price_raw}")
            return None

    async def search(self, page: Page, query: str, constraints: Optional[Dict[str, str]] = None, canonical_name: Optional[str] = None) -> List[SearchResult]:
        logger.info(f"Agent searching for: {query} with constraints: {constraints}")
        
        # 1. Try Deterministic Search first
        det_results = await self._try_deterministic_search(page)
        
        # Filter deterministic results if constraints exist (simple keyword matching)
        if det_results and constraints:
            filtered_det = []
            for r in det_results:
                if self._satisfies_constraints(r.title, constraints, canonical_name):
                    filtered_det.append(r)
            
            if filtered_det:
                 logger.info(f"Using {len(filtered_det)} deterministic results (filtered from {len(det_results)}), skipping LLM")
                 return filtered_det
            else:
                 logger.info(f"Deterministic results found but filtered out by constraints. Falling back to LLM.")

        elif det_results:
             logger.info(f"Using {len(det_results)} deterministic results, skipping LLM")
             return det_results

        # 2. Fallback to LLM
        logger.info(f"Falling back to LLM Agent searching for: {query}")
        
        # If we are already on a search page (handled by runner navigating to search_url_pattern), 
        # we might just need to extract.
        # But for general case, logic should be smarter. 
        # For v1, let's assume the runner navigates to search page if pattern exists, 
        # or defaults to home page.
        
        # Prioritize grid selectors for search to avoid header noise
        search_selectors = [
            '.vtex-search-result-3-x-gallery',
            '#gallery-layout-container',
            'main', 
            '.search-results',
            '#search-results',
            '.vtex-search-result-3-x-searchResultContainer'
        ]
        content = await self._get_page_snapshot(page, selectors=search_selectors)
        logger.info(f"Page Snapshot (first 1000 chars): {content[:1000]}")
        
        page_title = await page.title()
        
        # Simple extraction for now
        # Ideally this would be an iterative loop (Action -> Observation -> Action)
        # Here we just ask LLM to extract results from current page
        
        prompt = SEARCH_PROMPT.format(
            url=page.url,
            query=query,
            constraints=json.dumps(constraints) if constraints else "None",
            content_snapshot=content,
            page_title=page_title
        )
        
        response = await self.llm.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        try:
            data = json.loads(response)
            logger.info(f"LLM Search Response: {json.dumps(data, indent=2)}")
            results_data = data.get("results", [])
            results = []
            for r in results_data:
                title = r.get("title", "Unknown")
                
                # Apply same constraints verification to LLM results to prevent hallucination
                if constraints and not self._satisfies_constraints(title, constraints, canonical_name):
                    logger.info(f"LLM result '{title}' rejected by constraints verification")
                    continue

                results.append(SearchResult(
                    title=title,
                    url=r.get("url", ""),
                    price=self._clean_price(r.get("price")),
                    confidence=0.8,
                    fetch_type="llm"
                ))
            return results
        except Exception as e:
            logger.error(f"Failed to parse LLM search response: {e}")
            return []

    def _satisfies_constraints(self, title: str, constraints: Dict[str, Union[str, List[str]]], canonical_name: Optional[str] = None) -> bool:
        """
        Reuse the deterministic matching logic to verify titles.
        """
        # First check if canonical name is present in title
        if canonical_name:
            # Split canonical name into words and check if at least one significant word is in title
            words = [w for w in canonical_name.lower().split() if len(w) > 2]
            if words and not any(word in title.lower() for word in words):
                logger.debug(f"Title '{title}' rejected: doesn't contain canonical name '{canonical_name}'")
                return False
        
        if not constraints:
            return True
            
        for k, v in constraints.items():
            # Handle 'exclude' constraint (Negative match)
            if k == "exclude":
                should_exclude = False
                if isinstance(v, list):
                    for variant in v:
                        if self._match_variant(title, variant):
                            should_exclude = True
                            break
                else:
                    if self._match_variant(title, v):
                        should_exclude = True
                
                if should_exclude:
                    return False
                continue

            # Handle positive matches (OR logic within list)
            match = False
            if isinstance(v, list):
                for variant in v:
                    if self._match_variant(title, variant):
                        match = True
                        break
            else:
                if self._match_variant(title, v):
                    match = True
            
            if not match:
                return False
                
        return True

    def _match_variant(self, title: str, variant: str) -> bool:
        # Handle Regex
        if str(variant).startswith("regex:"):
            import re
            try:
                pattern = str(variant).split("regex:", 1)[1]
                if re.search(pattern, title, re.IGNORECASE):
                    return True
            except:
                pass
            return False
            
        # Standard Substring Match
        return str(variant).lower() in title.lower()

    async def extract(self, page: Page) -> ObservationDraft:
        logger.info(f"LLM Agent extracting from: {page.url}")
        # Use full body for extraction as details can be anywhere
        content = await self._get_page_snapshot(page, selectors=None)
        
        prompt = EXTRACTION_PROMPT.format(
            url=page.url,
            content_snapshot=content
        )
        
        response = await self.llm.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        try:
            data = json.loads(response)
            return ObservationDraft(
                price=data.get("price"),
                currency=data.get("currency", "BRL"),
                unit_price=data.get("unit_price"),
                promo_price=data.get("promo_price"),
                promo_text=data.get("promo_text"),
                availability=data.get("availability", "unknown"),
                title=data.get("title", ""),
                product_url=page.url,
                confidence=0.9,
                fetch_type="llm",
                raw_json=data
            )
        except Exception as e:
            logger.error(f"Failed to parse LLM extraction response: {e}")
            # Return empty/failed observation
            return ObservationDraft(
                title="Extraction Failed",
                product_url=page.url,
                availability="unknown",
                confidence=0.0
            )
