"""Отправка webhook-уведомлений об аномалиях."""

from __future__ import annotations

from typing import Any, Optional

import httpx
from loguru import logger


class WebhookSender:
    """Отправитель webhook-уведомлений."""

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        timeout: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        self._webhook_url = webhook_url
        self._timeout = timeout
        self._max_retries = max_retries

    def set_url(self, url: str) -> None:
        """Устанавливает URL веб-сервиса."""
        self._webhook_url = url
        logger.info(f"Webhook URL updated: {url}")

    @property
    def webhook_url(self) -> Optional[str]:
        """Возвращает текущий URL webhook."""
        return self._webhook_url

    def send_alert(self, alert: dict[str, Any]) -> bool:
        """Sends an alert notification."""
        if not self._webhook_url:
            return False

        payload = {
            "type": "ueba_alert",
            "alert": {
                "alert_id": alert.get("alert_id", ""),
                "user_id": alert.get("user_id", ""),
                "username": alert.get("username", ""),
                "risk_level": alert.get("risk_level", ""),
                "severity": alert.get("severity", ""),
                "anomaly_score": alert.get("anomaly_score", 0.0),
                "reason": alert.get("reason", ""),
                "timestamp": alert.get("timestamp", ""),
                "detected_by_model": alert.get("detected_by_model", ""),
            },
            "action_required": alert.get("risk_level") in ("high", "critical"),
        }

        return self._send(payload)

    def send_batch(self, alerts: list[dict[str, Any]]) -> bool:
        """Отправляет несколько алертов одной пачкой."""
        if not self._webhook_url:
            return False

        payload = {
            "type": "ueba_alert_batch",
            "count": len(alerts),
            "alerts": [
                {
                    "alert_id": a.get("alert_id", ""),
                    "user_id": a.get("user_id", ""),
                    "risk_level": a.get("risk_level", ""),
                    "anomaly_score": a.get("anomaly_score", 0.0),
                    "reason": a.get("reason", ""),
                }
                for a in alerts
            ],
        }

        return self._send(payload)

    def _send(self, payload: dict[str, Any]) -> bool:
        """Выполняет HTTP POST запрос с повторными попытками."""
        for attempt in range(self._max_retries):
            try:
                response = httpx.post(
                    self._webhook_url,
                    json=payload,
                    timeout=self._timeout,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code in (200, 201, 202):
                    logger.info(
                        f"Webhook sent successfully: "
                        f"{payload.get('type', 'unknown')}"
                    )
                    return True

                logger.warning(
                    f"Webhook returned {response.status_code} "
                    f"(attempt {attempt + 1}/{self._max_retries})"
                )

            except httpx.TimeoutException:
                logger.warning(
                    f"Webhook timeout (attempt {attempt + 1}/{self._max_retries})"
                )
            except httpx.RequestError as e:
                logger.warning(
                    f"Webhook request error: {e} "
                    f"(attempt {attempt + 1}/{self._max_retries})"
                )

        logger.error(f"Webhook failed after {self._max_retries} attempts")
        return False

    def test_webhook(self) -> tuple[bool, str]:
        """Тестирует webhook-подключение."""
        if not self._webhook_url:
            return False, "Webhook URL not configured"

        payload = {
            "type": "ueba_webhook_test",
            "message": "UEBA system webhook test",
        }

        try:
            response = httpx.post(
                self._webhook_url,
                json=payload,
                timeout=5.0,
            )

            if response.status_code in (200, 201, 202):
                return True, f"Webhook OK (status {response.status_code})"
            return False, f"Webhook returned {response.status_code}"

        except httpx.TimeoutException:
            return False, "Webhook timeout"
        except httpx.RequestError as e:
            return False, f"Webhook error: {e}"
