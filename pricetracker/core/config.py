from typing import List, Optional, Dict, Union
from pydantic import BaseModel, Field
import yaml

class SiteConfig(BaseModel):
    name: str
    enabled: bool = True
    base_url: str
    search_url_pattern: Optional[str] = None
    skip_detail_extraction: bool = False
    selectors: Optional[Dict[str, str]] = None
    regions: Optional[List[str]] = None

class ProductSiteConfig(BaseModel):
    search_term: Optional[str] = None

class ProductConfig(BaseModel):
    canonical_name: str
    search_name: Optional[str] = None # Alternative name for search
    brand: Optional[str] = None
    constraints: Optional[Dict[str, Union[str, List[str]]]] = None
    sites: Optional[Dict[str, ProductSiteConfig]] = None

class DatabaseConfig(BaseModel):
    url: str

class AgentConfig(BaseModel):
    provider: str
    model: str
    api_key_env: str = "OPENAI_API_KEY"
    base_url: Optional[str] = None

class AppConfig(BaseModel):
    sites: List[SiteConfig]
    products: List[ProductConfig]
    database: DatabaseConfig
    agent: AgentConfig
    
    @classmethod
    def load(cls, path: str = "config.yaml") -> "AppConfig":
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)
