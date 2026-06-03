"""API-роуты для работы с пользователями и событиями."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
import pandas as pd

from src.api.schemas import (
    UserProfile,
    UserListResponse,
    EventResponse,
    EventListResponse,
)


router = APIRouter(prefix="/users", tags=["users"])

_events_df = None
_users_df = None
_alert_manager_getter: Annotated[callable | None, None] = None


def set_alert_manager(getter: callable) -> None:
    global _alert_manager_getter
    _alert_manager_getter = getter


def set_data(events_df: pd.DataFrame | None, users_df: pd.DataFrame | None) -> None:
    global _events_df, _users_df
    _events_df = events_df
    _users_df = users_df


def _build_user_profile(user_row: pd.Series | dict, events_sub: pd.DataFrame) -> UserProfile:
    """Строит UserProfile из строки users.csv + статистики из events.csv."""
    user_id = str(user_row.get("user_id", ""))

    # Статистика из events
    if events_sub is not None and not events_sub.empty:
        total_events = len(events_sub)
        unique_actions = int(events_sub["action"].nunique())
        unique_locations = int(events_sub["location_city"].nunique())
        unique_resources = int(events_sub["resource"].nunique()) if "resource" in events_sub.columns else 0
        avg_bytes_sent = float(events_sub["bytes_sent"].mean()) if "bytes_sent" in events_sub.columns else 0.0
        avg_bytes_received = float(events_sub["bytes_received"].mean()) if "bytes_received" in events_sub.columns else 0.0
        failed_count = int((events_sub["status"] == "failed").sum()) if "status" in events_sub.columns else 0
        failed_ratio = failed_count / total_events if total_events > 0 else 0.0
        avg_hour = float(events_sub["hour"].mean()) if "hour" in events_sub.columns and not events_sub["hour"].isna().all() else 0.0
        # Макс скор из событий
        event_max_score = float(events_sub["risk_score"].max()) if "risk_score" in events_sub.columns else 0.0
    else:
        total_events = int(user_row.get("total_events", 0))
        unique_actions = int(user_row.get("unique_actions", 0))
        unique_locations = int(user_row.get("unique_locations", 0))
        unique_resources = 0
        avg_bytes_sent = 0.0
        avg_bytes_received = 0.0
        failed_ratio = 0.0
        avg_hour = 0.0
        event_max_score = float(user_row.get("anomaly_score_max", 0))

    # Данные из алертов (имеют приоритет)
    alert_max_score = 0.0
    alert_risk_status = None

    if _alert_manager_getter is not None:
        try:
            alert_mgr = _alert_manager_getter()
            profile = alert_mgr.get_user_profile(user_id)
            if profile:
                alert_max_score = profile.get("max_anomaly_score", 0.0)
                alert_risk_status = profile.get("risk_status")
        except Exception:
            pass

    # Итоговый макс скор = максимум из событий и алертов
    max_score = max(event_max_score, alert_max_score)

    # Итоговый статус риска
    if alert_risk_status:
        risk_status = alert_risk_status
    else:
        risk_status = _get_risk_status(max_score)

    return UserProfile(
        user_id=user_id,
        username=str(user_row.get("username", "")),
        full_name=str(user_row.get("full_name", "")),
        role=str(user_row.get("role", "")),
        department=str(user_row.get("department", "")),
        total_events=total_events,
        unique_actions=unique_actions,
        unique_locations=unique_locations,
        avg_hour=round(avg_hour, 1),
        unique_resources=unique_resources,
        avg_bytes_sent=round(avg_bytes_sent, 2),
        avg_bytes_received=round(avg_bytes_received, 2),
        failed_ratio=round(failed_ratio, 4),
        anomaly_score_max=round(max_score, 4),
        risk_status=risk_status,
    )


@router.get("", response_model=UserListResponse)
@router.get("/", response_model=UserListResponse)
def list_users(
    department: Annotated[str | None, Query(description="Фильтр по департаменту")] = None,
    role: Annotated[str | None, Query(description="Фильтр по роли")] = None,
    risk_status: Annotated[str | None, Query(description="Фильтр: normal, suspicious, compromised")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UserListResponse:
    """Получить список пользователей с профилями поведения."""
    if _users_df is None:
        raise HTTPException(status_code=503, detail="Users data not loaded")

    result = _users_df.copy()

    if department:
        result = result[result["department"] == department]
    if role:
        result = result[result["role"] == role]

    all_profiles: list[UserProfile] = []
    for _, row in result.iterrows():
        uid = str(row.get("user_id", ""))
        events_sub = None
        if _events_df is not None and not _events_df.empty:
            events_sub = _events_df[_events_df["user_id"] == uid]
        all_profiles.append(_build_user_profile(row, events_sub))

    # Фильтрация по статусу риска
    if risk_status:
        all_profiles = [p for p in all_profiles if p.risk_status == risk_status]

    total = len(all_profiles)
    start = (page - 1) * page_size
    end = start + page_size
    page_profiles = all_profiles[start:end]

    return UserListResponse(total=total, users=page_profiles)


@router.get("/{user_id}", response_model=UserProfile)
def get_user(user_id: str) -> UserProfile:
    """Получить профиль конкретного пользователя."""
    if _users_df is None:
        raise HTTPException(status_code=503, detail="Users data not loaded")

    row = _users_df[_users_df["user_id"] == user_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="User not found")

    events_sub = None
    if _events_df is not None and not _events_df.empty:
        events_sub = _events_df[_events_df["user_id"] == user_id]

    return _build_user_profile(row.iloc[0], events_sub)


@router.get("/{user_id}/events", response_model=EventListResponse)
def get_user_events(
    user_id: str,
    start_date: Annotated[str | None, Query(description="Начало периода (ISO)")] = None,
    end_date: Annotated[str | None, Query(description="Конец периода (ISO)")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> EventListResponse:
    """Получить события конкретного пользователя."""
    if _events_df is None:
        raise HTTPException(status_code=503, detail="Events data not loaded")

    events = _events_df[_events_df["user_id"] == user_id].copy()

    if start_date:
        events = events[events["timestamp"] >= pd.Timestamp(start_date)]
    if end_date:
        events = events[events["timestamp"] <= pd.Timestamp(end_date)]

    total = len(events)
    events = events.sort_values("timestamp", ascending=False)
    start = (page - 1) * page_size
    end = start + page_size
    page_events = events.iloc[start:end]

    return EventListResponse(
        total=total,
        events=[
            EventResponse(
                event_id=str(row.get("event_id", "")),
                timestamp=str(row.get("timestamp", "")),
                user_id=str(row.get("user_id", "")),
                username=str(row.get("username", "")),
                action=str(row.get("action", "")),
                resource=str(row.get("resource", "")),
                location_city=str(row.get("location_city", "")),
                location_country=str(row.get("location_country", "")),
                ip_address=str(row.get("ip_address", "")),
                device_type=str(row.get("device_type", "")),
                risk_score=float(row.get("risk_score", 0)),
                status=str(row.get("status", "")),
            )
            for _, row in page_events.iterrows()
        ],
    )


def _get_risk_status(max_score: float) -> str:
    """Определяет статус риска пользователя."""
    if max_score >= 0.7:
        return "compromised"
    elif max_score >= 0.4:
        return "suspicious"
    return "normal"
