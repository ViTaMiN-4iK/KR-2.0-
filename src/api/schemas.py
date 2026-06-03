"""Pydantic-схемы для валидации данных в API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict


class AlertStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    RESOLVED = "resolved"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---- Alert schemas ----

class AlertBase(BaseModel):
    event_id: str
    user_id: str
    username: str
    timestamp: str
    anomaly_score: float = Field(..., ge=0.0, le=1.0)
    risk_level: RiskLevel
    detected_by_model: str
    reason: str
    features: dict[str, float] = Field(default_factory=dict)


class AlertCreate(AlertBase):
    pass


class AnomalyContextItem(BaseModel):
    """Один пункт контекста аномалии: что обнаружено, факт vs норма."""
    label: str          # "Время срабатывания"
    actual: str         # "03:15 ночи"
    baseline: str        # "обычно 09:00–18:00"
    detail: str         # "отклонение: 8 часов 15 минут"


class AnomalyContext(BaseModel):
    """Контекст аномалии — фактическое значение vs нормальное."""
    items: list[AnomalyContextItem] = Field(default_factory=list)


class AlertResponse(AlertBase):
    model_config = ConfigDict(from_attributes=True)

    alert_id: str
    status: AlertStatus
    severity: str
    created_at: str
    updated_at: str
    investigation_notes: str = ""
    resolved_by: str = ""
    anomaly_context: AnomalyContext = Field(default_factory=AnomalyContext)


class AlertUpdate(BaseModel):
    status: Optional[AlertStatus] = None
    notes: Optional[str] = None
    resolved_by: Optional[str] = None


class AlertListResponse(BaseModel):
    total: int
    alerts: list[AlertResponse]
    page: int
    page_size: int


class AlertStatsResponse(BaseModel):
    total: int
    open: Optional[int] = None
    investigating: Optional[int] = None
    confirmed: Optional[int] = None
    resolved: Optional[int] = None
    false_positive: Optional[int] = None
    by_status: dict[str, int]
    by_risk_level: dict[str, int]
    avg_score: float


# ---- User schemas ----

class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    username: str
    full_name: str
    role: str
    department: str
    total_events: int
    unique_actions: int
    unique_locations: int
    avg_hour: float
    unique_resources: int
    avg_bytes_sent: float
    avg_bytes_received: float
    failed_ratio: float
    anomaly_score_max: float
    risk_status: str = "normal"


class UserListResponse(BaseModel):
    total: int
    users: list[UserProfile]


# ---- Event schemas ----

class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    timestamp: str
    user_id: str
    username: str
    action: str
    resource: str
    location_city: str
    location_country: str
    ip_address: str
    device_type: str
    risk_score: float
    status: str


class EventListResponse(BaseModel):
    total: int
    events: list[EventResponse]


# ---- Report schemas ----

class ReportRequest(BaseModel):
    alert_id: str
    include_user_events: bool = True
    include_comparison: bool = True


class ReportResponse(BaseModel):
    report_id: str
    alert_id: str
    generated_at: str
    pdf_url: str


# ---- System schemas ----

class HealthResponse(BaseModel):
    status: str
    version: str
    elasticsearch: bool
    models_loaded: bool


class SystemStats(BaseModel):
    total_events: int
    total_users: int
    total_alerts: int
    open_alerts: int
    trained_models: list[str]


# ---- Training schemas ----

class TrainRequest(BaseModel):
    events_file: Optional[str] = None
    label_column: Optional[str] = None
    contamination: float = Field(default=0.1, ge=0.01, le=0.5)


class TrainResponse(BaseModel):
    status: str
    best_model: str
    f1_score: float
    precision: float
    recall: float
    accuracy: float
    anomaly_count: int
    total_count: int
    training_time_seconds: float


class ModelEvaluationResponse(BaseModel):
    models: dict[str, dict[str, Any]]


# ---- Webhook schemas ----

class WebhookConfig(BaseModel):
    url: str
    enabled: bool = True


class WebhookTestResponse(BaseModel):
    success: bool
    message: str
