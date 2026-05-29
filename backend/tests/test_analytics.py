"""
Tests for /api/v1/analytics/* endpoints:
  GET /analytics/summary
  GET /analytics/{analysis_type}
"""

import uuid

import pytest

from tests.conftest import make_analytics_result


class TestAnalyticsSummary:
    URL = "/api/v1/analytics/summary"

    def test_summary_no_jobs_returns_404(self, client, auth_headers):
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 404

    def test_summary_with_completed_job(self, client, auth_headers, make_job, make_analysis):
        job = make_job(status="completed")
        make_analysis(job.id, "A01_revenue_summary", {"total": 50000})
        make_analysis(job.id, "A02_rfm_scoring", {"segments": []})
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "job_id" in body
        assert "modules" in body
        assert "A01_revenue_summary" in body["modules"]
        assert "A02_rfm_scoring" in body["modules"]

    def test_summary_column_projection(self, client, auth_headers, make_job, make_analysis):
        """Verify the column-projected query returns analysis_type + result_json keys."""
        job = make_job(status="completed")
        make_analysis(job.id, "A01_revenue_summary", {"total": 12345})
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        # modules dict must have the analysis_type as key and the result dict as value
        assert isinstance(body["modules"], dict)
        assert body["modules"]["A01_revenue_summary"]["total"] == 12345

    def test_summary_with_explicit_job_id(self, client, auth_headers, make_job, make_analysis):
        job = make_job(status="completed")
        make_analysis(job.id, "A04_gross_margin", {"margin_pct": 35.0})
        r = client.get(self.URL + f"?job_id={job.id}", headers=auth_headers)
        assert r.status_code == 200
        assert "A04_gross_margin" in r.json()["modules"]

    def test_summary_wrong_job_id(self, client, auth_headers):
        r = client.get(self.URL + f"?job_id={uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 404

    def test_summary_requires_auth(self, client):
        r = client.get(self.URL)
        assert r.status_code == 401


class TestGetAnalytics:
    def test_get_revenue_by_alias(self, client, auth_headers, make_job, make_analysis):
        job = make_job(status="completed")
        make_analysis(job.id, "A01_revenue_summary", {"total": 9999})
        r = client.get("/api/v1/analytics/revenue", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["analysis_type"] == "A01_revenue_summary"
        assert body["result_json"]["total"] == 9999

    def test_get_rfm_by_alias(self, client, auth_headers, make_job, make_analysis):
        job = make_job(status="completed")
        make_analysis(job.id, "A02_rfm_scoring", {"segments": ["Champions"]})
        r = client.get("/api/v1/analytics/rfm", headers=auth_headers)
        assert r.status_code == 200

    def test_get_by_full_module_key(self, client, auth_headers, make_job, make_analysis):
        job = make_job(status="completed")
        make_analysis(job.id, "A07_abc_classification", {"tiers": {"A": 10}})
        r = client.get("/api/v1/analytics/A07_abc_classification", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["analysis_type"] == "A07_abc_classification"

    def test_get_returns_result_json_and_analysis_type(self, client, auth_headers, make_job, make_analysis):
        """Column projection test: response must contain both keys."""
        job = make_job(status="completed")
        make_analysis(job.id, "A05_cohort_retention", {"cohorts": []})
        r = client.get("/api/v1/analytics/cohort", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "analysis_type" in body
        assert "result_json" in body

    def test_get_no_completed_job_returns_404(self, client, auth_headers):
        r = client.get("/api/v1/analytics/revenue", headers=auth_headers)
        assert r.status_code == 404

    def test_get_with_explicit_job_id(self, client, auth_headers, make_job, make_analysis):
        job = make_job(status="completed")
        make_analysis(job.id, "A08_aov_trends", {"avg": 75.5})
        r = client.get(f"/api/v1/analytics/aov?job_id={job.id}", headers=auth_headers)
        assert r.status_code == 200

    def test_get_requires_auth(self, client):
        r = client.get("/api/v1/analytics/revenue")
        assert r.status_code == 401

    def test_get_unknown_module_no_data_returns_404(self, client, auth_headers, make_job):
        make_job(status="completed")
        # A completed job exists but no A01 result
        r = client.get("/api/v1/analytics/revenue", headers=auth_headers)
        assert r.status_code == 404
