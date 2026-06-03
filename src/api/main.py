"""Главное приложение FastAPI — UEBA System REST API."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import ValidationError

from src.api.routes import alerts as routes_alerts
from src.api.routes import users as routes_users
from src.api.routes import reports as routes_reports
from src.alerts.manager import AlertManager
from src.alerts.webhook import WebhookSender
from src.ml.detector import AnomalyDetector
from src.pipeline.data_loader import DataLoader
from src.reporting.pdf_generator import PDFReportGenerator


# Глобальные компоненты
_alert_manager: Optional[AlertManager] = None
_detector: Optional[AnomalyDetector] = None
_pdf_generator: Optional[PDFReportGenerator] = None
_webhook_sender: Optional[WebhookSender] = None
_loader: Optional[DataLoader] = None


def configure_logging() -> None:
    """Настраивает логирование приложения."""
    logger.remove()
    logger.add(
        "logs/app.log",
        rotation="10 MB",
        retention="7 days",
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )
    logger.add(
        "logs/app_error.log",
        rotation="10 MB",
        retention="7 days",
        level="ERROR",
        format="<red>{time:YYYY-MM-DD HH:mm:ss}</red> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )


def init_components() -> None:
    """Инициализирует глобальные компоненты приложения."""
    global _alert_manager, _detector, _pdf_generator, _webhook_sender, _loader

    configure_logging()
    logger.info("Initializing UEBA System components")

    # Создаём директории
    Path("data/reports").mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)
    Path("models").mkdir(parents=True, exist_ok=True)

    # Загрузчик данных
    _loader = DataLoader()

    # Загружаем CSV если есть
    events_path = Path("data/events.csv")
    users_path = Path("data/users.csv")

    if events_path.exists() and users_path.exists():
        logger.info("Loading data from CSV files")
        events_df, users_df = _loader.load_from_csv(events_path, users_path)
        routes_users.set_data(events_df, users_df)
    else:
        logger.warning("CSV data files not found. Run data generation first.")
        routes_users.set_data(None, None)

    # Менеджер алертов
    _alert_manager = AlertManager(
        storage_path="data/alerts.json",
    )
    routes_alerts.set_alert_manager(lambda: _alert_manager)
    routes_users.set_alert_manager(lambda: _alert_manager)

    # Webhook sender
    _webhook_sender = WebhookSender()
    if _alert_manager.webhook_url:
        _webhook_sender.set_url(_alert_manager.webhook_url)

    # Детектор аномалий
    _detector = AnomalyDetector(contamination=0.1)
    logger.info("Anomaly detector initialized")

    # Генератор PDF
    _pdf_generator = PDFReportGenerator(author="UEBA System")
    logger.info("PDF generator initialized")

    # Передаём компоненты в роуты
    routes_reports.set_components(
        detector=_detector,
        alert_manager=_alert_manager,
        pdf_generator=_pdf_generator,
        webhook_sender=_webhook_sender,
    )

    logger.success("All components initialized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управляет жизненным циклом приложения."""
    init_components()
    logger.info("UEBA API started on http://0.0.0.0:8000")
    yield
    logger.info("UEBA API shutting down")


app = FastAPI(
    title="UEBA System API",
    description="User and Entity Behavior Analytics - REST API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=True,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Обработчик ошибок валидации
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


# Подключение роутов
app.include_router(routes_alerts.router, prefix="/api")
app.include_router(routes_users.router, prefix="/api")
app.include_router(routes_reports.router, prefix="/api")


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Проверка здоровья системы."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "ueba-api",
    }


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    """Корневой endpoint."""
    return {
        "service": "UEBA - User Entity Behavior Analytics",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
