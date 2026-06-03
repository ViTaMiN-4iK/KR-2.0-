"""API-роуты для работы с алертами."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import (
    AlertResponse,
    AlertUpdate,
    AlertListResponse,
    AlertStatsResponse,
    AlertStatus,
    AnomalyContext,
)



router = APIRouter(prefix="/alerts", tags=["alerts"])

# Lazy singleton - обновляется из main.py
_alert_manager_getter: Optional[callable] = None


def set_alert_manager(getter: callable) -> None:
    """Регистрирует getter для lazy-доступа к менеджеру."""
    global _alert_manager_getter
    _alert_manager_getter = getter


def _get_alert_manager():
    """Lazy-доступ к менеджеру алертов."""
    if _alert_manager_getter is None:
        raise HTTPException(status_code=503, detail="Alert manager not initialized")
    return _alert_manager_getter()


@router.get("/", response_model=AlertListResponse)
def list_alerts(
    status: Annotated[str | None, Query(description="Фильтр по статусу")] = None,
    risk_level: Annotated[str | None, Query(description="Фильтр по уровню риска")] = None,
    user_id: Annotated[str | None, Query(description="Фильтр по пользователю")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AlertListResponse:
    """Получить список алертов с фильтрацией и пагинацией."""
    manager = _get_alert_manager()

    all_alerts = manager.get_all_alerts(
        status=status,
        risk_level=risk_level,
        user_id=user_id,
        limit=1000,
    )

    total = len(all_alerts)
    start = (page - 1) * page_size
    end = start + page_size
    page_alerts = all_alerts[start:end]

    return AlertListResponse(
        total=total,
        alerts=[AlertResponse(**a) for a in page_alerts],
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=AlertStatsResponse)
def get_alert_stats() -> AlertStatsResponse:
    """Получить статистику по алертам."""
    manager = _get_alert_manager()
    stats = manager.get_stats()
    return AlertStatsResponse(**stats)


@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(alert_id: str) -> AlertResponse:
    """Получить детали одного алерта."""
    manager = _get_alert_manager()
    alert = manager.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Контекст аномалии из stored features
    alert["anomaly_context"] = {"items": _ctx_from_features(alert)}

    return AlertResponse(**alert)


def _ctx_from_features(alert: dict[str, Any]) -> list[dict[str, str]]:
    """Вычисляет контекст аномалии из stored features алерта."""
    features = alert.get("features", {})
    context: list[dict[str, str]] = []

    def _f(v):
        return float(v) if v is not None else 0.0

    def _flag(name):
        return _f(features.get(name, 0)) >= 0.5

    # --- Время ---
    if _flag("is_night") or features.get("hour_deviation", 0) > 3:
        context.append({
            "label": "Время активности",
            "actual": "ночное время (после 22:00)" if _flag("is_night") else "н/д",
            "baseline": "09:00–18:00 (рабочие часы)",
            "detail": "время активности выходит за пределы обычного",
        })

    # --- Выходной день ---
    if _flag("is_weekend"):
        context.append({
            "label": "День недели",
            "actual": "выходной день (сб/вс)",
            "baseline": "рабочий день (пн–пт)",
            "detail": "активность зафиксирована в нерабочее время",
        })

    # --- Объём данных ---
    if _flag("high_volume_send") or features.get("bytes_sent_deviation", 0) > 3:
        scaled = _f(features.get("bytes_sent_scaled", 0))
        estimated = int(scaled * 1_000_000)

        def _fmt(b):
            b = float(b)
            if b >= 1_048_576:
                return f"{b / 1_048_576:.1f} МБ"
            if b >= 1024:
                return f"{b / 1024:.1f} КБ"
            return f"{b:.0f} Б"

        context.append({
            "label": "Объём данных",
            "actual": f"отправлено {_fmt(estimated)}",
            "baseline": "типичный объём для этого пользователя",
            "detail": "объём отправленных данных значительно превышает норму",
        })

    # --- Локация ---
    if _flag("unusual_location_count"):
        # Пытаемся получить город из features
        city = ""
        for k, v in features.items():
            if "city" in k.lower() and isinstance(v, str) and v:
                city = v
                break

        baseline_loc = _f(features.get("baseline_unique_locations", 1))
        context.append({
            "label": "Геолокация",
            "actual": f"город: {city}" if city else "необычная локация",
            "baseline": f"{int(baseline_loc)} локация(й) обычно",
            "detail": "обнаружена новая или редкая локация для пользователя",
        })

    # --- Неудачная попытка ---
    if _flag("is_failed"):
        context.append({
            "label": "Статус действия",
            "actual": "неудачная попытка (failed)",
            "baseline": "успешное действие (success)",
            "detail": "неудачные попытки могут указывать на атаку методом перебора",
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


@router.patch("/{alert_id}", response_model=AlertResponse)
def update_alert(
    alert_id: str,
    update: AlertUpdate,
) -> AlertResponse:
    """Обновить статус алерта (расследование, подтверждение, ложное срабатывание)."""
    manager = _get_alert_manager()

    if update.status is None and update.notes is None:
        raise HTTPException(status_code=400, detail="No updates provided")

    status_val = update.status.value if update.status else None
    updated = manager.update_alert_status(
        alert_id=alert_id,
        status=status_val or "",
        notes=update.notes or "",
        resolved_by=update.resolved_by or "",
    )

    if updated is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    return AlertResponse(**updated)
