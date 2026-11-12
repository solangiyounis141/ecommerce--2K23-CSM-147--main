import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Category, Product, Sku, Variant
from app.seed import run_seed
from .conftest import make_category, make_product, make_sku

A = "/api/v1/admin"


# ---------- CAT06 authorization ----------
WRITE_ENDPOINTS = [
    ("post", f"{A}/products", {"name": "x", "slug": "x", "category_id": 1}),
    ("patch", f"{A}/products/1", {"name": "y"}),
    ("post", f"{A}/products/1/skus", {"code": "ABC-1", "price": "1.00"}),
    ("patch", f"{A}/skus/1", {"stock_quantity": 1}),
    ("post", f"{A}/categories", {"name": "c", "slug": "c"}),
    ("get", f"{A}/products", None),
    ("get", f"{A}/categories", None),
]


@pytest.mark.parametrize("method,url,body", WRITE_ENDPOINTS)
def test_unauthenticated_rejected(client, method, url, body):
    r = getattr(client, method)(url, **({"json": body} if body else {}))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "not_authenticated"


@pytest.mark.parametrize("method,url,body", WRITE_ENDPOINTS)
def test_non_admin_rejected(client, customer_headers, method, url, body):
    r = getattr(client, method)(url, headers=customer_headers, **({"json": body} if body else {}))
    assert r.status_code == 403


def test_garbage_token_rejected(client):
    r = client.get(f"{A}/products", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


# ---------- CAT01 categories ----------
def test_category_create_and_tree(client, admin_headers):
    root = make_category(client, admin_headers, "clothing")
    make_category(client, admin_headers, "t-shirts", root["id"])
    tree = client.get(f"{A}/categories", headers=admin_headers).json()["items"]
    assert len(tree) == 1 and tree[0]["children"][0]["slug"] == "t-shirts"


def test_duplicate_category_slug_409(client, admin_headers):
    make_category(client, admin_headers, "clothing")
    r = client.post(f"{A}/categories", json={"name": "Other", "slug": "clothing"}, headers=admin_headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_slug"


def test_bad_slug_validation_422(client, admin_headers):
    r = client.post(f"{A}/categories", json={"name": "X", "slug": "Bad Slug!"}, headers=admin_headers)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_category_cannot_be_own_parent(client, admin_headers):
    c = make_category(client, admin_headers, "a")
    r = client.patch(f"{A}/categories/{c['id']}", json={"parent_id": c["id"]}, headers=admin_headers)
    assert r.status_code == 422 and r.json()["error"]["code"] == "category_cycle"


def test_category_cycle_prevented(client, admin_headers):
    a = make_category(client, admin_headers, "a")
    b = make_category(client, admin_headers, "b", a["id"])
    c = make_category(client, admin_headers, "c", b["id"])
    r = client.patch(f"{A}/categories/{a['id']}", json={"parent_id": c["id"]}, headers=admin_headers)
    assert r.status_code == 422 and r.json()["error"]["code"] == "category_cycle"


def test_deactivating_parent_deactivates_children(client, admin_headers):
    a = make_category(client, admin_headers, "a")
    b = make_category(client, admin_headers, "b", a["id"])
    client.patch(f"{A}/categories/{a['id']}", json={"is_active": False}, headers=admin_headers)
    tree = client.get(f"{A}/categories", headers=admin_headers).json()["items"][0]
    assert tree["is_active"] is False and tree["children"][0]["is_active"] is False
    r = client.post(f"{A}/products", json={"name": "t", "slug": "t", "category_id": b["id"]}, headers=admin_headers)
    assert r.status_code == 422 and r.json()["error"]["code"] == "inactive_category"


def test_db_blocks_self_parent(db_session):
    db_session.add(Category(id=1, name="x", slug="x", parent_id=1))
    with pytest.raises(IntegrityError):
        db_session.commit()


# ---------- CAT02 products ----------
def test_product_created_as_draft(client, admin_headers):
    cat = make_category(client, admin_headers)
    p = make_product(client, admin_headers, cat["id"])
    assert p["status"] == "draft" and p["variants"] == []


def test_product_missing_required_fields_422(client, admin_headers):
    r = client.post(f"{A}/products", json={"name": "only name"}, headers=admin_headers)
    assert r.status_code == 422
    assert {d["field"] for d in r.json()["error"]["details"]} == {"slug", "category_id"}


def test_duplicate_product_slug_409(client, admin_headers):
    cat = make_category(client, admin_headers)
    make_product(client, admin_headers, cat["id"], "tee")
    r = client.post(f"{A}/products", json={"name": "T2", "slug": "tee", "category_id": cat["id"]}, headers=admin_headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_slug"


def test_unknown_category_422(client, admin_headers):
    r = client.post(f"{A}/products", json={"name": "T", "slug": "t", "category_id": 999}, headers=admin_headers)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_category"


def test_specifications_must_be_flat(client, admin_headers):
    cat = make_category(client, admin_headers)
    r = client.post(f"{A}/products", json={"name": "T", "slug": "t", "category_id": cat["id"],
                                           "specifications": {"nested": {"a": 1}}}, headers=admin_headers)
    assert r.status_code == 422


def test_draft_without_sku_ok_but_publish_needs_sku(client, admin_headers):
    cat = make_category(client, admin_headers)
    p = make_product(client, admin_headers, cat["id"])
    r = client.patch(f"{A}/products/{p['id']}", json={"status": "published"}, headers=admin_headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_sellable_sku"
    assert make_sku(client, admin_headers, p["id"]).status_code == 201
    r = client.patch(f"{A}/products/{p['id']}", json={"status": "published"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "published"


def test_delete_archives_product(client, admin_headers):
    cat = make_category(client, admin_headers)
    p = make_product(client, admin_headers, cat["id"])
    assert client.delete(f"{A}/products/{p['id']}", headers=admin_headers).status_code == 204
    assert client.get(f"{A}/products/{p['id']}", headers=admin_headers).json()["status"] == "archived"


# ---------- CAT03 / CAT04 SKUs, variants ----------
def test_sku_created_with_required_fields(client, admin_headers):
    cat = make_category(client, admin_headers)
    p = make_product(client, admin_headers, cat["id"])
    r = make_sku(client, admin_headers, p["id"], "tee-blk-m", {"size": "M", "color": "Black"})
    assert r.status_code == 201
    body = r.json()
    assert body["code"] == "TEE-BLK-M" and body["price"] == "19.99" and body["availability"] == "in_stock"


def test_sku_missing_price_422(client, admin_headers):
    cat = make_category(client, admin_headers)
    p = make_product(client, admin_headers, cat["id"])
    r = client.post(f"{A}/products/{p['id']}/skus", json={"code": "ABC-123"}, headers=admin_headers)
    assert r.status_code == 422


def test_duplicate_sku_code_409_even_across_products(client, admin_headers):
    cat = make_category(client, admin_headers)
    p1 = make_product(client, admin_headers, cat["id"], "p1")
    p2 = make_product(client, admin_headers, cat["id"], "p2")
    assert make_sku(client, admin_headers, p1["id"], "DUP-1").status_code == 201
    r = make_sku(client, admin_headers, p2["id"], "dup-1")
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_sku_code"


def test_negative_price_and_stock_rejected(client, admin_headers):
    cat = make_category(client, admin_headers)
    p = make_product(client, admin_headers, cat["id"])
    assert make_sku(client, admin_headers, p["id"], "NEG-1", stock_quantity=-1).status_code == 422
    assert make_sku(client, admin_headers, p["id"], "NEG-2", price="-5").status_code == 422
    assert make_sku(client, admin_headers, p["id"], "NEG-3", price="1.999").status_code == 422


def test_patch_sku_updates_and_rejects_negative_stock(client, admin_headers):
    cat = make_category(client, admin_headers)
    p = make_product(client, admin_headers, cat["id"])
    sku = make_sku(client, admin_headers, p["id"]).json()
    r = client.patch(f"{A}/skus/{sku['id']}", json={"stock_quantity": 0, "price": "25.50"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["availability"] == "out_of_stock" and r.json()["price"] == "25.50"
    r = client.patch(f"{A}/skus/{sku['id']}", json={"stock_quantity": -3}, headers=admin_headers)
    assert r.status_code == 422


def test_db_enforces_stock_price_and_unique_code(db_session):
    db_session.add_all([Category(id=1, name="c", slug="c"), Product(id=1, category_id=1, name="p", slug="p"),
                        Variant(id=1, product_id=1, option_values={}, option_key="{}")])
    db_session.commit()
    db_session.add(Sku(variant_id=1, code="OK-1", price=1, stock_quantity=-1))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    db_session.add(Sku(variant_id=1, code="OK-2", price=-1, stock_quantity=1))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    db_session.add_all([Sku(variant_id=1, code="SAME", price=1), Sku(variant_id=1, code="SAME", price=1)])
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_duplicate_variant_combination_409(client, admin_headers):
    cat = make_category(client, admin_headers)
    p = make_product(client, admin_headers, cat["id"])
    url = f"{A}/products/{p['id']}/variants"
    assert client.post(url, json={"option_values": {"size": "M", "color": "Black"}}, headers=admin_headers).status_code == 201
    r = client.post(url, json={"option_values": {"Color": "black", "SIZE": "M"}}, headers=admin_headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_variant"


def test_inconsistent_option_types_rejected(client, admin_headers):
    cat = make_category(client, admin_headers)
    p = make_product(client, admin_headers, cat["id"])
    assert make_sku(client, admin_headers, p["id"], "OPT-1", {"size": "M", "color": "Black"}).status_code == 201
    r = make_sku(client, admin_headers, p["id"], "OPT-2", {"size": "L"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_option_combination"
    r = make_sku(client, admin_headers, p["id"], "OPT-3")  # default variant clashes too
    assert r.status_code == 422


def test_missing_combination_is_not_created(client, admin_headers):
    cat = make_category(client, admin_headers)
    p = make_product(client, admin_headers, cat["id"])
    make_sku(client, admin_headers, p["id"], "T-BLK-M", {"size": "M", "color": "Black"})
    make_sku(client, admin_headers, p["id"], "T-WHT-L", {"size": "L", "color": "White"})
    data = client.get(f"{A}/products/{p['id']}", headers=admin_headers).json()
    combos = {tuple(sorted(v["option_values"].items())) for v in data["variants"]}
    assert len(combos) == 2  # Black/L and White/M were never invented
    assert sum(len(v["skus"]) for v in data["variants"]) == 2


def test_sku_variant_must_belong_to_product(client, admin_headers):
    cat = make_category(client, admin_headers)
    p1 = make_product(client, admin_headers, cat["id"], "p1")
    p2 = make_product(client, admin_headers, cat["id"], "p2")
    v = make_sku(client, admin_headers, p1["id"], "P1-A", {"size": "M"}).json()["variant_id"]
    r = client.post(f"{A}/products/{p2['id']}/skus", json={"code": "P2-A", "price": "1", "variant_id": v}, headers=admin_headers)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_variant"


def test_cannot_deactivate_last_sku_of_published_product(client, admin_headers):
    cat = make_category(client, admin_headers)
    p = make_product(client, admin_headers, cat["id"])
    sku = make_sku(client, admin_headers, p["id"]).json()
    client.patch(f"{A}/products/{p['id']}", json={"status": "published"}, headers=admin_headers)
    r = client.patch(f"{A}/skus/{sku['id']}", json={"is_active": False}, headers=admin_headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "last_sellable_sku"


# ---------- seed ----------
def test_seed_is_reproducible_and_idempotent(db_session):
    for _ in range(2):
        run_seed(db_session, "seed-admin@test.com", "pw-12345")
    assert db_session.query(Category).count() == 5
    assert db_session.query(Product).count() == 3
    assert db_session.query(Sku).count() == 6
    tee = db_session.query(Product).filter_by(slug="classic-cotton-tee").one()
    assert len(tee.variants) == 3  # White/L intentionally absent
