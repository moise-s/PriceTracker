from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pricetracker.core.config import AppConfig

def get_engine(db_url: str):
    is_sqlite = db_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    return create_engine(db_url, connect_args=connect_args)

def get_session_factory(db_url: str):
    engine = get_engine(db_url)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
