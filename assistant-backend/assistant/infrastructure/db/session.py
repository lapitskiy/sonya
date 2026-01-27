from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from assistant.config.settings import DATABASE_URL


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def session_factory():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

