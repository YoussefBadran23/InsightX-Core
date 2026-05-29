"""
Tests for /api/v1/kpi/* endpoints:
  GET /kpi/summary
  GET /kpi/history
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.conftest import make_kpi_snapshot


class TestKpiSummary:
    URL = "/api/v1/kpi/summary"

    def test_summary_no_data_returns_zeros(self, client, auth_headers):
        """When no snapshots exist the endpoint returns zeros, not 404."""
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert float(body["total_revenue"]) == 0.0
        assert body["active_customers"] == 0

    def test_summary_with_latest_snapshot(self, client, auth_headers, make_snap):
        make_snap(snapshot_date=date.today())
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert float(body["total_revenue"]) == 10000.00
        assert body["active_customers"] == 200

    def test_summary_includes_region_fields(self, client, auth_headers, make_snap):
        make_snap()
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "revenue_na" in body
        assert "revenue_eu" in body
        assert "revenue_apac" in body
        assert "revenue_latam" in body

    def test_summary_mom_delta_with_two_snapshots(self, client, auth_headers, db, test_user):
        """32-row query path: latest + a snapshot ~30 days prior both present."""
        today = date.today()
        prev = today - timedelta(days=30)
        make_kpi_snapshot(db, test_user.id, snapshot_date=today, total_revenue=Decimal("12000.00"))
        make_kpi_snapshot(db, test_user.id, snapshot_date=prev, total_revenue=Decimal("10000.00"))
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["revenue_delta"] is not None
        # 12000 vs 10000 → +20%
        delta = body["revenue_delta"]
        assert delta["change_pct"] == pytest.approx(20.0, abs=0.5)
        assert delta["direction"] == "up"

    def test_summary_no_delta_when_only_one_snapshot(self, client, auth_headers, make_snap):
        make_snap(snapshot_date=date.today())
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        # revenue_delta may be None or flat when no comparison snapshot
        body = r.json()
        if body.get("revenue_delta"):
            assert body["revenue_delta"]["change_pct"] is None or body["revenue_delta"]["direction"] == "flat"

    def test_summary_source_currency_field(self, client, auth_headers, make_snap, make_job):
        make_job(status="completed", source_currency="EUR")
        make_snap()
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["source_currency"] == "EUR"

    def test_summary_requires_auth(self, client):
        r = client.get(self.URL)
        assert r.status_code == 401


class TestKpiHistory:
    URL = "/api/v1/kpi/history"

    def test_history_empty(self, client, auth_headers):
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["items"] == []

    def test_history_with_snapshots(self, client, auth_headers, db, test_user):
        today = date.today()
        for i in range(5):
            make_kpi_snapshot(db, test_user.id, snapshot_date=today - timedelta(days=i))
        r = client.get(self.URL + "?days=30", headers=auth_headers)
        assert r.status_code == 200
        assert len(r.json()["items"]) == 5

    def test_history_respects_days_param(self, client, auth_headers, db, test_user):
        today = date.today()
        # 1 recent, 1 old (outside 7-day window)
        make_kpi_snapshot(db, test_user.id, snapshot_date=today - timedelta(days=2))
        make_kpi_snapshot(db, test_user.id, snapshot_date=today - timedelta(days=60))
        r = client.get(self.URL + "?days=7", headers=auth_headers)
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1

    def test_history_requires_auth(self, client):
        r = client.get(self.URL)
        assert r.status_code == 401

    def test_history_days_validation(self, client, auth_headers):
        r = client.get(self.URL + "?days=3", headers=auth_headers)  # below minimum of 7
        assert r.status_code == 422
