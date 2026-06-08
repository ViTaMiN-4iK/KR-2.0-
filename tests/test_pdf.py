"""Tests for PDF report generation."""

from __future__ import annotations

import os
import pytest
from pathlib import Path

from src.reporting.pdf_generator import PDFReportGenerator, _clean


class TestPDFReportGenerator:
    """Tests for PDFReportGenerator."""

    @pytest.fixture
    def generator(self):
        """Create a PDF generator instance."""
        return PDFReportGenerator(author="Test Suite", logo_text="Test UEBA")

    @pytest.fixture
    def sample_alert(self):
        """Sample alert dict for testing."""
        return {
            "alert_id": "alert_test_001",
            "event_id": "evt_test_001",
            "user_id": "user_test_1",
            "username": "test_user",
            "timestamp": "2026-01-15T02:30:00Z",
            "anomaly_score": 0.92,
            "anomaly_score_normalized": 0.95,
            "risk_level": "high",
            "detected_by_model": "isolation_forest",
            "reason": "Activity detected at nighttime with unusual data volume",
            "status": "open",
            "created_at": "2026-01-15T02:31:00Z",
            "updated_at": "2026-01-15T02:31:00Z",
            "features": {
                "hour": 2.5,
                "is_night": 1.0,
                "is_weekend": 0.0,
                "is_work_hours": 0.0,
                "is_failed": 0.0,
                "high_volume_send": 1.0,
                "bytes_sent_scaled": 8.5,
                "hour_deviation": 6.0,
                "bytes_sent_deviation": 5.0,
                "baseline_unique_locations": 1.0,
                "unique_locations_today": 2.0,
                "suspicious_combo": 0.0,
            },
            "anomaly_context": {
                "items": [
                    {
                        "label": "Activity Time",
                        "actual": "nighttime (after 22:00)",
                        "baseline": "09:00-18:00 (business hours)",
                        "detail": "activity time is outside normal working hours",
                    },
                    {
                        "label": "Data Volume",
                        "actual": "sent 8.5 MB",
                        "baseline": "typical volume for this user",
                        "detail": "sent data volume significantly exceeds normal levels",
                    },
                ]
            },
        }

    @pytest.fixture
    def sample_user(self):
        """Sample user dict for testing."""
        return {
            "user_id": "user_test_1",
            "username": "test_user",
            "role": "developer",
            "department": "IT",
            "total_events": 150,
            "anomaly_score_max": 0.92,
        }

    def test_generate_alert_report(self, generator, sample_alert, tmp_path):
        """Test that PDF alert report is generated successfully."""
        output = tmp_path / "alert_report.pdf"
        result = generator.generate_alert_report(
            alert=sample_alert,
            output_path=str(output),
        )

        assert result == str(output)
        assert output.exists()
        assert output.stat().st_size > 0

    def test_generate_alert_report_no_features(self, generator, tmp_path):
        """Test PDF generation with alert having no features."""
        alert = {
            "alert_id": "alert_nofeatures",
            "event_id": "evt_nof",
            "user_id": "user_nof",
            "username": "nof_user",
            "timestamp": "2026-01-15T10:00:00Z",
            "anomaly_score": 0.5,
            "risk_level": "low",
            "detected_by_model": "dbscan",
            "reason": "Minor deviation",
            "status": "open",
            "created_at": "2026-01-15T10:00:00Z",
            "updated_at": "2026-01-15T10:00:00Z",
        }
        output = tmp_path / "nofeatures_report.pdf"
        result = generator.generate_alert_report(alert=alert, output_path=str(output))

        assert result == str(output)
        assert output.exists()

    def test_generate_alert_report_creates_parent_dirs(self, generator, sample_alert, tmp_path):
        """Test that parent directories are created if they don't exist."""
        nested = tmp_path / "nested" / "dir" / "report.pdf"
        result = generator.generate_alert_report(
            alert=sample_alert,
            output_path=str(nested),
        )
        assert result == str(nested)
        assert nested.exists()

    def test_generate_alert_report_critical_risk(self, generator, sample_alert, tmp_path):
        """Test PDF generation for critical risk alert."""
        sample_alert["risk_level"] = "critical"
        sample_alert["anomaly_score"] = 0.98
        output = tmp_path / "critical_report.pdf"
        result = generator.generate_alert_report(alert=sample_alert, output_path=str(output))
        assert output.exists()

    def test_generate_alert_report_low_risk(self, generator, sample_alert, tmp_path):
        """Test PDF generation for low risk alert."""
        sample_alert["risk_level"] = "low"
        sample_alert["anomaly_score"] = 0.15
        output = tmp_path / "low_report.pdf"
        result = generator.generate_alert_report(alert=sample_alert, output_path=str(output))
        assert output.exists()

    def test_generate_user_report(self, generator, sample_user, tmp_path):
        """Test that PDF user report is generated successfully."""
        output = tmp_path / "user_report.pdf"
        result = generator.generate_user_report(
            user=sample_user,
            events=[],
            output_path=str(output),
        )

        assert result == str(output)
        assert output.exists()
        assert output.stat().st_size > 0

    def test_generate_user_report_creates_parent_dirs(self, generator, sample_user, tmp_path):
        """Test user report creates parent directories."""
        nested = tmp_path / "reports" / "users" / "profile.pdf"
        result = generator.generate_user_report(
            user=sample_user,
            events=[],
            output_path=str(nested),
        )
        assert nested.exists()


class TestRecommendations:
    """Tests for recommendation generation logic."""

    @pytest.fixture
    def generator(self):
        return PDFReportGenerator()

    def test_recommendations_critical_risk(self, generator):
        """Test recommendations for critical risk alert."""
        alert = {"risk_level": "critical", "reason": "nighttime activity"}
        recs = generator._generate_recommendations(alert)
        assert len(recs) >= 3
        assert any("isolate" in r.lower() for r in recs)

    def test_recommendations_high_risk(self, generator):
        """Test recommendations for high risk alert."""
        alert = {"risk_level": "high", "reason": "large data transfer"}
        recs = generator._generate_recommendations(alert)
        assert len(recs) >= 3

    def test_recommendations_medium_risk(self, generator):
        """Test recommendations for medium risk alert."""
        alert = {"risk_level": "medium", "reason": "unusual location"}
        recs = generator._generate_recommendations(alert)
        assert len(recs) >= 2

    def test_recommendations_low_risk(self, generator):
        """Test recommendations for low risk alert."""
        alert = {"risk_level": "low", "reason": "minor deviation"}
        recs = generator._generate_recommendations(alert)
        assert len(recs) >= 1

    def test_recommendations_include_night_context(self, generator):
        """Test that 'night' in reason adds specific recommendation."""
        alert = {"risk_level": "medium", "reason": "nighttime login attempt"}
        recs = generator._generate_recommendations(alert)
        assert any("after-hours" in r.lower() for r in recs)

    def test_recommendations_include_data_context(self, generator):
        """Test that 'data' in reason adds verification recommendation."""
        alert = {"risk_level": "medium", "reason": "large data volume"}
        recs = generator._generate_recommendations(alert)
        assert any("data transfer" in r.lower() or "verify" in r.lower() for r in recs)


class TestCleanFunction:
    """Tests for the _clean helper function."""

    def test_clean_none(self):
        """Test _clean with None input."""
        assert _clean(None) == "n/a"

    def test_clean_ascii(self):
        """Test _clean with plain ASCII text."""
        assert _clean("hello world") == "hello world"

    def test_clean_cyrillic_replaced(self):
        """Test that Cyrillic characters are replaced with ?."""
        result = _clean("Привет мир")
        assert "?" in result
        assert "П" not in result

    def test_clean_mixed_content(self):
        """Test _clean with mixed ASCII and non-ASCII."""
        result = _clean("User: admin, Status: OK")
        assert result == "User: admin, Status: OK"

    def test_clean_empty_string(self):
        """Test _clean with empty string."""
        assert _clean("") == "n/a"

    def test_clean_multiple_non_ascii_collapsed(self):
        """Test that multiple ? are collapsed to single ?."""
        result = _clean("Привет")
        assert result.count("?") <= 1
