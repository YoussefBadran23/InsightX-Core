"""
Tests for /api/v1/products/* endpoints:
  GET /products            — list, search, filter ABC tier, low-stock, sort, pagination
  GET /products/{id}       — detail
"""

import uuid
from decimal import Decimal

import pytest

from tests.conftest import make_product


class TestListProducts:
    URL = "/api/v1/products"

    def test_list_empty(self, client, auth_headers):
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_list_returns_products(self, client, auth_headers, make_prod):
        make_prod()
        make_prod()
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 2

    def test_list_pagination(self, client, auth_headers, make_prod):
        for _ in range(8):
            make_prod()
        r = client.get(self.URL + "?page=1&page_size=3", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 3
        assert body["pages"] == 3

    def test_search_by_name(self, client, auth_headers, db, test_user):
        make_product(db, test_user.id, name="Wireless Headphones", sku="WH-001", category="Audio")
        make_product(db, test_user.id, name="USB Cable", sku="USB-002", category="Cables")
        r = client.get(self.URL + "?search=wireless", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_search_by_sku(self, client, auth_headers, db, test_user):
        make_product(db, test_user.id, name="Monitor", sku="MON-4K-01", category="Displays")
        r = client.get(self.URL + "?search=MON-4K", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_filter_by_category(self, client, auth_headers, db, test_user):
        make_product(db, test_user.id, name="P1", sku="P1", category="Electronics")
        make_product(db, test_user.id, name="P2", sku="P2", category="Furniture")
        r = client.get(self.URL + "?category=Electronics", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_filter_by_abc_tier(self, client, auth_headers, db, test_user):
        make_product(db, test_user.id, name="Tier A", sku="TA-01", category="X", abc_tier="A")
        make_product(db, test_user.id, name="Tier B", sku="TB-01", category="X", abc_tier="B")
        r = client.get(self.URL + "?abc_tier=A", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_filter_low_stock_only(self, client, auth_headers, db, test_user):
        make_product(db, test_user.id, name="Low", sku="LO-01", category="X",
                     stock_qty=2, low_stock_threshold=10)
        make_product(db, test_user.id, name="Full", sku="FU-01", category="X",
                     stock_qty=100, low_stock_threshold=10)
        r = client.get(self.URL + "?low_stock_only=true", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["sku"] == "LO-01"

    def test_sort_by_revenue_desc(self, client, auth_headers, db, test_user):
        make_product(db, test_user.id, name="Cheap", sku="CH-01", category="X",
                     total_revenue=Decimal("100.00"))
        make_product(db, test_user.id, name="Expensive", sku="EX-01", category="X",
                     total_revenue=Decimal("50000.00"))
        r = client.get(self.URL + "?sort_by=total_revenue&sort_dir=desc", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert float(items[0]["total_revenue"]) >= float(items[1]["total_revenue"])

    def test_list_summary_fields(self, client, auth_headers, db, test_user):
        make_product(db, test_user.id, name="A", sku="A1", category="Cat1",
                     unit_price=Decimal("10.00"), stock_qty=5)
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        summary = r.json()["summary"]
        assert "inventory_value" in summary
        assert "low_stock_count" in summary
        assert "categories_count" in summary

    def test_excludes_soft_deleted(self, client, auth_headers, db, test_user):
        from datetime import datetime, timezone
        make_product(db, test_user.id, name="Gone", sku="GN-01", category="X",
                     deleted_at=datetime.now(timezone.utc))
        make_product(db, test_user.id, name="Active", sku="AC-01", category="X")
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_excludes_inactive(self, client, auth_headers, db, test_user):
        make_product(db, test_user.id, name="Inactive", sku="IN-01", category="X", is_active=False)
        make_product(db, test_user.id, name="Active", sku="AC-02", category="X", is_active=True)
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_list_requires_auth(self, client):
        r = client.get(self.URL)
        assert r.status_code == 401


class TestGetProduct:
    def test_get_existing(self, client, auth_headers, make_prod):
        prod = make_prod()
        r = client.get(f"/api/v1/products/{prod.id}", headers=auth_headers)
        assert r.status_code == 200
        assert str(r.json()["id"]) == str(prod.id)

    def test_get_not_found(self, client, auth_headers):
        r = client.get(f"/api/v1/products/{uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 404

    def test_get_requires_auth(self, client, make_prod):
        prod = make_prod()
        r = client.get(f"/api/v1/products/{prod.id}")
        assert r.status_code == 401
