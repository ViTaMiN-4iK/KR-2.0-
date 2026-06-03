"""Управление алертами: хранение, жизненный цикл, отправка webhook."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from loguru import logger


class AlertStatus(Enum):
    """Статусы алерта."""
    OPEN = "open"
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    RESOLVED = "resolved"


class AlertSeverity(Enum):
    """Уровни серьёзности."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertManager:
    """Менеджер алертов с хранением в JSON-файле и Elasticsearch."""

    def __init__(
        self,
        storage_path: str | Path = "data/alerts.json",
        user_profiles_path: str | Path = "data/user_profiles.json",
        es_client: Optional[Any] = None,
    ) -> None:
        self._storage_path = Path(storage_path)
        self._user_profiles_path = Path(user_profiles_path)
        self._es = es_client
        self._alerts: dict[str, dict[str, Any]] = {}
        self._user_profiles: dict[str, dict[str, Any]] = {}
        self._webhook_url: Optional[str] = None
        self._load_alerts()
        self._load_user_profiles()
        # Seed from alerts after loading, so alerts override file data
        self._seed_user_profiles_from_alerts()

    def _load_alerts(self) -> None:
        """Загружает алерты из файла."""
        if self._storage_path.exists():
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._alerts = {a["alert_id"]: a for a in data.get("alerts", [])}
                logger.info(f"Loaded {len(self._alerts)} alerts from storage")
            except Exception as e:
                logger.warning(f"Failed to load alerts: {e}")
                self._alerts = {}

    def _load_user_profiles(self) -> None:
        """Загружает профили пользователей из файла."""
        if self._user_profiles_path.exists():
            try:
                with open(self._user_profiles_path, "r", encoding="utf-8") as f:
                    self._user_profiles = json.load(f)
                logger.info(f"Loaded {len(self._user_profiles)} user profiles")
            except Exception as e:
                logger.warning(f"Failed to load user profiles: {e}")
                self._user_profiles = {}

    def _seed_user_profiles_from_alerts(self) -> None:
        """Инициализирует профили пользователей из существующих алертов."""
        for alert in self._alerts.values():
            self._update_user_profile_from_alert(
                user_id=alert.get("user_id", ""),
                username=alert.get("username", ""),
                anomaly_score=alert.get("anomaly_score", 0),
                risk_level=alert.get("risk_level", "low"),
                reason=alert.get("reason", ""),
            )

    def _save_user_profiles(self) -> None:
        """Сохраняет профили пользователей в файл."""
        self._user_profiles_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._user_profiles_path, "w", encoding="utf-8") as f:
                json.dump(self._user_profiles, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save user profiles: {e}")

    def _update_user_profile_from_alert(
        self,
        user_id: str,
        username: str,
        anomaly_score: float,
        risk_level: str,
        reason: str,
    ) -> None:
        """Обновляет профиль пользователя на основе нового алерта."""
        profile = self._user_profiles.get(user_id, {
            "user_id": user_id,
            "username": username,
            "alert_count": 0,
            "max_anomaly_score": 0.0,
            "risk_status": "normal",
            "latest_alert_reason": "",
            "open_alert_count": 0,
        })

        profile["user_id"] = user_id
        profile["username"] = username
        profile["alert_count"] = profile.get("alert_count", 0) + 1
        profile["open_alert_count"] = profile.get("open_alert_count", 0) + 1
        profile["latest_alert_reason"] = reason

        if anomaly_score > profile.get("max_anomaly_score", 0):
            profile["max_anomaly_score"] = anomaly_score

        # Определяем общий статус риска
        max_score = profile["max_anomaly_score"]
        if max_score >= 0.7:
            profile["risk_status"] = "compromised"
        elif max_score >= 0.4:
            profile["risk_status"] = "suspicious"
        else:
            profile["risk_status"] = "normal"

        self._user_profiles[user_id] = profile
        self._save_user_profiles()

        # Также обновляем в Elasticsearch
        self._index_user_profile_to_es(profile)

        logger.debug(f"Updated profile for user {user_id}: risk_status={profile['risk_status']}, max_score={max_score:.4f}")

    def _index_user_profile_to_es(self, profile: dict[str, Any]) -> None:
        """Индексирует профиль пользователя в Elasticsearch."""
        if self._es is None:
            return
        try:
            self._es.index(
                index="ueba-users",
                id=profile["user_id"],
                document=profile,
            )
        except Exception as e:
            logger.error(f"Failed to index user profile to ES: {e}")

    def _save_alerts(self) -> None:
        """Сохраняет алерты в файл."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"alerts": list(self._alerts.values()), "updated_at": datetime.now(timezone.utc).isoformat()},
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as e:
            logger.error(f"Failed to save alerts: {e}")

    def _index_to_es(self, alert: dict[str, Any]) -> None:
        """Индексирует алерт в Elasticsearch."""
        if self._es is None:
            return
        try:
            self._es.index(
                index="ueba-alerts",
                id=alert["alert_id"],
                document=alert,
            )
        except Exception as e:
            logger.error(f"Failed to index alert to ES: {e}")

    def add_alert(
        self,
        event_id: str,
        user_id: str,
        username: str,
        timestamp: str,
        anomaly_score: float,
        risk_level: str,
        detected_by_model: str,
        reason: str,
        features: Optional[dict[str, float]] = None,
    ) -> dict[str, Any]:
        """Создаёт новый алерт."""
        alert_id = str(uuid4())

        # Проверяем дубликаты
        for existing in self._alerts.values():
            if existing["event_id"] == event_id and existing["status"] != "resolved":
                logger.debug(f"Alert for event {event_id} already exists")
                return existing

        alert = {
            "alert_id": alert_id,
            "event_id": event_id,
            "user_id": user_id,
            "username": username,
            "timestamp": timestamp,
            "anomaly_score": anomaly_score,
            "risk_level": risk_level,
            "detected_by_model": detected_by_model,
            "reason": reason,
            "features": features or {},
            "status": AlertStatus.OPEN.value,
            "severity": self._map_risk_to_severity(risk_level),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "investigation_notes": "",
            "resolved_by": "",
        }

        self._alerts[alert_id] = alert
        self._save_alerts()
        self._index_to_es(alert)

        # Обновляем профиль пользователя
        self._update_user_profile_from_alert(
            user_id=user_id,
            username=username,
            anomaly_score=anomaly_score,
            risk_level=risk_level,
            reason=reason,
        )

        logger.info(
            f"Alert created: {alert_id} | user={user_id} | "
            f"risk={risk_level} | score={anomaly_score:.3f}"
        )

        return alert

    def _map_risk_to_severity(self, risk_level: str) -> str:
        mapping = {
            "critical": AlertSeverity.CRITICAL.value,
            "high": AlertSeverity.HIGH.value,
            "medium": AlertSeverity.MEDIUM.value,
            "low": AlertSeverity.LOW.value,
        }
        return mapping.get(risk_level, AlertSeverity.MEDIUM.value)

    def get_alert(self, alert_id: str) -> Optional[dict[str, Any]]:
        """Получает алерт по ID."""
        return self._alerts.get(alert_id)

    def get_all_alerts(
        self,
        status: Optional[str] = None,
        risk_level: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Получает список алертов с фильтрацией."""
        results = list(self._alerts.values())

        if status:
            results = [a for a in results if a["status"] == status]
        if risk_level:
            results = [a for a in results if a["risk_level"] == risk_level]
        if user_id:
            results = [a for a in results if a["user_id"] == user_id]

        results.sort(key=lambda a: a["created_at"], reverse=True)
        return results[:limit]

    def update_alert_status(
        self,
        alert_id: str,
        status: str,
        notes: str = "",
        resolved_by: str = "",
    ) -> Optional[dict[str, Any]]:
        """Обновляет статус алерта."""
        if alert_id not in self._alerts:
            return None

        self._alerts[alert_id]["status"] = status
        self._alerts[alert_id]["updated_at"] = datetime.now(timezone.utc).isoformat()

        if notes:
            self._alerts[alert_id]["investigation_notes"] = notes
        if resolved_by:
            self._alerts[alert_id]["resolved_by"] = resolved_by

        self._save_alerts()
        self._index_to_es(self._alerts[alert_id])

        logger.info(f"Alert {alert_id} status updated to '{status}'")
        return self._alerts[alert_id]

    def get_stats(self) -> dict[str, Any]:
        """Возвращает статистику по алертам."""
        alerts = list(self._alerts.values())
        if not alerts:
            return {
                "total": 0,
                "by_status": {},
                "by_risk_level": {},
                "avg_score": 0.0,
            }

        by_status: dict[str, int] = {}
        by_risk: dict[str, int] = {}

        for a in alerts:
            by_status[a["status"]] = by_status.get(a["status"], 0) + 1
            by_risk[a["risk_level"]] = by_risk.get(a["risk_level"], 0) + 1

        return {
            "total": len(alerts),
            "open": by_status.get("open", 0),
            "investigating": by_status.get("investigating", 0),
            "confirmed": by_status.get("confirmed", 0),
            "resolved": by_status.get("resolved", 0),
            "false_positive": by_status.get("false_positive", 0),
            "by_status": by_status,
            "by_risk_level": by_risk,
            "avg_score": sum(a["anomaly_score"] for a in alerts) / len(alerts),
        }

    def set_webhook_url(self, url: str) -> None:
        """Устанавливает URL для webhook-уведомлений."""
        self._webhook_url = url
        logger.info(f"Webhook URL set to: {url}")

    @property
    def webhook_url(self) -> Optional[str]:
        return self._webhook_url

    def get_anomaly_context(self, alert_id: str) -> list[dict[str, str]]:
        """Вычисляет контекст аномалии: факт vs норма по каждому отклонению.

        Берёт исторические события пользователя из ES и считает базовые значения.
        """
        alert = self._alerts.get(alert_id)
        if alert is None or self._es is None:
            return []

        user_id = alert["user_id"]
        features = alert.get("features", {})
        context: list[dict[str, str]] = []

        try:
            resp = self._es.search(
                index="ueba-events",
                body={
                    "query": {"term": {"user_id": user_id}},
                    "size": 1000,
                    "sort": [{"timestamp": "desc"}],
                },
            )
            hits = resp["hits"]["hits"]
            if not hits:
                return []

            records = [h["_source"] for h in hits]
            import pandas as pd
            df = pd.DataFrame(records)
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df["hour"] = df["timestamp"].dt.hour

            def _f(v):
                return float(v) if v is not None else 0.0

            def _flag(name, threshold=0.5):
                return _f(features.get(name, 0)) >= threshold

            # --- Время ---
            if _flag("is_night") or features.get("hour_deviation", 0) > 3:
                event_hour = df.iloc[0]["hour"] if not df.empty else None
                if event_hour is not None and pd.notna(event_hour):
                    actual_str = (
                        f"{int(event_hour):02d}:{int((event_hour % 1) * 60):02d}"
                        f" {'ночи' if event_hour < 6 else 'дня'}"
                    )
                else:
                    actual_str = "н/д"

                mean_hour = df["hour"].mean()
                if pd.notna(mean_hour):
                    baseline_str = f"обычно {int(mean_hour):02d}:00–{(int(mean_hour)+9)%24:02d}:00"
                else:
                    baseline_str = "09:00–18:00 (рабочие часы)"

                deviation = abs(event_hour - mean_hour) if event_hour and pd.notna(event_hour) and pd.notna(mean_hour) else 0
                detail = f"отклонение от типичного времени: {deviation:.1f} ч"

                context.append({
                    "label": "Время активности",
                    "actual": actual_str,
                    "baseline": baseline_str,
                    "detail": detail,
                })

            # --- Выходной день ---
            if _flag("is_weekend"):
                context.append({
                    "label": "День недели",
                    "actual": "выходной день (сб/вс)",
                    "baseline": "рабочий день (пн–пт)",
                    "detail": "активность в нерабочее время",
                })

            # --- Объём данных ---
            if _flag("high_volume_send") or features.get("bytes_sent_deviation", 0) > 3:
                bs = features.get("bytes_sent_deviation", 0)
                bs_actual = features.get("bytes_sent_scaled", 0)
                bs_baseline = features.get("baseline_bytes_sent_mean", 0)

                if df is not None and "bytes_sent" in df.columns:
                    actual_bytes = df.iloc[0]["bytes_sent"] if "bytes_sent" in df.columns and not df.empty else bs_actual
                    baseline_mean = df["bytes_sent"].mean()
                else:
                    actual_bytes = bs_actual
                    baseline_mean = bs_baseline

                actual_str = self._format_bytes(float(actual_bytes) if pd.notna(actual_bytes) else 0)
                baseline_str = f"в среднем {self._format_bytes(float(baseline_mean) if pd.notna(baseline_mean) else 0)}"
                context.append({
                    "label": "Объём данных",
                    "actual": f"отправлено {actual_str}",
                    "baseline": baseline_str,
                    "detail": f"превышение нормы в {bs:.1f}x",
                })

            # --- Локация ---
            if _flag("unusual_location_count"):
                event_city = ""
                if not df.empty and "location_city" in df.columns:
                    event_city = str(df.iloc[0]["location_city"])

                unique_cities = df["location_city"].nunique() if "location_city" in df.columns else 0
                baseline_cities = features.get("baseline_unique_locations", 1)

                actual_str = event_city or "неизвестно"
                baseline_str = f"{int(baseline_cities)} локация(й) обычно"
                context.append({
                    "label": "Геолокация",
                    "actual": f"город: {actual_str}",
                    "baseline": baseline_str,
                    "detail": f"необычное количество уникальных локаций: {unique_cities}",
                })

            # --- Неудачная попытка ---
            if _flag("is_failed"):
                context.append({
                    "label": "Статус действия",
                    "actual": "неудачная попытка (failed)",
                    "baseline": "успешное действие (success)",
                    "detail": "многократные неудачные попытки могут указывать на атаку",
                })

            # --- Подозрительная комбинация ---
            if _flag("suspicious_combo"):
                context.append({
                    "label": "Комбинация факторов",
                    "actual": "ночь + выходной день",
                    "baseline": "рабочее время в будний день",
                    "detail": "критическая комбинация аномальных факторов",
                })

            return context

        except Exception:
            return []

    def get_user_profiles(self) -> dict[str, dict[str, Any]]:
        """Возвращает все профили пользователей с обновлённой статистикой."""
        return self._user_profiles

    def get_user_profile(self, user_id: str) -> Optional[dict[str, Any]]:
        """Получает профиль конкретного пользователя."""
        return self._user_profiles.get(user_id)

    @staticmethod
    def _format_bytes(b: float) -> str:
        """Форматирует байты в читаемый вид."""
        if b >= 1_073_741_824:
            return f"{b / 1_073_741_824:.1f} ГБ"
        if b >= 1_048_576:
            return f"{b / 1_048_576:.1f} МБ"
        if b >= 1024:
            return f"{b / 1024:.1f} КБ"
        return f"{b:.0f} Б"
