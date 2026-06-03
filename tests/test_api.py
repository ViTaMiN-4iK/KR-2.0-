"""Tests for API routes."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

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
