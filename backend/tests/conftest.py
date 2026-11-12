import os

os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import create_token, hash_password
from app.database import get_db, make_engine
from app.main import app
from app.models import Base, User


@pytest.fixture()
def db_session():
    engine = make_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    with Session() as session:
        yield session


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _user(db, email, role):
    u = User(email=email, password_hash=hash_password("pw-12345"), role=role)
    db.add(u)
    db.commit()
    return u


@pytest.fixture()
def admin_headers(db_session):
    return {"Authorization": f"Bearer {create_token(_user(db_session, 'admin@test.com', 'admin'))}"}


@pytest.fixture()
def customer_headers(db_session):
    return {"Authorization": f"Bearer {create_token(_user(db_session, 'cust@test.com', 'customer'))}"}


# ---- helpers ----
def make_category(client, h, slug="clothing", parent_id=None):
    r = client.post("/api/v1/admin/categories", json={"name": slug.title(), "slug": slug, "parent_id": parent_id}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def make_product(client, h, category_id, slug="tee"):
    r = client.post("/api/v1/admin/products", json={"name": "Tee", "slug": slug, "category_id": category_id}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def make_sku(client, h, product_id, code="TEE-BLK-M", options=None, **extra):
    body = {"code": code, "price": "19.99", "stock_quantity": 5, **extra}
    if options is not None:
        body["option_values"] = options
    return client.post(f"/api/v1/admin/products/{product_id}/skus", json=body, headers=h)
