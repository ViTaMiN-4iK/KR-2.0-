"""Детектор аномалий — основной интерфейс для обнаружения аномалий."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from loguru import logger

from src.ml.models import (
    AnomalyModel,
    ModelType,
    ModelResult,
    create_model,
)
from src.ml.trainer import ModelTrainer, TrainingResult, EvaluationMetrics
from src.pipeline.features import FeatureEngineer


@dataclass
class AnomalyAlert:
    """Алерт об обнаруженной аномалии."""
    event_id: str
    user_id: str
    username: str
    timestamp: str
    anomaly_score: float
    anomaly_score_normalized: float  # 0-1
    risk_level: str  # low, medium, high, critical
    detected_by_model: str
    features: dict[str, float]
    reason: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "open"
    alert_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "user_id": self.user_id,
            "username": self.username,
            "timestamp": self.timestamp,
            "anomaly_score": self.anomaly_score,
            "anomaly_score_normalized": self.anomaly_score_normalized,
            "risk_level": self.risk_level,
            "detected_by_model": self.detected_by_model,
            "features": self.features,
            "reason": self.reason,
            "created_at": self.created_at,
            "status": self.status,
        }


class AnomalyDetector:
    """Основной класс обнаружения аномалий в поведении пользователей."""

    RISK_THRESHOLDS = {
        "critical": 0.9,
        "high": 0.7,
        "medium": 0.5,
        "low": 0.0,
    }

    def __init__(
        self,
        contamination: float = 0.1,
        models_to_try: Optional[list[ModelType]] = None,
    ) -> None:
        self._contamination = contamination
        self._feature_engineer = FeatureEngineer()
        self._trainer = ModelTrainer(
            models=models_to_try,
            contamination=contamination,
        )
        self._best_model: Optional[AnomalyModel] = None
        self._training_result: Optional[TrainingResult] = None
        self._is_trained = False
        self._feature_columns: list[str] = []

    def train(
        self,
        df: pd.DataFrame,
        label_column: Optional[str] = None,
        save_path: Optional[str | Path] = None,
    ) -> TrainingResult:
        """Обучает модель на исторических данных.

        Args:
            df: DataFrame с событиями (должен содержать колонку 'timestamp')
            label_column: Необязательная колонка с метками аномалий (1=аномалия)
            save_path: Путь для сохранения результатов

        Returns:
            TrainingResult с лучшей моделью
        """
        logger.info(f"Training anomaly detector on {len(df)} events")

        # Feature engineering
        features_df = self._feature_engineer.fit_transform(df)
        self._feature_columns = self._feature_engineer.get_feature_columns()

        # Выбираем только доступные колонки
        available_features = [c for c in self._feature_columns if c in features_df.columns]
        if not available_features:
            raise ValueError("No feature columns available after transformation")

        X = features_df[available_features].fillna(0).values

        # Метки (если есть)
        y: Optional[np.ndarray] = None
        if label_column and label_column in df.columns:
            y = df[label_column].fillna(0).astype(int).values

        self._training_result = self._trainer.train_and_select(
            X, y, available_features
        )
        self._best_model = self._training_result.best_model
        self._is_trained = True

        if save_path:
            self._training_result.save(save_path)

        logger.success(
            f"Training complete. Best model: "
            f"{self._training_result.best_model_type.value}"
        )

        return self._training_result

    def detect(
        self,
        df: pd.DataFrame,
        risk_threshold: float = 0.5,
    ) -> list[AnomalyAlert]:
        """Обнаруживает аномалии в новых данных.

        Args:
            df: DataFrame с событиями
            risk_threshold: Порог риска (0-1) для создания алертов

        Returns:
            Список AnomalyAlert для обнаруженных аномалий
        """
        if not self._is_trained:
            raise RuntimeError("Detector must be trained before detection")

        # Применяем feature engineering
        features_df = self._feature_engineer.transform(df)

        available_features = [c for c in self._feature_columns if c in features_df.columns]
        X = features_df[available_features].fillna(0).values

        # Предсказание
        result = self._best_model.predict(X)

        alerts: list[AnomalyAlert] = []

        # Оценка степени аномальности через нормализацию scores
        scores = result.scores
        if scores.max() != scores.min():
            scores_normalized = (scores - scores.min()) / (scores.max() - scores.min())
        else:
            scores_normalized = np.zeros(len(scores))

        # Аномалии по модели
        anomaly_indices = np.where(result.anomaly_mask)[0]

        for idx in anomaly_indices:
            score_norm = float(scores_normalized[idx])
            risk_level = self._get_risk_level(score_norm)

            if score_norm < risk_threshold:
                continue

            event = df.iloc[idx]
            alert_reason = self._generate_reason(event, features_df.iloc[idx], score_norm)

            alert = AnomalyAlert(
                event_id=str(event.get("event_id", f"evt_{idx}")),
                user_id=str(event.get("user_id", "unknown")),
                username=str(event.get("username", "")),
                timestamp=str(event.get("timestamp", "")),
                anomaly_score=float(scores[idx]),
                anomaly_score_normalized=score_norm,
                risk_level=risk_level,
                detected_by_model=result.model_type.value,
                features={
                    feat: float(features_df.iloc[idx][feat])
                    for feat in available_features[:10]
                    if feat in features_df.iloc[idx]
                },
                reason=alert_reason,
            )
            alerts.append(alert)

        logger.info(f"Detected {len(alerts)} anomalies (threshold={risk_threshold})")
        return alerts

    def _get_risk_level(self, score_normalized: float) -> str:
        """Определяет уровень риска по нормализованному скору."""
        for level, threshold in sorted(
            self.RISK_THRESHOLDS.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            if score_normalized >= threshold:
                return level
        return "low"

    def _generate_reason(
        self,
        event: pd.Series,
        features: pd.Series,
        score: float,
    ) -> str:
        """Генерирует текстовое описание причины аномалии."""
        reasons = []

        if features.get("is_night", 0) == 1:
            reasons.append("действие в ночное время")
        if features.get("is_weekend", 0) == 1:
            reasons.append("действие в выходной день")
        if features.get("hour_deviation", 0) > 3:
            reasons.append("необычное время активности")
        if features.get("high_volume_send", 0) == 1:
            reasons.append("аномально большой объём отправленных данных")
        if features.get("suspicious_combo", 0) == 1:
            reasons.append("подозрительная комбинация: ночь + выходной")
        if features.get("is_failed", 0) == 1:
            reasons.append("неудачная попытка действия")
        if features.get("bytes_sent_deviation", 0) > features.get(
            "baseline_bytes_sent_std", 0
        ) * 3:
            reasons.append("значительное отклонение от типичного объёма данных")

        action = event.get("action", "")
        if action in ["bulk_download", "data_exfiltration", "unauthorized_access"]:
            reasons.append(f"подозрительное действие: {action}")

        if not reasons:
            reasons.append(f"общий скор аномальности {score:.2f}")

        return "; ".join(reasons)

    def save_model(self, path: str | Path) -> None:
        """Сохраняет состояние детектора в JSON."""
        if self._training_result is None:
            raise RuntimeError("No trained model to save")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "is_trained": self._is_trained,
            "feature_columns": self._feature_columns,
            "contamination": self._contamination,
            "training_result": self._training_result.best_metrics.to_dict(),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Detector state saved to {path}")

    def load_model(self, path: str | Path) -> None:
        """Загружает состояние детектора из JSON."""
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._is_trained = data.get("is_trained", False)
        self._feature_columns = data.get("feature_columns", [])
        self._contamination = data.get("contamination", 0.1)

        logger.info(f"Detector state loaded from {path}")

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    @property
    def training_result(self) -> Optional[TrainingResult]:
        return self._training_result
