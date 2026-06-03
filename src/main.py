"""UEBA - User and Entity Behavior Analytics System.

Система обнаружения аномалий в поведении пользователей.
Вариант 9 курсового проекта.

Usage:
    python -m src.api.main        # Запуск FastAPI сервера
    python -m web.app             # Запуск Flask веб-интерфейса
    python data/generate_logs.py   # Генерация синтетических данных
"""

from src.pipeline.data_loader import DataLoader
from src.pipeline.features import FeatureEngineer
from src.ml.detector import AnomalyDetector
from src.alerts.manager import AlertManager
from src.alerts.webhook import WebhookSender
from src.reporting.pdf_generator import PDFReportGenerator
