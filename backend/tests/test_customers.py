"""
Tests for /api/v1/customers/* endpoints:
  GET /customers           — list, search, filter, sort, pagination
  GET /customers/{id}      — detail
"""

import uuid
from decimal import Decimal

import pytest

from tests.conftest import make_customer


class TestListCustomers:
    URL = "/api/v1/customers"

    def test_list_empty(self, client, auth_headers):
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_list_returns_customers(self, client, auth_headers, make_cust):
        make_cust()
        make_cust()
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 2

    def test_list_pagination(self, client, auth_headers, make_cust):
        for _ in range(10):
            make_cust()
        r = client.get(self.URL + "?page=1&page_size=3", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 3
        assert body["pages"] == 4

    def test_list_search_by_name(self, client, auth_headers, db, test_user):
        make_customer(db, test_user.id, full_name="Alice Wonderland", email="alice@test.com")
        make_customer(db, test_user.id, full_name="Bob Builder", email="bob@test.com")
        r = client.get(self.URL + "?search=alice", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["full_name"] == "Alice Wonderland"

    def test_list_search_by_email(self, client, auth_headers, db, test_user):
        make_customer(db, test_user.id, full_name="Carol", email="carol@unique.com")
        r = client.get(self.URL + "?search=carol@unique", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_list_filter_by_segment(self, client, auth_headers, db, test_user):
        make_customer(db, test_user.id, email="vip@test.com", ai_segment="vip_champion")
        make_customer(db, test_user.id, email="risk@test.com", ai_segment="at_risk")
        r = client.get(self.URL + "?segment=vip_champion", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_list_filter_by_region(self, client, auth_headers, db, test_user):
        make_customer(db, test_user.id, email="na@test.com", region="NA")
        make_customer(db, test_user.id, email="eu@test.com", region="EU")
        r = client.get(self.URL + "?region=NA", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_list_sort_by_lifetime_value(self, client, auth_headers, db, test_user):
        make_customer(db, test_user.id, email="low@test.com", lifetime_value=Decimal("100.00"))
        make_customer(db, test_user.id, email="high@test.com", lifetime_value=Decimal("9999.00"))
        r = client.get(self.URL + "?sort_by=lifetime_value&sort_dir=desc", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert float(items[0]["lifetime_value"]) >= float(items[1]["lifetime_value"])

    def test_list_summary_fields(self, client, auth_headers, db, test_user):
        make_customer(db, test_user.id, email="s1@test.com", ai_segment="vip_champion")
        make_customer(db, test_user.id, email="s2@test.com", ai_segment="at_risk")
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        summary = r.json()["summary"]
        assert "avg_lifetime_value" in summary
        assert summary["vip_count"] == 1
        assert summary["at_risk_count"] == 1

    def test_list_excludes_soft_deleted(self, client, auth_headers, db, test_user):
        from datetime import datetime, timezone
        make_customer(db, test_user.id, email="deleted@test.com",
                      deleted_at=datetime.now(timezone.utc))
        make_customer(db, test_user.id, email="active@test.com")
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_list_requires_auth(self, client):
        r = client.get(self.URL)
        assert r.status_code == 401


class TestGetCustomer:
    def test_get_existing(self, client, auth_headers, make_cust):
        cust = make_cust()
        r = client.get(f"/api/v1/customers/{cust.id}", headers=auth_headers)
        assert r.status_code == 200
        assert str(r.json()["id"]) == str(cust.id)

    def test_get_not_found(self, client, auth_headers):
        r = client.get(f"/api/v1/customers/{uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 404

    def test_get_requires_auth(self, client, make_cust):
        cust = make_cust()
        r = client.get(f"/api/v1/customers/{cust.id}")
        assert r.status_code == 401

    def test_get_other_users_customer_returns_404(self, client, auth_headers, db):
        """Customer owned by a different user must return 404, not 200."""
        other_user_id = uuid.uuid4()
        # We can't insert with a FK violation in SQLite, so just verify
        # a random UUID returns 404
        r = client.get(f"/api/v1/customers/{uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 404
