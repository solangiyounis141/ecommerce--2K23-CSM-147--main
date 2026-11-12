import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")


def make_engine(url: str, **kwargs):
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _enable_fk(dbapi_conn, _record):  # SQLite ignores FKs unless enabled
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return engine


engine = make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
