"""SQLAlchemy models. Importing this package registers every table on ``Base.metadata``."""

from pricetracker.db.base import Base
from pricetracker.models.accounts import (
    Address,
    LoginAttempt,
    Profile,
    RecoveryCode,
    User,
    UserSession,
    UserStoreSelection,
    Vehicle,
)
from pricetracker.models.catalog import (
    CatalogItem,
    Image,
    ListItem,
    Product,
    ProductMarketPin,
    ShoppingList,
)
from pricetracker.models.markets import AdapterVersion, Market, Store
from pricetracker.models.runs import Candidate, Observation, Run, RunEvent, RunTarget
from pricetracker.models.system import (
    AppSetting,
    GeoCache,
    HttpCache,
    LlmCache,
    LlmCall,
    LlmProvider,
    Notification,
    PriceAlert,
    Schedule,
)

__all__ = [
    "AdapterVersion",
    "Address",
    "AppSetting",
    "Base",
    "Candidate",
    "CatalogItem",
    "GeoCache",
    "HttpCache",
    "Image",
    "ListItem",
    "LlmCache",
    "LlmCall",
    "LlmProvider",
    "LoginAttempt",
    "Market",
    "Notification",
    "Observation",
    "PriceAlert",
    "Product",
    "ProductMarketPin",
    "Profile",
    "RecoveryCode",
    "Run",
    "RunEvent",
    "RunTarget",
    "Schedule",
    "ShoppingList",
    "Store",
    "User",
    "UserSession",
    "UserStoreSelection",
    "Vehicle",
]
