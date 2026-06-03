"""Тренер ML-моделей с автоматическим выбором лучшей модели."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
    accuracy_score,
    confusion_matrix,
)

from src.ml.models import (
    AnomalyModel,
    ModelType,
    ModelConfig,
    ModelResult,
    create_model,
)


@dataclass
class EvaluationMetrics:
    """Метрики оценки модели."""
    accuracy: float
    precision: float
    recall: float
    f1: float
    confusion_matrix: list[list[int]]
    anomaly_count: int
    total_count: int
    anomaly_ratio: float
    model_type: str
    model_config: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "confusion_matrix": self.confusion_matrix,
            "anomaly_count": self.anomaly_count,
            "total_count": self.total_count,
            "anomaly_ratio": self.anomaly_ratio,
            "model_type": self.model_type,
            "model_config": self.model_config,
            "metadata": self.metadata,
        }

    def __str__(self) -> str:
        return (
            f"[{self.model_type}] "
            f"F1={self.f1:.4f} | Prec={self.precision:.4f} | "
            f"Rec={self.recall:.4f} | Acc={self.accuracy:.4f} | "
            f"Anomalies={self.anomaly_count}/{self.total_count}"
        )


@dataclass
class TrainingResult:
    """Результат тренировки с автоматическим выбором лучшей модели."""
    best_model: AnomalyModel
    best_metrics: EvaluationMetrics
    all_results: dict[ModelType, EvaluationMetrics]
    best_model_type: ModelType
    feature_columns: list[str]

    def save(self, path: str | Path) -> None:
        """Сохраняет результаты тренировки в JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "best_model_type": self.best_model_type.value,
            "best_metrics": self.best_metrics.to_dict(),
            "feature_columns": self.feature_columns,
            "all_results": {
                k.value: v.to_dict() for k, v in self.all_results.items()
            },
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Training results saved to {path}")


class ModelTrainer:
    """Тренер с автоматическим выбором лучшей модели."""

    def __init__(
        self,
        models: Optional[list[ModelType]] = None,
        scoring_metric: str = "f1",
        contamination: float = 0.1,
    ) -> None:
        if models is None:
            models = [
                ModelType.ISOLATION_FOREST,
                ModelType.ONE_CLASS_SVM,
                ModelType.DBSCAN,
                ModelType.LOCAL_OUTLIER_FACTOR,
            ]

        self._models = models
        self._scoring_metric = scoring_metric
        self._contamination = contamination
        self._feature_columns: list[str] = []
        self._best_model: Optional[AnomalyModel] = None
        self._best_metrics: Optional[EvaluationMetrics] = None
        self._all_results: dict[ModelType, EvaluationMetrics] = {}

    def train_and_select(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        feature_columns: list[str],
    ) -> TrainingResult:
        """Обучает все модели и выбирает лучшую.

        Args:
            X_train: Обучающая выборка
            y_train: Метки (0 = нормальное, 1 = аномалия)
            feature_columns: Список имён признаков

        Returns:
            TrainingResult с лучшей моделью и всеми результатами
        """
        self._feature_columns = feature_columns
        logger.info(f"Training {len(self._models)} models on {X_train.shape[0]} samples")

        best_score = -1.0
        best_model_type: Optional[ModelType] = None
        best_model: Optional[AnomalyModel] = None
        best_metrics: Optional[EvaluationMetrics] = None
        all_results: dict[ModelType, EvaluationMetrics] = {}

        for model_type in self._models:
            try:
                result = self._train_single_model(
                    model_type, X_train, y_train
                )
                all_results[model_type] = result

                score = self._get_score(result)
                logger.info(f"  {result}")

                if score > best_score:
                    best_score = score
                    best_model_type = model_type
                    best_model = create_model(
                        model_type,
                        contamination=self._contamination,
                    )
                    best_model._is_fitted = True
                    best_model._model = all_results[model_type].metadata.get(
                        "trained_model"
                    )
                    best_metrics = result

            except Exception as e:
                logger.warning(f"  Model {model_type.value} failed: {e}")
                continue

        if best_model is None or best_metrics is None:
            raise RuntimeError("All models failed to train")

        self._best_model = best_model
        self._best_metrics = best_metrics
        self._all_results = all_results

        logger.success(
            f"Best model: {best_model_type.value} "
            f"(score={best_score:.4f})"
        )

        return TrainingResult(
            best_model=best_model,
            best_metrics=best_metrics,
            all_results=all_results,
            best_model_type=best_model_type or ModelType.ISOLATION_FOREST,
            feature_columns=feature_columns,
        )

    def _train_single_model(
        self,
        model_type: ModelType,
        X: np.ndarray,
        y: np.ndarray,
    ) -> EvaluationMetrics:
        """Обучает одну модель и возвращает метрики."""
        model = create_model(
            model_type,
            contamination=self._contamination,
        )

        # Для обучения используем только "нормальные" данные
        # (y == 0), если есть размеченные данные
        has_labels = y is not None and len(np.unique(y)) > 1

        if has_labels and model_type not in (
            ModelType.ONE_CLASS_SVM,
            ModelType.LOCAL_OUTLIER_FACTOR,
        ):
            normal_mask = y == 0
            X_normal = X[normal_mask]
            model.fit(X_normal)
            predictions_raw = model.predict(X)

        elif model_type == ModelType.LOCAL_OUTLIER_FACTOR:
            if has_labels:
                normal_mask = y == 0
                X_normal = X[normal_mask]
                model.fit(X_normal)
                predictions_raw = model.predict(X)
            else:
                model.fit(X)
                result = model.predict(X)
                predictions_raw = result.predictions

        else:
            model.fit(X)
            predictions_raw = model.predict(X)

        # Формируем бинарные предсказания
        predictions = (predictions_raw == -1).astype(int)
        true_labels = predictions  # для unsupervised по умолчанию

        # Если есть истинные метки — используем их
        if has_labels:
            true_labels = y

        accuracy = accuracy_score(true_labels, predictions)
        precision = precision_score(true_labels, predictions, zero_division=0)
        recall = recall_score(true_labels, predictions, zero_division=0)
        f1 = f1_score(true_labels, predictions, zero_division=0)
        cm = confusion_matrix(true_labels, predictions).tolist()

        # Для unsupervised — помечаем как предсказания модели
        model_result = ModelResult(
            model_type=model_type,
            predictions=predictions_raw,
            scores=np.zeros(len(predictions_raw)),
            labels=np.zeros(len(predictions_raw)),
            metadata={
                "trained_model": model._model,
            },
        )

        config_dict = {
            "contamination": self._contamination,
            "model_type": model_type.value,
        }

        return EvaluationMetrics(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
            confusion_matrix=cm,
            anomaly_count=int(model_result.anomaly_count),
            total_count=len(predictions),
            anomaly_ratio=model_result.anomaly_ratio,
            model_type=model_type.value,
            model_config=config_dict,
            metadata=model_result.metadata,
        )

    def _get_score(self, metrics: EvaluationMetrics) -> float:
        """Возвращает значение метрики для сравнения моделей."""
        if self._scoring_metric == "f1":
            return metrics.f1
        elif self._scoring_metric == "precision":
            return metrics.precision
        elif self._scoring_metric == "recall":
            return metrics.recall
        elif self._scoring_metric == "accuracy":
            return metrics.accuracy
        return metrics.f1

    @property
    def best_model(self) -> Optional[AnomalyModel]:
        return self._best_model

    @property
    def best_metrics(self) -> Optional[EvaluationMetrics]:
        return self._best_metrics

    @property
    def all_results(self) -> dict[ModelType, EvaluationMetrics]:
        return self._all_results
