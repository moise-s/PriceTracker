from typing import List, Optional, Protocol, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field
from playwright.async_api import Page
from pricetracker.db.models import Product

class SearchResult(BaseModel):
    title: str
    url: str
    price: Optional[float] = None
    confidence: float = 1.0
    fetch_type: Optional[str] = None

class ObservationDraft(BaseModel):
    price: Optional[float] = None
    currency: Optional[str] = None
    unit_price: Optional[str] = None
    promo_price: Optional[float] = None
    promo_text: Optional[str] = None
    availability: str = "unknown"
    title: str
    product_url: str
    confidence: float = 1.0
    fetch_type: Optional[str] = None
    raw_json: Dict[str, Any] = Field(default_factory=dict)

class SiteAdapter(Protocol):
    """
    Interface for site-specific interaction.
    """
    
    async def search(self, page: Page, query: str) -> List[SearchResult]:
        """Search for a product and return list of results."""
        ...

    async def extract(self, page: Page) -> ObservationDraft:
        """Extract product details from the current page."""
        ...
