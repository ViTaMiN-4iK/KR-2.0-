"""Script to run the full UEBA pipeline: generate data -> train -> detect."""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

from data.generate_logs import generate_dataset
from src.pipeline.data_loader import DataLoader
from src.ml.detector import AnomalyDetector


def main() -> None:
    parser = argparse.ArgumentParser(description="UEBA Pipeline")
    parser.add_argument("--clear", action="store_true", help="Clear previous alerts and user profiles before starting")
    parser.add_argument("--labeled", action="store_true", help="Use ground-truth is_anomaly labels for training/evaluation")
    args = parser.parse_args()

    if args.clear:
        alerts_path = Path("data/alerts.json")
        profiles_path = Path("data/user_profiles.json")
        if alerts_path.exists():
            alerts_path.unlink()
            logger.info("Cleared alerts.json")
        if profiles_path.exists():
            profiles_path.unlink()
            logger.info("Cleared user_profiles.json")

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
    label_col = "is_anomaly" if args.labeled else None
    result = detector.train(events_df, label_column=label_col)
    logger.success(
        f"Best model: {result.best_model_type.value} "
        f"(F1={result.best_metrics.f1:.4f})"
    )

    # Step 4: Detect anomalies
    logger.info("Step 4: Detecting anomalies...")
    try:
        alerts = detector.detect(events_df, risk_threshold=0.0)
        logger.info(f"Detected {len(alerts)} alerts")
    except Exception as e:
        import traceback
        logger.error(f"Detection failed: {e}\n{traceback.format_exc()}")
        alerts = []

    # Step 5: Save alerts
    logger.info("Step 5: Saving alerts...")
    try:
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

        # Flush once after all alerts are added
        manager.flush()
        logger.success(f"Saved {len(alerts)} alerts to data/alerts.json")

        # Send webhook for critical alerts
        for alert in alerts:
            if alert.risk_level in ("critical", "high"):
                webhook.send_alert(alert.to_dict())
    except Exception as e:
        import traceback
        logger.error(f"Saving alerts failed: {e}\n{traceback.format_exc()}")
    logger.success("=== UEBA Pipeline Complete ===")
    logger.info(f"\nTo start the API: uvicorn src.api.main:app --port 8000")
    logger.info(f"To start the web UI: flask --app web.app:app run --port 5000")


if __name__ == "__main__":
    main()
