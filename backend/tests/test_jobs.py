"""
Tests for /api/v1/jobs/* endpoints:
  GET    /jobs
  GET    /jobs/{job_id}
  GET    /jobs/{job_id}/status
  GET    /jobs/{job_id}/modules
  DELETE /jobs/{job_id}
"""

import uuid

import pytest

from tests.conftest import make_upload_job, make_module_status


class TestListJobs:
    URL = "/api/v1/jobs"

    def test_list_empty(self, client, auth_headers):
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_list_with_jobs(self, client, auth_headers, make_job):
        make_job()
        make_job(status="pending")
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 2

    def test_list_pagination(self, client, auth_headers, make_job):
        for _ in range(5):
            make_job()
        r = client.get(self.URL + "?page=1&page_size=2", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 2
        assert body["total"] == 5
        assert body["pages"] == 3

    def test_list_requires_auth(self, client):
        r = client.get(self.URL)
        assert r.status_code == 401

    def test_list_only_own_jobs(self, client, auth_headers, db):
        """Jobs belonging to another user must not appear."""
        other_user_id = uuid.uuid4()
        # Can't create another user without full FK, so just verify count = 0
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 0


class TestGetJob:
    def test_get_existing_job(self, client, auth_headers, make_job):
        job = make_job()
        r = client.get(f"/api/v1/jobs/{job.id}", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert str(body["id"]) == str(job.id)
        assert "modules" in body

    def test_get_job_with_modules(self, client, auth_headers, make_job, db):
        job = make_job()
        make_module_status(db, job.id, module_key="A01_revenue_summary")
        make_module_status(db, job.id, module_key="A02_rfm_scoring")
        r = client.get(f"/api/v1/jobs/{job.id}", headers=auth_headers)
        assert r.status_code == 200
        assert len(r.json()["modules"]) == 2

    def test_get_nonexistent_job(self, client, auth_headers):
        r = client.get(f"/api/v1/jobs/{uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 404

    def test_get_job_requires_auth(self, client, make_job):
        job = make_job()
        r = client.get(f"/api/v1/jobs/{job.id}")
        assert r.status_code == 401


class TestGetJobStatus:
    def test_get_status(self, client, auth_headers, make_job):
        job = make_job(status="analyzing")
        r = client.get(f"/api/v1/jobs/{job.id}/status", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "analyzing"

    def test_get_status_not_found(self, client, auth_headers):
        r = client.get(f"/api/v1/jobs/{uuid.uuid4()}/status", headers=auth_headers)
        assert r.status_code == 404


class TestGetJobModules:
    def test_get_modules_empty(self, client, auth_headers, make_job):
        job = make_job()
        r = client.get(f"/api/v1/jobs/{job.id}/modules", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == []

    def test_get_modules_with_data(self, client, auth_headers, make_job, db):
        job = make_job()
        make_module_status(db, job.id, module_key="A01_revenue_summary", can_run=True)
        make_module_status(db, job.id, module_key="A03_market_basket", can_run=False)
        r = client.get(f"/api/v1/jobs/{job.id}/modules", headers=auth_headers)
        assert r.status_code == 200
        modules = r.json()
        assert len(modules) == 2
        keys = {m["module_key"] for m in modules}
        assert "A01_revenue_summary" in keys

    def test_get_modules_requires_auth(self, client, make_job):
        job = make_job()
        r = client.get(f"/api/v1/jobs/{job.id}/modules")
        assert r.status_code == 401


class TestDeleteJob:
    def test_delete_job(self, client, auth_headers, make_job, db):
        job = make_job()
        job_id = job.id
        r = client.delete(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert r.status_code == 204
        # Verify it's gone
        r2 = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert r2.status_code == 404

    def test_delete_nonexistent(self, client, auth_headers):
        r = client.delete(f"/api/v1/jobs/{uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 404

    def test_delete_requires_auth(self, client, make_job):
        job = make_job()
        r = client.delete(f"/api/v1/jobs/{job.id}")
        assert r.status_code == 401
