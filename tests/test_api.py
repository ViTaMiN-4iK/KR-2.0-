"""Tests for API routes."""

from __future__ import annotations

import json
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pandas as pd

from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import alerts as routes_alerts
from src.api.routes import users as routes_users
from src.api.routes import reports as routes_reports
from src.alerts.manager import AlertManager
from src.reporting.pdf_generator import PDFReportGenerator
from src.api.schemas import (
    AlertResponse,
    AlertUpdate,
    RiskLevel,
    AlertStatus,
)


class TestAlertSchemas:
    """Tests for API Pydantic schemas."""

    def test_alert_response_valid(self):
        """Test valid AlertResponse creation."""
        alert = AlertResponse(
            alert_id="test-001",
            event_id="evt_001",
            user_id="user_1",
            username="user_1@test",
            timestamp="2026-01-01T10:00:00Z",
            anomaly_score=0.75,
            risk_level=RiskLevel.HIGH,
            detected_by_model="isolation_forest",
            reason="Test reason",
            status=AlertStatus.OPEN,
            severity="high",
            created_at="2026-01-01T10:00:00Z",
            updated_at="2026-01-01T10:00:00Z",
        )

        assert alert.risk_level == RiskLevel.HIGH
        assert alert.anomaly_score == 0.75

    def test_alert_score_validation(self):
        """Test that anomaly_score is validated (0-1 range)."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AlertResponse(
                alert_id="test-002",
                event_id="evt_002",
                user_id="user_2",
                username="user_2@test",
                timestamp="2026-01-01T10:00:00Z",
                anomaly_score=1.5,  # Invalid: > 1.0
                risk_level=RiskLevel.HIGH,
                detected_by_model="isolation_forest",
                reason="Test",
                status=AlertStatus.OPEN,
                severity="high",
                created_at="2026-01-01T10:00:00Z",
                updated_at="2026-01-01T10:00:00Z",
            )

    def test_alert_update_optional_fields(self):
        """Test AlertUpdate with optional fields."""
        update = AlertUpdate(
            status=AlertStatus.INVESTIGATING,
            notes="Investigation in progress",
        )

        assert update.status == AlertStatus.INVESTIGATING
        assert update.notes == "Investigation in progress"

    def test_alert_update_all_optional(self):
        """Test AlertUpdate with no fields (all optional)."""
        update = AlertUpdate()
        assert update.status is None
        assert update.notes is None


# ---- Fixtures ----

@pytest.fixture
def temp_storage():
    """Temporary alerts storage."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"alerts": []}, f)
        temp_path = f.name
    yield temp_path
    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def seeded_alert_manager(temp_storage):
    """AlertManager with one pre-seeded alert, persisted to file."""
    import uuid
    from src.api.schemas import AlertStatus
    alert = {
        "alert_id": str(uuid.uuid4()),
        "event_id": "evt_api_001",
        "user_id": "user_api_1",
        "username": "api_user_1@test",
        "timestamp": "2026-01-15T10:00:00Z",
        "anomaly_score": 0.85,
        "risk_level": "high",
        "detected_by_model": "isolation_forest",
        "reason": "Unusual activity",
        "features": {"hour": 2.0, "is_night": 1.0},
        "status": "open",
        "severity": "high",
        "created_at": "2026-01-15T10:00:00Z",
        "updated_at": "2026-01-15T10:00:00Z",
        "investigation_notes": "",
        "resolved_by": "",
        "anomaly_context": {"items": []},
    }
    with open(temp_storage, "w") as f:
        json.dump({"alerts": [alert]}, f)
    mgr = AlertManager(storage_path=temp_storage)
    return mgr


@pytest.fixture
def mock_report_dir(tmp_path):
    """Temporary reports directory."""
    reports = tmp_path / "reports"
    reports.mkdir()
    return reports


# ---- API Endpoint Tests ----

class TestAlertEndpoints:
    """Integration tests for /api/alerts endpoints via TestClient."""

    def test_health_check(self):
        """GET /health returns healthy status."""
        # Bypass lifespan (no data files needed)
        with patch("src.api.routes.alerts._alert_manager_getter", None):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health")
            # Health check doesn't use lazy components — always works
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"

    def test_root_endpoint(self):
        """GET / returns service info."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert data["version"] == "0.1.0"

    def test_list_alerts_empty(self, seeded_alert_manager):
        """GET /api/alerts returns alert list."""
        routes_alerts.set_alert_manager(lambda: seeded_alert_manager)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/alerts/")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "alerts" in data
        assert data["total"] >= 1

    def test_list_alerts_filter_by_status(self, seeded_alert_manager):
        """GET /api/alerts?status=open filters correctly."""
        routes_alerts.set_alert_manager(lambda: seeded_alert_manager)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/alerts/?status=open")
        assert response.status_code == 200
        data = response.json()
        for alert in data["alerts"]:
            assert alert["status"] == "open"

    def test_get_alert_by_id(self, seeded_alert_manager):
        """GET /api/alerts/{id} returns alert details."""
        routes_alerts.set_alert_manager(lambda: seeded_alert_manager)
        client = TestClient(app, raise_server_exceptions=False)

        # First list to get the ID
        list_resp = client.get("/api/alerts/")
        alert_id = list_resp.json()["alerts"][0]["alert_id"]

        response = client.get(f"/api/alerts/{alert_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["alert_id"] == alert_id
        assert data["risk_level"] == "high"

    def test_get_alert_not_found(self, seeded_alert_manager):
        """GET /api/alerts/{id} returns 404 for unknown ID."""
        routes_alerts.set_alert_manager(lambda: seeded_alert_manager)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/alerts/nonexistent_id_xyz")
        assert response.status_code == 404

    def test_update_alert_status(self, seeded_alert_manager):
        """PATCH /api/alerts/{id} updates status."""
        routes_alerts.set_alert_manager(lambda: seeded_alert_manager)
        client = TestClient(app, raise_server_exceptions=False)

        list_resp = client.get("/api/alerts/")
        alert_id = list_resp.json()["alerts"][0]["alert_id"]

        response = client.patch(
            f"/api/alerts/{alert_id}",
            json={"status": "investigating", "notes": "Checking this"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "investigating"

    def test_update_alert_no_fields(self, seeded_alert_manager):
        """PATCH with no fields returns 400."""
        routes_alerts.set_alert_manager(lambda: seeded_alert_manager)
        client = TestClient(app, raise_server_exceptions=False)
        list_resp = client.get("/api/alerts/")
        alert_id = list_resp.json()["alerts"][0]["alert_id"]

        response = client.patch(f"/api/alerts/{alert_id}", json={})
        assert response.status_code == 400

    def test_alert_stats(self, seeded_alert_manager):
        """GET /api/alerts/stats returns statistics."""
        routes_alerts.set_alert_manager(lambda: seeded_alert_manager)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/alerts/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "by_risk_level" in data
        assert data["total"] >= 1

    def test_alert_manager_not_initialized(self):
        """Endpoints return 503 when alert manager is not set."""
        routes_alerts.set_alert_manager(None)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/alerts/")
        assert response.status_code == 503


class TestUserEndpoints:
    """Tests for /api/users endpoints."""

    def test_list_users_no_data(self):
        """GET /api/users returns 503 when users not loaded."""
        routes_users.set_data(None, None)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/users/")
        assert response.status_code == 503

    def test_get_user_no_data(self):
        """GET /api/users/{id} returns 503 when users not loaded."""
        routes_users.set_data(None, None)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/users/user_1")
        assert response.status_code == 503

    def test_list_users_with_data(self):
        """GET /api/users returns user list when data is set."""
        df_users = pd.DataFrame([{
            "user_id": "u1",
            "username": "user_one",
            "full_name": "User One",
            "role": "developer",
            "department": "IT",
            "total_events": 10,
            "unique_actions": 3,
            "unique_locations": 1,
        }])
        routes_users.set_data(None, df_users)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/users/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    def test_get_user_with_data(self):
        """GET /api/users/{id} returns user profile."""
        df_users = pd.DataFrame([{
            "user_id": "u2",
            "username": "user_two",
            "full_name": "User Two",
            "role": "analyst",
            "department": "Finance",
            "total_events": 5,
            "unique_actions": 2,
            "unique_locations": 1,
        }])
        routes_users.set_data(None, df_users)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/users/u2")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "u2"

    def test_get_user_not_found(self):
        """GET /api/users/{id} returns 404 for unknown user."""
        df_users = pd.DataFrame([{
            "user_id": "u3",
            "username": "user_three",
            "full_name": "User Three",
            "role": "analyst",
            "department": "HR",
            "total_events": 2,
            "unique_actions": 1,
            "unique_locations": 1,
        }])
        routes_users.set_data(None, df_users)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/users/nonexistent")
        assert response.status_code == 404

    def test_list_users_filter_by_department(self):
        """GET /api/users?department=IT filters correctly."""
        df_users = pd.DataFrame([
            {"user_id": "u_dep1", "username": "dev1", "full_name": "Dev One",
             "role": "developer", "department": "IT",
             "total_events": 5, "unique_actions": 1, "unique_locations": 1},
            {"user_id": "u_dep2", "username": "fin1", "full_name": "Fin One",
             "role": "analyst", "department": "Finance",
             "total_events": 3, "unique_actions": 1, "unique_locations": 1},
        ])
        routes_users.set_data(None, df_users)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/users/?department=IT")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["users"][0]["department"] == "IT"


class TestReportEndpoints:
    """Tests for /api/reports endpoints."""

    def test_generate_report_not_initialized(self):
        """POST /api/reports/generate returns 503 when components not set."""
        routes_reports.set_components(
            detector=None, alert_manager=None, pdf_generator=None, webhook_sender=None
        )
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/reports/generate",
            json={"alert_id": "any"},
        )
        # Returns 503 because alert_manager is None
        assert response.status_code == 503

    def test_generate_report_alert_not_found(self, seeded_alert_manager, mock_report_dir):
        """POST /api/reports/generate returns 404 for unknown alert."""
        mock_pdf_gen = MagicMock(spec=PDFReportGenerator)
        routes_reports.set_components(
            detector=None,
            alert_manager=seeded_alert_manager,
            pdf_generator=mock_pdf_gen,
            webhook_sender=None,
        )
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/reports/generate",
            json={"alert_id": "this_does_not_exist"},
        )
        assert response.status_code == 404

    def test_generate_report_success(self, seeded_alert_manager):
        """POST /api/reports/generate creates report and returns 200."""
        pdf_gen = PDFReportGenerator(author="Test Suite")
        routes_reports.set_components(
            detector=None,
            alert_manager=seeded_alert_manager,
            pdf_generator=pdf_gen,
            webhook_sender=None,
        )
        # Set alerts routes so the GET /api/alerts/ works
        routes_alerts.set_alert_manager(lambda: seeded_alert_manager)
        client = TestClient(app, raise_server_exceptions=False)

        # Get an existing alert ID
        list_resp = client.get("/api/alerts/")
        assert "alerts" in list_resp.json(), "Alert list should contain 'alerts' key"
        alert_id = list_resp.json()["alerts"][0]["alert_id"]

        response = client.post(
            "/api/reports/generate",
            json={"alert_id": alert_id, "include_user_events": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert "report_id" in data
        assert data["alert_id"] == alert_id
        assert "pdf_url" in data

    def test_download_report_not_found(self):
        """GET /api/reports/download/{id} returns 404 for unknown report."""
        routes_reports.set_components(
            detector=None, alert_manager=None, pdf_generator=None, webhook_sender=None
        )
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/reports/download/nonexistent_report_xyz")
        assert response.status_code == 404

    def test_webhook_configure(self):
        """POST /api/webhook/configure sets webhook URL."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            json.dump({"alerts": []}, f)
            temp_path = f.name
        try:
            mgr = AlertManager(storage_path=temp_path)
            routes_reports.set_components(
                detector=None, alert_manager=mgr, pdf_generator=None, webhook_sender=None
            )
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/webhook/configure",
                json={"url": "http://test.local/webhook"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "webhook_url" in data
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
