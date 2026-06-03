# UEBA System - User and Entity Behavior Analytics

Система обнаружения аномалий в поведении пользователей (UEBA) для курсовой работы по дисциплине «Методы и технологии программирования».

## Вариант 9

**Предметная область**: Мониторинг инцидентов
**Технологии**: Python + pandas + scikit-learn + Elasticsearch + Flask + FastAPI + ReportLab

## Описание

Система анализирует логи событий (входы, действия, доступ к данным) для выявления подозрительной активности. Построение профилей нормального поведения, обнаружение отклонений (необычное время, местоположение, объёмы данных). Визуализация в веб-интерфейсе, алерты при критических аномалиях.

## Архитектура

```
┌──────────────────────────────────────────────┐
│  Synthetic Data Generator (data/generate_logs.py) │
│  Пользователи, события, аномальные паттерны  │
└─────────────────────┬────────────────────────┘
                      ▼
┌──────────────────────────────────────────────┐
│  Data Pipeline (src/pipeline/)               │
│  data_loader.py + features.py                │
│  Нормализация, feature engineering           │
└─────────────────────┬────────────────────────┘
                      ▼
┌──────────────────────────────────────────────┐
│  Elasticsearch + Kibana (Docker)             │
│  Хранение событий и визуализация             │
└─────────────────────┬────────────────────────┘
                      ▼
┌──────────────────────────────────────────────┐
│  ML Engine (src/ml/)                         │
│  Isolation Forest + One-Class SVM + DBSCAN   │
│  Автоматический выбор лучшей модели          │
└──────────┬─────────────────┬────────────────┘
           ▼                 ▼
┌──────────────────┐  ┌────────────────────────┐
│  FastAPI REST API│  │  Flask Web Interface   │
│  (port 8000)     │  │  (port 5000)           │
│  /api/alerts     │  │  /dashboard/alerts      │
│  /api/users      │  │  /alerts/investigate   │
│  /api/reports    │  │  /users/profile         │
└──────────┬────────┘  └───────────┬────────────┘
           │                       │
           ▼                       ▼
    PDF-отчёты (ReportLab)    Webhook-алерты
```

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Генерация синтетических данных

```bash
python data/generate_logs.py
```

Генерирует 50 пользователей и события за 30 дней.
~15% пользователей помечены как аномальные.

### 3. Запуск через Docker Compose

```bash
docker-compose up -d
```

- **FastAPI**: http://localhost:8000
- **Flask UI**: http://localhost:5000
- **Kibana**: http://localhost:5601
- **Elasticsearch**: http://localhost:9200

### 4. Запуск без Docker

```bash
# Запуск API
uvicorn src.api.main:app --reload --port 8000

# Запуск веб-интерфейса (в отдельном терминале)
flask --app web.app:app run --port 5000
```

## Структура проекта

```
Cursovaya_2.0/
├── data/                   # Синтетические данные
│   ├── generate_logs.py    # Генератор логов
│   ├── events.csv          # События (генерируемые)
│   ├── users.csv           # Пользователи (генерируемые)
│   └── alerts.json         # Алерты
├── src/
│   ├── pipeline/           # Пайплайн обработки
│   │   ├── data_loader.py  # Загрузка из CSV/ES
│   │   └── features.py     # Feature engineering
│   ├── ml/                 # ML-движок
│   │   ├── models.py       # Модели (IF, SVM, DBSCAN)
│   │   ├── trainer.py      # Обучение + автовыбор
│   │   └── detector.py     # Главный детектор
│   ├── api/                # FastAPI REST API
│   │   ├── main.py         # Точка входа
│   │   ├── schemas.py      # Pydantic модели
│   │   └── routes/         # API endpoints
│   ├── alerts/             # Система алертов
│   │   ├── manager.py      # Жизненный цикл алертов
│   │   └── webhook.py      # Webhook-отправка
│   └── reporting/          # Генерация отчётов
│       └── pdf_generator.py # PDF (ReportLab)
├── web/                    # Веб-интерфейс
│   ├── app.py              # Flask приложение
│   ├── filters.py          # Jinja фильтры
│   ├── routes/             # Blueprints
│   └── templates/          # HTML шаблоны
├── tests/                  # Тесты
├── docs/                   # Диаграммы
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

## API Endpoints

### Alerts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/alerts` | Список алертов с фильтрами |
| GET | `/api/alerts/{id}` | Детали алерта |
| GET | `/api/alerts/stats` | Статистика по алертам |
| PATCH | `/api/alerts/{id}` | Обновление статуса |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users` | Список пользователей |
| GET | `/api/users/{id}` | Профиль пользователя |
| GET | `/api/users/{id}/events` | События пользователя |

### Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/reports/generate` | Генерация PDF-отчёта |
| GET | `/api/reports/download/{id}` | Скачать PDF |

### Training

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/train` | Тренировка ML-модели |
| GET | `/api/models/evaluation` | Сравнение моделей |

### Webhook

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/webhook/configure` | Настройка webhook |
| POST | `/api/webhook/test` | Тест webhook |

## ML Модели

1. **Isolation Forest** — древовидная модель для обнаружения аномалий
2. **One-Class SVM** — метод опорных векторов для one-class классификации
3. **DBSCAN** — кластеризация с выделением шумовых точек как аномалий
4. **Local Outlier Factor** — обнаружение локальных выбросов

Автоматический выбор лучшей модели по F1-score.

## Веб-интерфейс

- **Dashboard** (`/dashboard`) — обзорная панель со статистикой
- **Alerts** (`/alerts`) — список всех алертов с фильтрами
- **Investigate** (`/alerts/{id}`) — детальное расследование алерта: timeline событий пользователя, обновление статуса, генерация PDF
- **Users** (`/users`) — список пользователей с профилями риска
- **User Profile** (`/users/{id}`) — полная карточка пользователя

## Тестирование

```bash
pytest tests/ -v
pytest tests/ --cov=src --cov-report=html
```

## SAST-анализ

```bash
bandit -r src/ -f json -o bandit_report.json
```

## Генерация отчётов

После создания алертов можно сгенерировать PDF-отчёт, включающий:
- Информацию об алерте и уровне риска
- Причину аномалии
- Ключевые признаки аномалии
- Рекомендации по реагированию
- Место для заметок расследования

## Конфигурация

```bash
cp .env.example .env
# Отредактируйте .env
```

| Параметр | Описание | Значение по умолчанию |
|----------|---------|----------------------|
| `ELASTICSEARCH_URL` | URL Elasticsearch | http://localhost:9200 |
| `FLASK_SECRET_KEY` | Секретный ключ Flask | dev-secret-key... |
| `API_BASE_URL` | URL API для Flask | http://localhost:8000 |
| `WEBHOOK_URL` | URL для webhook-уведомлений | (пусто) |
| `LOG_LEVEL` | Уровень логирования | INFO |

## Разработка

```bash
# Установка pre-commit hooks
pip install pre-commit
pre-commit install

# Запуск всех тестов с покрытием
pytest tests/ --cov=src --cov-report=term-missing --cov-report=html

# Форматирование кода
ruff format .
ruff check --fix .
```
# KR-2.0-
