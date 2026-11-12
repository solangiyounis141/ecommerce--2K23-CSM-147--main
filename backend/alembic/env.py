import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os

from alembic import context
from sqlalchemy import create_engine

from app.models import Base

config = context.config
url = os.getenv("DATABASE_URL", "sqlite:///./dev.db")


def run_migrations_online():
    engine = create_engine(url)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
