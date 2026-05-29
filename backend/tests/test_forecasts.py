"""
Tests for /api/v1/forecasts/* endpoints:
  GET  /forecasts/latest
  GET  /forecasts/{job_id}
  POST /forecasts/scenario
"""

import uuid
from datetime import datetime, timezone

import pytest

from tests.conftest import make_analytics_result


_FORECAST_DATA = {
    "history": [
        {"date": "2024-01-01", "fitted": 1000.0, "lower": 900.0, "upper": 1100.0},
        {"date": "2024-01-02", "fitted": 1050.0, "lower": 950.0, "upper": 1150.0},
    ],
    "forecast": [
        {"date": "2024-02-01", "yhat": 1200.0, "lower": 1100.0, "upper": 1300.0},
        {"date": "2024-02-02", "yhat": 1300.0, "lower": 1200.0, "upper": 1400.0},
    ],
    "summary": {"model_engine": "prophet"},
}


class TestGetLatestForecast:
    URL = "/api/v1/forecasts/latest"

    def test_no_completed_job_returns_404(self, client, auth_headers):
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 404

    def test_completed_job_no_forecast_data_returns_404(self, client, auth_headers, make_job):
        make_job(status="completed")
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 404

    def test_returns_forecast_from_cache(self, client, auth_headers, make_job, make_analysis):
        job = make_job(status="completed")
        make_analysis(job.id, "A15_prophet_forecast", _FORECAST_DATA)
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["forecast_periods"] == 2
        assert body["total_historical_days"] == 2
        assert body["method"] == "prophet"

    def test_forecast_summary_fields(self, client, auth_headers, make_job, make_analysis):
        job = make_job(status="completed")
        make_analysis(job.id, "A15_prophet_forecast", _FORECAST_DATA)
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        summary = r.json()["forecast_summary"]
        assert "total_forecast_revenue" in summary
        assert "avg_daily_forecast" in summary
        # 1200 + 1300 = 2500
        assert summary["total_forecast_revenue"] == pytest.approx(2500.0)

    def test_requires_auth(self, client):
        r = client.get(self.URL)
        assert r.status_code == 401


class TestGetForecastByJob:
    def test_get_by_job_id(self, client, auth_headers, make_job, make_analysis):
        job = make_job(status="completed")
        make_analysis(job.id, "A15_prophet_forecast", _FORECAST_DATA)
        r = client.get(f"/api/v1/forecasts/{job.id}", headers=auth_headers)
        assert r.status_code == 200
        assert str(r.json()["job_id"]) == str(job.id)

    def test_job_not_found_returns_404(self, client, auth_headers):
        r = client.get(f"/api/v1/forecasts/{uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 404

    def test_job_no_forecast_returns_404(self, client, auth_headers, make_job):
        job = make_job(status="completed")
        r = client.get(f"/api/v1/forecasts/{job.id}", headers=auth_headers)
        assert r.status_code == 404

    def test_requires_auth(self, client, make_job):
        job = make_job(status="completed")
        r = client.get(f"/api/v1/forecasts/{job.id}")
        assert r.status_code == 401


class TestScenario:
    URL = "/api/v1/forecasts/scenario"

    def _body(self, job_id=None, marketing=10.0, price=0.0, seasonal="medium"):
        b = {
            "marketing_spend_pct": marketing,
            "price_shift_pct": price,
            "seasonal_adjustment": seasonal,
        }
        if job_id:
            b["job_id"] = str(job_id)
        return b

    def test_scenario_math_marketing_10_pct(self, client, auth_headers, make_job, make_analysis):
        """
        marketing_spend_pct=10 → marketing_lift = 1 + (10/100)*0.3 = 1.03
        price_shift_pct=0 → price_effect = 1.0
        seasonal_adjustment=medium → seasonal_factor = 1.0
        total_multiplier = 1.03
        """
        job = make_job(status="completed")
        make_analysis(job.id, "A15_prophet_forecast", _FORECAST_DATA)
        r = client.post(self.URL, json=self._body(job.id, marketing=10.0, price=0.0),
                        headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["scenario_multiplier"] == pytest.approx(1.03, rel=1e-4)
        # yhat values scaled: 1200 * 1.03 = 1236, 1300 * 1.03 = 1339
        preds = body["predictions"]
        assert preds[0] == pytest.approx(1236.0, abs=0.1)
        assert preds[1] == pytest.approx(1339.0, abs=0.1)

    def test_scenario_price_shift(self, client, auth_headers, make_job, make_analysis):
        """price_shift_pct=10 → price_effect = 1 + (10/100)*0.7 = 1.07"""
        job = make_job(status="completed")
        make_analysis(job.id, "A15_prophet_forecast", _FORECAST_DATA)
        r = client.post(self.URL, json=self._body(job.id, marketing=0.0, price=10.0),
                        headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["scenario_multiplier"] == pytest.approx(1.07, rel=1e-4)

    def test_scenario_seasonal_high(self, client, auth_headers, make_job, make_analysis):
        """seasonal_adjustment=high → seasonal_factor=1.15"""
        job = make_job(status="completed")
        make_analysis(job.id, "A15_prophet_forecast", _FORECAST_DATA)
        r = client.post(self.URL, json=self._body(job.id, marketing=0.0, price=0.0,
                                                   seasonal="high"),
                        headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["scenario_multiplier"] == pytest.approx(1.15, rel=1e-4)

    def test_scenario_combined_multiplier(self, client, auth_headers, make_job, make_analysis):
        """
        marketing=10, price=0, seasonal=medium
        = 1.0 * 1.03 * 1.0 = 1.03
        Verify total_forecast_revenue is scaled correctly.
        """
        job = make_job(status="completed")
        make_analysis(job.id, "A15_prophet_forecast", _FORECAST_DATA)
        r = client.post(self.URL, json=self._body(job.id, marketing=10.0),
                        headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        expected_total = round((1200.0 + 1300.0) * 1.03, 2)
        assert body["total_forecast_revenue"] == pytest.approx(expected_total, abs=0.1)

    def test_scenario_no_completed_job_returns_404(self, client, auth_headers):
        r = client.post(self.URL, json=self._body(), headers=auth_headers)
        assert r.status_code == 404

    def test_scenario_no_forecast_data_returns_404(self, client, auth_headers, make_job):
        job = make_job(status="completed")
        r = client.post(self.URL, json=self._body(job.id), headers=auth_headers)
        assert r.status_code == 404

    def test_scenario_requires_auth(self, client):
        r = client.post(self.URL, json=self._body())
        assert r.status_code == 401
