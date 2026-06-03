"""API-роуты для генерации отчётов и тренировки моделей."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.api.schemas import (
    TrainRequest,
    TrainResponse,
    ModelEvaluationResponse,
    ReportRequest,
    ReportResponse,
    WebhookConfig,
    WebhookTestResponse,
)
from src.api.routes.alerts import _ctx_from_features


router = APIRouter(tags=["reports"])

_detector = None
_alert_manager = None
_pdf_generator = None
_webhook_sender = None


def set_components(
    detector=None,
    alert_manager=None,
    pdf_generator=None,
    webhook_sender=None,
) -> None:
    global _detector, _alert_manager, _pdf_generator, _webhook_sender
    _detector = detector
    _alert_manager = alert_manager
    _pdf_generator = pdf_generator
    _webhook_sender = webhook_sender


@router.post("/train", response_model=TrainResponse)
def train_model(request: TrainRequest) -> TrainResponse:
    """Запускает тренировку ML-модели на данных."""
    global _detector

    if _detector is None:
        raise HTTPException(status_code=503, detail="Detector not initialized")

    import pandas as pd
    from src.pipeline.data_loader import DataLoader

    # Загружаем данные
    loader = DataLoader()
    events_file = request.events_file or "data/events.csv"
    users_file = "data/users.csv"

    if not Path(events_file).exists():
        raise HTTPException(status_code=400, detail=f"Events file not found: {events_file}")

    df, _ = loader.load_from_csv(events_file, users_file)
    # Use sample for faster training (keep full data for detection)
    sample_size = min(5000, len(df))
    df_sample = df.sample(n=sample_size, random_state=42) if len(df) > sample_size else df

    start_time = time.time()

    # Тренируем на выборке для скорости
    result = _detector.train(df_sample, label_column=request.label_column)

    # Обнаруживаем аномалии на полных данных и сохраняем алерты
    alerts = _detector.detect(df, risk_threshold=0.5)
    if _alert_manager is not None:
        for alert in alerts:
            _alert_manager.add_alert(
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

    elapsed = time.time() - start_time

    metrics = result.best_metrics

    return TrainResponse(
        status="trained",
        best_model=result.best_model_type.value,
        f1_score=metrics.f1,
        precision=metrics.precision,
        recall=metrics.recall,
        accuracy=metrics.accuracy,
        anomaly_count=metrics.anomaly_count,
        total_count=metrics.total_count,
        training_time_seconds=round(elapsed, 2),
    )


@router.get("/models/evaluation", response_model=ModelEvaluationResponse)
def get_model_evaluation() -> ModelEvaluationResponse:
    """Получить сравнительную оценку всех моделей."""
    if _detector is None or _detector.training_result is None:
        raise HTTPException(status_code=503, detail="Models not trained yet")

    results = {}
    for model_type, metrics in _detector.training_result.all_results.items():
        results[model_type.value] = metrics.to_dict()

    return ModelEvaluationResponse(models=results)


@router.post("/reports/generate", response_model=ReportResponse)
def generate_report(request: ReportRequest) -> ReportResponse:
    """Генерирует PDF-отчёт по алерту."""
    global _alert_manager, _pdf_generator

    if _alert_manager is None:
        raise HTTPException(status_code=503, detail="Alert manager not initialized")
    if _pdf_generator is None:
        raise HTTPException(status_code=503, detail="PDF generator not available")

    alert = _alert_manager.get_alert(request.alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert["anomaly_context"] = {"items": _ctx_from_features(alert)}

    from datetime import datetime, timezone
    import uuid

    report_id = str(uuid.uuid4())
    pdf_path = Path("data/reports") / f"{report_id}.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    _pdf_generator.generate_alert_report(
        alert=alert,
        output_path=str(pdf_path),
        include_user_events=request.include_user_events,
        include_comparison=request.include_comparison,
    )

    return ReportResponse(
        report_id=report_id,
        alert_id=request.alert_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        pdf_url=f"/api/reports/download/{report_id}",
    )


@router.get("/reports/download/{report_id}")
def download_report(report_id: str) -> FileResponse:
    """Скачать сгенерированный PDF-отчёт."""
    pdf_path = Path("data/reports") / f"{report_id}.pdf"

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    return FileResponse(
        path=str(pdf_path),
        filename=f"ueba_report_{report_id}.pdf",
        media_type="application/pdf",
    )


@router.post("/webhook/configure")
def configure_webhook(config: WebhookConfig) -> dict[str, str]:
    """Настроить webhook-уведомления."""
    global _alert_manager, _webhook_sender

    if _alert_manager is None:
        raise HTTPException(status_code=503, detail="Alert manager not initialized")

    _alert_manager.set_webhook_url(config.url)

    if _webhook_sender is not None:
        _webhook_sender.set_url(config.url)

    return {"status": "ok", "webhook_url": config.url}


@router.post("/webhook/test", response_model=WebhookTestResponse)
def test_webhook() -> WebhookTestResponse:
    """Проверить подключение к webhook."""
    global _webhook_sender

    if _webhook_sender is None:
        return WebhookTestResponse(success=False, message="Webhook sender not initialized")

    success, message = _webhook_sender.test_webhook()
    return WebhookTestResponse(success=success, message=message)
