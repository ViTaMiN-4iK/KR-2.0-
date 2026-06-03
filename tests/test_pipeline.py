"""Tests for the data pipeline."""

from __future__ import annotations

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from src.pipeline.data_loader import DataLoader
from src.pipeline.features import FeatureEngineer


@pytest.fixture
def sample_events() -> pd.DataFrame:
    """Creates sample events DataFrame for testing."""
    data = []
    base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    for i in range(20):
        data.append({
            "event_id": f"evt_{i:04d}",
            "timestamp": (base_time + pd.Timedelta(hours=i)).isoformat(),
            "user_id": f"user_{i % 3}",
            "username": f"user_{i % 3}@company.local",
            "full_name": f"User {i % 3}",
            "role": "developer",
            "department": "IT",
            "action": ["login", "file_read", "db_query"][i % 3],
            "resource": "/srv/data/file.txt",
            "location_city": "Moscow",
            "location_country": "RU",
            "ip_address": f"10.0.{i % 10}.{i}",
            "device_type": "laptop",
            "browser": "Chrome 120",
            "os": "Windows 11",
            "bytes_sent": 1000 + i * 100,
            "bytes_received": 5000 + i * 100,
            "status": "success",
            "risk_score": 0.1 + (i % 5) * 0.1,
        })

    return pd.DataFrame(data)


class TestDataLoader:
    """Tests for DataLoader."""

    def test_load_from_csv_not_found(self):
        """Test that loading from non-existent file raises error."""
        loader = DataLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_from_csv("nonexistent.csv", "users.csv")

    def test_filter_by_timerange(self, sample_events):
        """Test filtering events by time range."""
        loader = DataLoader()
        # Convert timestamps to datetime first
        df = sample_events.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        loader._events_df = df.copy()

        start = datetime(2026, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
        result = loader.filter_by_timerange(df, start=start)

        assert len(result) < len(sample_events)
        assert all(pd.to_datetime(result["timestamp"]) >= pd.Timestamp(start))

    def test_filter_by_users(self, sample_events):
        """Test filtering by user list."""
        loader = DataLoader()
        result = loader.filter_by_users(sample_events, ["user_0", "user_1"])

        assert set(result["user_id"].unique()) == {"user_0", "user_1"}
        assert len(result) > 0

    def test_get_user_profiles(self, sample_events):
        """Test user profile aggregation."""
        loader = DataLoader()
        # Add hour column to match expected schema
        df = sample_events.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["hour"] = df["timestamp"].dt.hour
        profiles = loader.get_user_profiles(df)

        assert len(profiles) == 3
        assert all(col in profiles.columns for col in [
            "user_id", "total_events", "unique_actions"
        ])


class TestFeatureEngineer:
    """Tests for FeatureEngineer."""

    def test_fit_transform_empty(self):
        """Test that fitting on empty data raises error."""
        fe = FeatureEngineer()
        with pytest.raises(ValueError):
            fe.fit(pd.DataFrame())

    def test_temporal_features(self, sample_events):
        """Test that temporal features are added correctly."""
        fe = FeatureEngineer()
        result = fe.fit_transform(sample_events)

        assert "hour" in result.columns
        assert "day_of_week" in result.columns
        assert "is_weekend" in result.columns
        assert "is_night" in result.columns
        assert "is_work_hours" in result.columns

        assert result["hour"].min() >= 0
        assert result["hour"].max() <= 23
        assert set(result["is_weekend"].unique()).issubset({0, 1})

    def test_fit_transform_consistent(self, sample_events):
        """Test that fit_transform produces consistent results."""
        fe = FeatureEngineer()
        result = fe.fit_transform(sample_events)

        assert len(result) == len(sample_events)
        assert fe.is_fitted

    def test_get_feature_columns(self, sample_events):
        """Test feature columns retrieval."""
        fe = FeatureEngineer()
        fe.fit_transform(sample_events)
        cols = fe.get_feature_columns()

        assert isinstance(cols, list)
        assert len(cols) > 0

    def test_categorical_encoding(self, sample_events):
        """Test that categorical columns get encoded."""
        fe = FeatureEngineer()
        result = fe.fit_transform(sample_events)

        assert "action_encoded" in result.columns
        assert "location_city_encoded" in result.columns
