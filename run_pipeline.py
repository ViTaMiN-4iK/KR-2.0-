#!/usr/bin/env python3
"""Script to run the full UEBA pipeline: generate data -> train -> detect."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
import pandas as pd

from data.generate_logs import generate_dataset
from src.pipeline.data_loader import DataLoader
from src.ml.detector import AnomalyDetector


def main() -> None:
    logger.info("=== UEBA Pipeline Start ===")

    # Step 1: Generate data
    logger.info("Step 1: Generating synthetic data...")
    events_path, users_path = generate_dataset(output_dir="data")
    logger.success("Data generated")

    # Step 2: Load data
    logger.info("Step 2: Loading data...")
    loader = DataLoader()
    events_df, users_df = loader.load_from_csv(events_path, users_path)
    logger.success(f"Loaded {len(events_df)} events, {len(users_df)} users")

    # Step 3: Train ML model
    logger.info("Step 3: Training ML models...")
    detector = AnomalyDetector(contamination=0.1)
    result = detector.train(events_df)
    logger.success(
        f"Best model: {result.best_model_type.value} "
        f"(F1={result.best_metrics.f1:.4f})"
    )

    # Step 4: Detect anomalies
    logger.info("Step 4: Detecting anomalies...")
    alerts = detector.detect(events_df, risk_threshold=0.5)
    logger.info(f"Detected {len(alerts)} alerts")

    # Step 5: Save alerts
    logger.info("Step 5: Saving alerts...")
    from src.alerts.manager import AlertManager
    from src.alerts.webhook import WebhookSender

    manager = AlertManager(storage_path="data/alerts.json")
    webhook = WebhookSender()

    for alert in alerts:
        manager.add_alert(
            event_id=alert.event_id,
            user_id=alert.user_id,
            username=alert.username,
            timestamp=alert.timestamp,
            anomaly_score=alert.anomaly_score_normalized,
            risk_level=alert.risk_level,
            detected_by_model=alert.detected_by_model,
            reason=alert.reason,
            features=alert.features,
        )

    # Send webhook for critical alerts
    for alert in alerts:
        if alert.risk_level in ("critical", "high"):
            webhook.send_alert(alert.to_dict())

    logger.success(f"Saved {len(alerts)} alerts to data/alerts.json")
    logger.success("=== UEBA Pipeline Complete ===")
    logger.info(f"\nTo start the API: uvicorn src.api.main:app --port 8000")
    logger.info(f"To start the web UI: flask --app web.app:app run --port 5000")


if __name__ == "__main__":
    main()
