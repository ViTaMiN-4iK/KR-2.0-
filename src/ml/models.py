"""ML-модели для обнаружения аномалий в поведении пользователей."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.cluster import DBSCAN
from sklearn.neighbors import LocalOutlierFactor


class ModelType(Enum):
    """Типы поддерживаемых ML-моделей."""
    ISOLATION_FOREST = "isolation_forest"
    ONE_CLASS_SVM = "one_class_svm"
    DBSCAN = "dbscan"
    LOCAL_OUTLIER_FACTOR = "local_outlier_factor"


@dataclass
class ModelConfig:
    """Конфигурация модели."""
    model_type: ModelType
    # Isolation Forest
    contamination: float = 0.1
    n_estimators: int = 100
    max_samples: float = 0.8
    # One-Class SVM
    nu: float = 0.1
    kernel: str = "rbf"
    gamma: str = "scale"
    # DBSCAN
    eps: float = 0.5
    min_samples: int = 5
    # LOF
    n_neighbors: int = 20
    # Общие
    random_state: int = 42
    n_jobs: int = -1


@dataclass
class ModelResult:
    """Результат работы модели."""
    model_type: ModelType
    predictions: np.ndarray
    scores: np.ndarray
    labels: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def anomaly_mask(self) -> np.ndarray:
        """Возвращает маску аномалий (True = аномалия)."""
        return self.predictions == -1

    @property
    def anomaly_count(self) -> int:
        return int(self.anomaly_mask.sum())

    @property
    def anomaly_ratio(self) -> float:
        total = len(self.predictions)
        return self.anomaly_count / total if total > 0 else 0.0


class AnomalyModel:
    """Обёртка над ML-моделью для обнаружения аномалий."""

    def __init__(self, config: ModelConfig) -> None:
        self._config = config
        self._model = self._build_model()
        self._is_fitted = False

    def _build_model(self) -> Any:
        """Создаёт экземпляр модели согласно конфигурации."""
        cfg = self._config

        if cfg.model_type == ModelType.ISOLATION_FOREST:
            return IsolationForest(
                contamination=cfg.contamination,
                n_estimators=cfg.n_estimators,
                max_samples=cfg.max_samples,
                random_state=cfg.random_state,
                n_jobs=cfg.n_jobs,
            )

        elif cfg.model_type == ModelType.ONE_CLASS_SVM:
            return OneClassSVM(
                nu=cfg.nu,
                kernel=cfg.kernel,
                gamma=cfg.gamma,
            )

        elif cfg.model_type == ModelType.DBSCAN:
            return DBSCAN(
                eps=cfg.eps,
                min_samples=cfg.min_samples,
                n_jobs=cfg.n_jobs,
            )

        elif cfg.model_type == ModelType.LOCAL_OUTLIER_FACTOR:
            return LocalOutlierFactor(
                n_neighbors=cfg.n_neighbors,
                contamination=cfg.contamination,
                novelty=True,
                n_jobs=cfg.n_jobs,
            )

        raise ValueError(f"Unknown model type: {cfg.model_type}")

    def fit(self, X: np.ndarray) -> "AnomalyModel":
        """Обучает модель на нормальных данных."""
        try:
            if self._config.model_type == ModelType.LOCAL_OUTLIER_FACTOR:
                # LOF с novelty=True обучается на нормальных данных
                self._model.fit(X)
            else:
                self._model.fit(X)
            self._is_fitted = True
        except Exception as e:
            raise RuntimeError(f"Model fitting failed: {e}") from e

        return self

    def predict(self, X: np.ndarray) -> ModelResult:
        """Предсказывает аномалии на новых данных."""
        if not self._is_fitted:
            raise RuntimeError("Model must be fitted before prediction")

        cfg = self._config

        if cfg.model_type == ModelType.ISOLATION_FOREST:
            predictions = self._model.predict(X)
            scores = self._model.score_samples(X)
            labels = self._model.labels_ if hasattr(self._model, "labels_") else np.zeros(len(X))

        elif cfg.model_type == ModelType.ONE_CLASS_SVM:
            predictions = self._model.predict(X)
            scores = self._model.decision_function(X)
            labels = np.zeros(len(X))

        elif cfg.model_type == ModelType.DBSCAN:
            predictions = self._model.labels_
            # DBSCAN: -1 = шум (аномалия)
            predictions = np.where(predictions == -1, -1, 1)
            scores = np.zeros(len(X))
            labels = self._model.labels_

        elif cfg.model_type == ModelType.LOCAL_OUTLIER_FACTOR:
            predictions = self._model.predict(X)
            scores = self._model.decision_function(X)
            labels = np.zeros(len(X))

        else:
            raise ValueError(f"Unknown model type: {cfg.model_type}")

        metadata = {
            "model_name": cfg.model_type.value,
            "config": {
                "contamination": cfg.contamination,
                "n_estimators": cfg.n_estimators,
                "eps": cfg.eps,
                "min_samples": cfg.min_samples,
            },
        }

        return ModelResult(
            model_type=cfg.model_type,
            predictions=predictions,
            scores=scores,
            labels=labels,
            metadata=metadata,
        )

    def get_feature_importance_if(self) -> Optional[np.ndarray]:
        """Возвращает важность признаков для Isolation Forest."""
        if self._config.model_type == ModelType.ISOLATION_FOREST:
            if hasattr(self._model, "feature_importances_"):
                return self._model.feature_importances_
        return None


def create_model(model_type: ModelType, **kwargs) -> AnomalyModel:
    """Фабричная функция для создания модели."""
    defaults: dict[ModelType, dict[str, Any]] = {
        ModelType.ISOLATION_FOREST: {
            "contamination": 0.1,
            "n_estimators": 100,
            "max_samples": 0.8,
        },
        ModelType.ONE_CLASS_SVM: {
            "nu": 0.1,
            "kernel": "rbf",
            "gamma": "scale",
        },
        ModelType.DBSCAN: {
            "eps": 0.5,
            "min_samples": 5,
        },
        ModelType.LOCAL_OUTLIER_FACTOR: {
            "n_neighbors": 20,
            "contamination": 0.1,
        },
    }

    config_defaults = defaults.get(model_type, {})
    config_defaults.update(kwargs)

    config = ModelConfig(model_type=model_type, **config_defaults)
    return AnomalyModel(config)
