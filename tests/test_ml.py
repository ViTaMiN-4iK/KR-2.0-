"""Tests for ML models and anomaly detection."""

from __future__ import annotations

import pytest
import numpy as np
import pandas as pd

from src.ml.models import (
    AnomalyModel,
    ModelType,
    ModelConfig,
    create_model,
)
from src.ml.detector import AnomalyDetector, AnomalyAlert
from src.pipeline.features import FeatureEngineer


@pytest.fixture
def sample_features() -> np.ndarray:
    """Creates sample feature matrix for testing."""
    np.random.seed(42)
    normal = np.random.randn(100, 5) * 0.5 + [10, 20, 30, 40, 50]
    anomalies = np.random.randn(10, 5) * 3 + [20, 40, 60, 80, 100]
    X = np.vstack([normal, anomalies])
    return X.astype(np.float64)


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Creates sample DataFrame for testing."""
    np.random.seed(42)
    data = {
        "event_id": [f"evt_{i}" for i in range(50)],
        "user_id": [f"user_{i % 5}" for i in range(50)],
        "username": [f"user_{i % 5}@test.local" for i in range(50)],
        "timestamp": pd.date_range("2026-01-01", periods=50, freq="h").astype(str).tolist(),
        "action": np.random.choice(["login", "file_read", "db_query"], 50),
        "resource": [f"/resource/{i % 10}" for i in range(50)],
        "location_city": np.random.choice(["Moscow", "SPB", "London"], 50),
        "location_country": np.random.choice(["RU", "UK"], 50),
        "device_type": np.random.choice(["laptop", "desktop"], 50),
        "browser": np.random.choice(["Chrome", "Firefox"], 50),
        "os": np.random.choice(["Windows", "Linux"], 50),
        "status": np.random.choice(["success", "failed"], 50),
        "department": np.random.choice(["IT", "Finance"], 50),
        "role": np.random.choice(["developer", "analyst"], 50),
        "bytes_sent": np.random.randint(100, 10000, 50),
        "bytes_received": np.random.randint(100, 50000, 50),
        "risk_score": np.random.uniform(0, 1, 50),
    }
    return pd.DataFrame(data)


class TestAnomalyModels:
    """Tests for anomaly detection models."""

    def test_isolation_forest_fit_predict(self, sample_features):
        """Test Isolation Forest fit and predict."""
        model = create_model(ModelType.ISOLATION_FOREST, contamination=0.1)
        model.fit(sample_features)
        result = model.predict(sample_features)

        assert len(result.predictions) == len(sample_features)
        assert result.anomaly_count >= 0
        assert 0 <= result.anomaly_ratio <= 1

    def test_dbscan_fit_predict(self, sample_features):
        """Test DBSCAN fit and predict."""
        model = create_model(ModelType.DBSCAN, eps=2.0, min_samples=3)
        model.fit(sample_features)
        result = model.predict(sample_features)

        assert len(result.predictions) == len(sample_features)

    def test_local_outlier_factor(self, sample_features):
        """Test LOF model."""
        model = create_model(
            ModelType.LOCAL_OUTLIER_FACTOR,
            n_neighbors=10,
            contamination=0.1,
        )
        model.fit(sample_features)
        result = model.predict(sample_features)

        assert len(result.predictions) == len(sample_features)


class TestAnomalyDetector:
    """Tests for the main AnomalyDetector class."""

    def test_detector_train(self, sample_df):
        """Test that detector trains successfully."""
        detector = AnomalyDetector(contamination=0.1)
        result = detector.train(sample_df)

        assert detector.is_trained
        assert result is not None
        assert result.best_model_type in [
            ModelType.ISOLATION_FOREST,
            ModelType.ONE_CLASS_SVM,
            ModelType.DBSCAN,
            ModelType.LOCAL_OUTLIER_FACTOR,
        ]

    def test_detector_detect_untrained(self, sample_df):
        """Test that detection without training raises error."""
        detector = AnomalyDetector()
        with pytest.raises(RuntimeError):
            detector.detect(sample_df)

    def test_detector_detect(self, sample_df):
        """Test detection produces alerts."""
        detector = AnomalyDetector(contamination=0.15)
        detector.train(sample_df)

        alerts = detector.detect(sample_df, risk_threshold=0.0)

        assert isinstance(alerts, list)

    def test_risk_level_mapping(self, sample_df):
        """Test risk level calculation."""
        detector = AnomalyDetector()

        assert detector._get_risk_level(0.95) == "critical"
        assert detector._get_risk_level(0.8) == "high"
        assert detector._get_risk_level(0.6) == "medium"
        assert detector._get_risk_level(0.3) == "low"

    def test_alert_to_dict(self):
        """Test AnomalyAlert serialization."""
        alert = AnomalyAlert(
            event_id="evt_001",
            user_id="user_1",
            username="user_1@test",
            timestamp="2026-01-01T10:00:00Z",
            anomaly_score=0.85,
            anomaly_score_normalized=0.9,
            risk_level="high",
            detected_by_model="isolation_forest",
            features={"hour": 3.0, "is_night": 1.0},
            reason="Action at unusual time",
        )

        data = alert.to_dict()

        assert data["event_id"] == "evt_001"
        assert data["risk_level"] == "high"
        assert data["anomaly_score"] == 0.85
        assert "hour" in data["features"]
