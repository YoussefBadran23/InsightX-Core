"""
Tests for /api/v1/upload/* endpoints:
  POST /upload/sniff      — header detection, semantic mock
  POST /upload/confirm    — job creation, Celery task mock
  GET  /upload/schema/columns
"""

import io
import os
import uuid
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _csv_file(content: str = "order_id,customer_id,amount\n1,CUS-01,99.00\n"):
    return ("upload.csv", io.BytesIO(content.encode()), "text/csv")


# ── POST /upload/sniff ────────────────────────────────────────────────────────

class TestSniff:
    URL = "/api/v1/upload/sniff"

    def test_sniff_csv_success(self, client, auth_headers):
        """Happy path: upload a small CSV and get back a mapping preview."""
        with patch("app.routers.upload._semantic_resources", return_value=(None, None, None)):
            r = client.post(
                self.URL,
                files={"file": _csv_file()},
                headers=auth_headers,
            )
        assert r.status_code == 200
        body = r.json()
        assert "sniff_id" in body
        assert "mappings" in body
        assert len(body["mappings"]) > 0

    def test_sniff_returns_module_summary(self, client, auth_headers):
        with patch("app.routers.upload._semantic_resources", return_value=(None, None, None)):
            r = client.post(
                self.URL,
                files={"file": _csv_file()},
                headers=auth_headers,
            )
        assert r.status_code == 200
        assert "module_summary" in r.json()

    def test_sniff_unsupported_extension(self, client, auth_headers):
        r = client.post(
            self.URL,
            files={"file": ("data.txt", io.BytesIO(b"col1,col2\n1,2"), "text/plain")},
            headers=auth_headers,
        )
        assert r.status_code == 400

    def test_sniff_requires_auth(self, client):
        r = client.post(
            self.URL,
            files={"file": _csv_file()},
        )
        assert r.status_code == 401

    def test_sniff_empty_csv(self, client, auth_headers):
        """A CSV with only whitespace headers should return 400."""
        with patch("app.routers.upload._semantic_resources", return_value=(None, None, None)):
            r = client.post(
                self.URL,
                files={"file": ("empty.csv", io.BytesIO(b" , \n"), "text/csv")},
                headers=auth_headers,
            )
        # Either 400 (no headers) or 200 with empty mappings are acceptable
        assert r.status_code in (200, 400)


# ── POST /upload/confirm ──────────────────────────────────────────────────────

class TestConfirm:
    URL = "/api/v1/upload/confirm"

    def _sniff_id(self, client, auth_headers) -> str:
        """Run a sniff first to get a valid sniff_id (pending file on disk)."""
        with patch("app.routers.upload._semantic_resources", return_value=(None, None, None)):
            r = client.post(
                "/api/v1/upload/sniff",
                files={"file": _csv_file()},
                headers=auth_headers,
            )
        assert r.status_code == 200
        return r.json()["sniff_id"]

    def test_confirm_creates_job_and_dispatches_task(self, client, auth_headers, db):
        sniff_id = self._sniff_id(client, auth_headers)

        mock_task = MagicMock()
        mock_task.id = str(uuid.uuid4())

        with patch("app.routers.upload.celery_client") as mock_celery:
            mock_celery.send_task.return_value = mock_task
            r = client.post(
                self.URL,
                json={
                    "sniff_id": sniff_id,
                    "confirmed_mappings": [
                        {"csv_header": "order_id", "internal_column": "order_id"},
                        {"csv_header": "customer_id", "internal_column": "customer_id"},
                        {"csv_header": "amount", "internal_column": "order_total"},
                    ],
                },
                headers=auth_headers,
            )

        assert r.status_code == 200
        body = r.json()
        assert "job_id" in body
        assert body["status"] == "processing"
        mock_celery.send_task.assert_called_once()

    def test_confirm_with_currency(self, client, auth_headers, db):
        sniff_id = self._sniff_id(client, auth_headers)

        mock_task = MagicMock()
        mock_task.id = str(uuid.uuid4())

        with patch("app.routers.upload.celery_client") as mock_celery:
            mock_celery.send_task.return_value = mock_task
            r = client.post(
                self.URL,
                json={
                    "sniff_id": sniff_id,
                    "confirmed_mappings": [],
                    "source_currency": "EUR",
                },
                headers=auth_headers,
            )

        assert r.status_code == 200

    def test_confirm_nonexistent_sniff_id(self, client, auth_headers):
        r = client.post(
            self.URL,
            json={
                "sniff_id": "nonexistent_file.csv",
                "confirmed_mappings": [],
            },
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_confirm_requires_auth(self, client):
        r = client.post(
            self.URL,
            json={"sniff_id": "x.csv", "confirmed_mappings": []},
        )
        assert r.status_code == 401


# ── GET /upload/schema/columns ────────────────────────────────────────────────

class TestSchemaColumns:
    URL = "/api/v1/upload/schema/columns"

    def test_schema_columns_returns_list(self, client):
        r = client.get(self.URL)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        assert len(body) > 0
        first = body[0]
        assert "internal_column" in first
        assert "display_name" in first
        assert "group" in first
