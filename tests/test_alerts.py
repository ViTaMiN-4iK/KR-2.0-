"""Tests for Alert Manager."""

from __future__ import annotations

import pytest
import json
import tempfile
import os
from pathlib import Path

from src.alerts.manager import AlertManager, AlertStatus
from src.alerts.webhook import WebhookSender


@pytest.fixture
def temp_storage():
    """Creates temporary storage for alerts."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = f.name
    yield temp_path
    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def alert_manager(temp_storage):
    """Creates AlertManager with temporary storage."""
    return AlertManager(storage_path=temp_storage)


class TestAlertManager:
    """Tests for AlertManager."""

    def test_add_alert(self, alert_manager):
        """Test creating a new alert."""
        alert = alert_manager.add_alert(
            event_id="evt_001",
            user_id="user_1",
            username="user_1@company.local",
            timestamp="2026-01-15T10:30:00Z",
            anomaly_score=0.85,
            risk_level="high",
            detected_by_model="isolation_forest",
            reason="Unusual login time detected",
            features={"hour": 3.0, "is_night": 1.0},
        )

        assert alert["alert_id"] is not None
        assert alert["event_id"] == "evt_001"
        assert alert["risk_level"] == "high"
        assert alert["status"] == "open"
        assert "alert_id" in alert

    def test_get_alert(self, alert_manager):
        """Test retrieving an alert by ID."""
        created = alert_manager.add_alert(
            event_id="evt_002",
            user_id="user_2",
            username="user_2@company.local",
            timestamp="2026-01-15T11:00:00Z",
            anomaly_score=0.7,
            risk_level="medium",
            detected_by_model="isolation_forest",
            reason="Medium risk event",
        )

        retrieved = alert_manager.get_alert(created["alert_id"])
        assert retrieved is not None
        assert retrieved["event_id"] == "evt_002"

    def test_get_alert_not_found(self, alert_manager):
        """Test retrieving non-existent alert."""
        result = alert_manager.get_alert("nonexistent_id")
        assert result is None

    def test_get_all_alerts_filter(self, alert_manager):
        """Test filtering alerts by status."""
        alert_manager.add_alert(
            event_id="evt_003",
            user_id="user_3",
            username="user_3@company.local",
            timestamp="2026-01-15T12:00:00Z",
            anomaly_score=0.9,
            risk_level="critical",
            detected_by_model="isolation_forest",
            reason="Critical",
        )
        alert_manager.add_alert(
            event_id="evt_004",
            user_id="user_4",
            username="user_4@company.local",
            timestamp="2026-01-15T12:30:00Z",
            anomaly_score=0.5,
            risk_level="medium",
            detected_by_model="isolation_forest",
            reason="Medium",
        )

        all_alerts = alert_manager.get_all_alerts()
        assert len(all_alerts) == 2

        critical = alert_manager.get_all_alerts(risk_level="critical")
        assert len(critical) == 1
        assert critical[0]["event_id"] == "evt_003"

    def test_update_alert_status(self, alert_manager):
        """Test updating alert status."""
        alert = alert_manager.add_alert(
            event_id="evt_005",
            user_id="user_5",
            username="user_5@company.local",
            timestamp="2026-01-15T13:00:00Z",
            anomaly_score=0.6,
            risk_level="medium",
            detected_by_model="isolation_forest",
            reason="Test alert",
        )

        updated = alert_manager.update_alert_status(
            alert_id=alert["alert_id"],
            status="investigating",
            notes="Looking into this",
            resolved_by="analyst_1",
        )

        assert updated is not None
        assert updated["status"] == "investigating"
        assert updated["investigation_notes"] == "Looking into this"

    def test_get_stats(self, alert_manager):
        """Test alert statistics."""
        alert_manager.add_alert(
            event_id="evt_stat_1",
            user_id="user_s1",
            username="user_s1@company.local",
            timestamp="2026-01-15T14:00:00Z",
            anomaly_score=0.8,
            risk_level="high",
            detected_by_model="isolation_forest",
            reason="High risk",
        )

        stats = alert_manager.get_stats()
        assert stats["total"] == 1
        assert stats["open"] == 1
        assert "by_risk_level" in stats

    def test_no_duplicate_alerts(self, alert_manager):
        """Test that duplicate alerts are not created."""
        alert1 = alert_manager.add_alert(
            event_id="evt_dup",
            user_id="user_dup",
            username="user_dup@company.local",
            timestamp="2026-01-15T15:00:00Z",
            anomaly_score=0.7,
            risk_level="medium",
            detected_by_model="isolation_forest",
            reason="First",
        )

        alert2 = alert_manager.add_alert(
            event_id="evt_dup",
            user_id="user_dup",
            username="user_dup@company.local",
            timestamp="2026-01-15T15:00:00Z",
            anomaly_score=0.7,
            risk_level="medium",
            detected_by_model="isolation_forest",
            reason="Duplicate",
        )

        assert alert1["alert_id"] == alert2["alert_id"]


class TestWebhookSender:
    """Tests for WebhookSender."""

    def test_send_no_url(self):
        """Test that sending without URL returns False."""
        sender = WebhookSender()
        result = sender.send_alert({"alert_id": "test"})
        assert result is False

    def test_send_batch_no_url(self):
        """Test batch send without URL."""
        sender = WebhookSender()
        result = sender.send_batch([{"alert_id": "test"}])
        assert result is False

    @property
    def webhook_url(self) -> Optional[str]:
        return self._webhook_url

    def test_webhook_url_setter(self):
        """Test setting webhook URL."""
        sender = WebhookSender()
        sender.set_url("http://example.com/webhook")
        assert sender.webhook_url == "http://example.com/webhook"
