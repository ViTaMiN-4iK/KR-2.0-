"""Feature engineering для ML-моделей обнаружения аномалий."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, MinMaxScaler


# Категориальные колонки для кодирования
CATEGORICAL_COLS = [
    "action",
    "location_city",
    "location_country",
    "device_type",
    "browser",
    "os",
    "status",
    "department",
    "role",
]

# Числовые колонки для нормализации
NUMERICAL_COLS = [
    "hour",
    "day_of_week",
    "bytes_sent",
    "bytes_received",
    "risk_score",
]

# Колонки для агрегации по пользователю (профиль поведения)
USER_AGG_COLS = {
    "action": ["count", "nunique"],
    "location_city": ["nunique"],
    "bytes_sent": ["mean", "std", "max"],
    "bytes_received": ["mean", "std", "max"],
    "risk_score": ["mean", "max"],
}


class FeatureEngineer:
    """Инженер признаков для UEBA ML-системы."""

    def __init__(self) -> None:
        self._encoders: dict[str, LabelEncoder] = {}
        self._scaler: Optional[MinMaxScaler] = None
        self._fitted: bool = False
        self._user_baseline: Optional[pd.DataFrame] = None

    def fit(self, df: pd.DataFrame) -> "FeatureEngineer":
        """Обучает кодировщики и скейлер на тренировочных данных."""
        if df.empty:
            raise ValueError("Training data cannot be empty")

        # Временные признаки
        df = self._add_temporal_features(df)

        # Кодирование категориальных признаков
        for col in CATEGORICAL_COLS:
            if col in df.columns:
                df[col] = df[col].fillna("unknown")
                encoder = LabelEncoder()
                df[col + "_encoded"] = encoder.fit_transform(df[col].astype(str))
                self._encoders[col] = encoder

        # Скейлинг числовых признаков
        scaler_cols = [c for c in NUMERICAL_COLS if c in df.columns]
        self._scaler = MinMaxScaler()
        self._scaler.fit(df[scaler_cols].fillna(0))

        # Строим базовый профиль пользователя
        self._user_baseline = self._build_user_baseline(df)
        self._fitted = True

        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Применяет трансформации к данным."""
        if not self._fitted:
            raise RuntimeError("FeatureEngineer must be fitted before transform")

        result = df.copy()

        # Временные признаки
        result = self._add_temporal_features(result)

        # Кодирование категориальных признаков
        for col in CATEGORICAL_COLS:
            if col in result.columns:
                result[col] = result[col].fillna("unknown")
                col_name = col + "_encoded"
                if col in self._encoders:
                    known = set(self._encoders[col].classes_)
                    result[col_name] = result[col].apply(
                        lambda x: (
                            self._encoders[col].transform([x])[0]
                            if x in known
                            else -1
                        )
                    )

        # Скейлинг
        scaler_cols = [c for c in NUMERICAL_COLS if c in result.columns]
        if self._scaler and scaler_cols:
            result[[c + "_scaled" for c in scaler_cols]] = self._scaler.transform(
                result[scaler_cols].fillna(0)
            )

        # Признаки отклонения от профиля пользователя
        result = self._add_user_deviation_features(result)

        # Поведенческие признаки
        result = self._add_behavioral_features(result)

        return result

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Обучение и трансформация в одном."""
        return self.fit(df).transform(df)

    def _add_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Добавляет временные признаки."""
        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"], errors="coerce")
            df["hour"] = ts.dt.hour.fillna(12).astype(int)
            df["day_of_week"] = ts.dt.dayofweek.fillna(0).astype(int)
            df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
            df["is_night"] = ((df["hour"] >= 22) | (df["hour"] < 6)).astype(int)
            df["is_work_hours"] = (
                (df["hour"] >= 9) & (df["hour"] < 18) & (df["day_of_week"] < 5)
            ).astype(int)
            df["month"] = ts.dt.month.fillna(1).astype(int)
            df["week_of_year"] = ts.dt.isocalendar().week.fillna(1).astype(int)

        return df

    def _add_behavioral_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Добавляет поведенческие признаки."""
        # Количество уникальных ресурсов за день для каждого пользователя
        if {"user_id", "timestamp"}.issubset(df.columns):
            df = df.copy()
            df["timestamp_date"] = pd.to_datetime(df["timestamp"]).dt.date
            resources_per_day = (
                df.groupby(["user_id", "timestamp_date"])["resource"]
                .nunique()
                .reset_index(name="resources_accessed_today")
            )
            df["timestamp_date"] = pd.to_datetime(df["timestamp"]).dt.date
            df = df.merge(resources_per_day, on=["user_id", "timestamp_date"], how="left")

            # Количество событий за день
            events_per_day = (
                df.groupby(["user_id", "timestamp_date"]).size().reset_index(name="events_today")
            )
            df = df.merge(events_per_day, on=["user_id", "timestamp_date"], how="left")

            # Средний объём данных за день
            bytes_per_day = (
                df.groupby(["user_id", "timestamp_date"])["bytes_sent"]
                .sum()
                .reset_index(name="bytes_sent_today")
            )
            df = df.merge(bytes_per_day, on=["user_id", "timestamp_date"], how="left")

            df.drop(columns=["timestamp_date"], inplace=True)

        # Подозрительные комбинации
        df["suspicious_combo"] = (
            (df.get("is_night", 0) == 1) & (df.get("is_weekend", 0) == 1)
        ).astype(int)

        # Большой объём отправки
        if "bytes_sent" in df.columns:
            df["high_volume_send"] = (df["bytes_sent"] > df["bytes_sent"].quantile(0.95)).astype(int)

        # Много неудачных попыток
        if "status" in df.columns:
            df["is_failed"] = (df["status"] == "failed").astype(int)

        return df

    def _build_user_baseline(self, df: pd.DataFrame) -> pd.DataFrame:
        """Строит базовый профиль нормального поведения каждого пользователя."""
        baseline = (
            df.groupby("user_id")
            .agg({
                "hour": ["mean", "std"],
                "day_of_week": ["mean"],
                "bytes_sent": ["mean", "std"],
                "bytes_received": ["mean", "std"],
                "action": "nunique",
                "location_city": "nunique",
                "resource": "nunique",
            })
        )
        baseline.columns = [
            "baseline_hour_mean",
            "baseline_hour_std",
            "baseline_dow_mean",
            "baseline_bytes_sent_mean",
            "baseline_bytes_sent_std",
            "baseline_bytes_received_mean",
            "baseline_bytes_received_std",
            "baseline_unique_actions",
            "baseline_unique_locations",
            "baseline_unique_resources",
        ]
        return baseline.reset_index()

    def _add_user_deviation_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Добавляет признаки отклонения от типичного профиля пользователя."""
        if self._user_baseline is None:
            return df

        result = df.merge(self._user_baseline, on="user_id", how="left")

        # Отклонение от типичного часа
        result["hour_deviation"] = abs(result["hour"] - result["baseline_hour_mean"])
        result["hour_deviation"] = result["hour_deviation"].fillna(0)

        # Отклонение по объёму данных
        result["bytes_sent_deviation"] = abs(
            result["bytes_sent"] - result["baseline_bytes_sent_mean"]
        )
        result["bytes_sent_deviation"] = result["bytes_sent_deviation"].fillna(0)

        # Нетипичная локация (больше уникальных локаций чем обычно)
        location_count = (
            result.groupby("user_id")["location_city"]
            .transform("nunique")
        )
        result["unusual_location_count"] = (
            location_count.values > result["baseline_unique_locations"].values * 1.5
        ).astype(int)

        return result

    def get_feature_columns(self) -> list[str]:
        """Возвращает список имён признаковых колонок."""
        features: list[str] = []

        for col in CATEGORICAL_COLS:
            encoded = col + "_encoded"
            if encoded in self._encoders or encoded in ():
                features.append(encoded)

        for col in NUMERICAL_COLS:
            scaled = col + "_scaled"
            features.append(scaled)

        features.extend([
            "is_weekend",
            "is_night",
            "is_work_hours",
            "hour_deviation",
            "bytes_sent_deviation",
            "unusual_location_count",
            "suspicious_combo",
            "high_volume_send",
            "is_failed",
            "resources_accessed_today",
            "events_today",
            "bytes_sent_today",
        ])

        return features

    @property
    def is_fitted(self) -> bool:
        return self._fitted
