"""Генератор синтетических данных для UEBA-системы.

Создаёт реалистичные логи событий пользователей с нормальным
и аномальным поведением для обучения и тестирования ML-моделей.
"""

from __future__ import annotations

import csv
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Константы для генерации данных
USER_COUNT = 50
NORMAL_RATIO = 0.85
DAYS_TO_GENERATE = 30
EVENTS_PER_DAY_NORMAL = (5, 30)
EVENTS_PER_DAY_ANOMALY = (50, 200)

# Роли пользователей
ROLES = ["developer", "analyst", "manager", "admin", "support"]
DEPARTMENTS = ["IT", "Sales", "Finance", "HR", "Operations"]

# Типичные часы работы (московское время, UTC+3)
WORK_HOURS = list(range(8, 19))

# Рабочие дни недели (пн-пт)
WORKDAYS = [0, 1, 2, 3, 4]

# Действия пользователей
ACTIONS_NORMAL = [
    "login",
    "logout",
    "file_read",
    "file_write",
    "db_query",
    "email_send",
    "meeting_join",
    "document_view",
    "report_generate",
    "config_read",
]

ACTIONS_SUSPICIOUS = [
    "bulk_download",
    "unauthorized_access",
    "privilege_escalation",
    "data_exfiltration",
    "brute_force",
    "sql_injection_attempt",
    "unusual_file_access",
    "off_hours_login",
]

# Геолокации
LOCATIONS = [
    ("Moscow", "RU", 55.7558, 37.6173),
    ("Saint Petersburg", "RU", 59.9344, 30.3351),
    ("Novosibirsk", "RU", 55.0084, 82.9357),
    ("Krasnodar", "RU", 45.0355, 38.9753),
    ("Samara", "RU", 53.1959, 50.1002),
    ("Vladivostok", "RU", 43.1332, 131.9113),
    ("London", "UK", 51.5074, -0.1278),
    ("Berlin", "DE", 52.5200, 13.4050),
    ("New York", "US", 40.7128, -74.0060),
]

# Департаменты -> типичные ресурсы
RESOURCES_BY_DEPT: dict[str, list[str]] = {
    "IT": [
        "/srv/git/repos",
        "/srv/jenkins/builds",
        "/etc/kubernetes",
        "/var/log/syslog",
        "/opt/app/config",
    ],
    "Finance": [
        "/documents/1c/accounts",
        "/reports/quarterly",
        "/invoices/2024",
        "/contracts/active",
        "/documents/audit",
    ],
    "Sales": [
        "/crm/customers",
        "/presentations/marketing",
        "/contracts/templates",
        "/reports/sales",
    ],
    "HR": [
        "/hr/payroll",
        "/hr/personnel",
        "/documents/contracts",
        "/hr/vacations",
    ],
    "Operations": [
        "/ops/schedules",
        "/ops/inventory",
        "/ops/deliveries",
        "/logs/warehouse",
    ],
}

# IP-диапазоны по геолокации
IP_RANGES = {
    "Moscow": "10.0.{zone}.{host}",
    "Saint Petersburg": "10.1.{zone}.{host}",
    "Novosibirsk": "10.2.{zone}.{host}",
    "Krasnodar": "10.3.{zone}.{host}",
    "Samara": "10.4.{zone}.{host}",
    "Vladivostok": "10.5.{zone}.{host}",
    "London": "10.10.{zone}.{host}",
    "Berlin": "10.11.{zone}.{host}",
    "New York": "10.20.{zone}.{host}",
}

# Устройства
DEVICE_TYPES = ["laptop", "desktop", "mobile", "tablet", "server"]
BROWSERS = ["Chrome 120", "Firefox 121", "Safari 17", "Edge 120", "Chrome 119"]
OS_TYPES = ["Windows 11", "macOS 14", "Ubuntu 22.04", "iOS 17", "Android 14"]


def generate_users(count: int) -> list[dict[str, Any]]:
    """Генерирует список пользователей с профилями поведения."""
    users = []
    for i in range(count):
        user_id = f"user_{i + 1:03d}"
        role = random.choice(ROLES)
        dept = random.choice(DEPARTMENTS)
        is_anomaly = random.random() > NORMAL_RATIO

        # Базовые характеристики
        home_city = random.choice(LOCATIONS)
        work_hours = sorted(random.sample(WORK_HOURS, random.randint(6, 10)))
        typical_actions = random.choices(
            ACTIONS_NORMAL,
            k=random.randint(4, 8),
        )

        users.append({
            "user_id": user_id,
            "username": f"{user_id}@company.local",
            "full_name": f"User {i + 1}",
            "role": role,
            "department": dept,
            "is_anomaly_user": is_anomaly,
            "home_location": home_city[0],
            "typical_work_hours": work_hours,
            "typical_actions": list(set(typical_actions)),
        })

    return users


def generate_ip(city: str, internal: bool = True) -> str:
    """Генерирует IP-адрес для города."""
    zone = random.randint(0, 99)
    host = random.randint(1, 254)
    if internal:
        template = IP_RANGES.get(city, IP_RANGES["Moscow"])
        return template.format(zone=zone, host=host)
    return f"195.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def generate_timestamp(
    date: datetime,
    typical_hours: list[int],
    is_anomaly: bool,
    is_workday: bool,
) -> datetime:
    """Генерирует временную метку с учётом паттернов поведения."""
    if not is_workday:
        # Выходные — случайное время в течение дня
        return date.replace(
            hour=random.randint(0, 23),
            minute=random.randint(0, 59),
            second=random.randint(0, 59),
            tzinfo=timezone.utc,
        )

    if is_anomaly:
        # Аномальное поведение: ночное время или раннее утро
        hour = random.choice([0, 1, 2, 3, 4, 5, 22, 23])
    else:
        # Нормальное поведение: в пределах рабочих часов
        hour = random.choices(
            typical_hours + [23],  # иногда задерживаются
            weights=[1] * len(typical_hours) + [0.2],
        )[0]

    return date.replace(
        hour=hour,
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
        tzinfo=timezone.utc,
    )


def generate_action(
    user: dict[str, Any],
    is_anomaly: bool,
    event_count: int,
) -> dict[str, Any]:
    """Генерирует одно событие действия."""
    if is_anomaly:
        suspicious_count = len(ACTIONS_SUSPICIOUS)
        normal_count = len(ACTIONS_NORMAL)
        if event_count > 80:
            weights = [0.6 / suspicious_count] * suspicious_count + [0.4 / normal_count] * normal_count
        else:
            weights = [0.2 / suspicious_count] * suspicious_count + [0.8 / normal_count] * normal_count
        action = random.choices(ACTIONS_SUSPICIOUS + ACTIONS_NORMAL, weights=weights)[0]
        location = random.choice(LOCATIONS)
        city = location[0]
    else:
        action = random.choice(user["typical_actions"])
        city = user["home_location"]
        matching = [l for l in LOCATIONS if l[0] == city]
        location = matching[0] if matching else random.choice(LOCATIONS)

    is_unusual_location = city != user["home_location"] and random.random() < 0.15
    if is_unusual_location:
        location = random.choice([l for l in LOCATIONS if l[0] != user["home_location"]])
        city = location[0]

    return {
        "event_id": str(uuid.uuid4()),
        "action": action,
        "resource": random.choice(RESOURCES_BY_DEPT.get(user["department"], RESOURCES_BY_DEPT["IT"])),
        "location_city": city,
        "location_country": location[1],
        "ip_address": generate_ip(city),
        "device_type": random.choice(DEVICE_TYPES),
        "browser": random.choice(BROWSERS),
        "os": random.choice(OS_TYPES),
        "bytes_sent": random.randint(100, 1_000_000) if "download" in action else random.randint(100, 50000),
        "bytes_received": random.randint(100, 5_000_000) if "download" in action else random.randint(100, 100000),
        "status": "success" if random.random() > 0.05 else random.choice(["failed", "blocked"]),
        "risk_score": 0.0,
    }


def generate_events_for_user(
    user: dict[str, Any],
    start_date: datetime,
    days: int,
) -> list[dict[str, Any]]:
    """Генерирует события для одного пользователя за указанное количество дней."""
    events = []
    is_anomaly = user["is_anomaly_user"]

    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        is_workday = current_date.weekday() in WORKDAYS

        # Количество событий в день
        if is_anomaly:
            # Аномальные пользователи: либо очень много, либо очень мало
            count_range = EVENTS_PER_DAY_ANOMALY
        else:
            count_range = EVENTS_PER_DAY_NORMAL

        event_count = random.randint(*count_range)

        for _ in range(event_count):
            ts = generate_timestamp(
                current_date,
                user["typical_work_hours"],
                is_anomaly,
                is_workday,
            )

            action_data = generate_action(user, is_anomaly, event_count)

            event_dt = ts.replace(tzinfo=None)
            event = {
                "event_id": action_data["event_id"],
                "timestamp": ts.isoformat(),
                "user_id": user["user_id"],
                "username": user["username"],
                "full_name": user["full_name"],
                "role": user["role"],
                "department": user["department"],
                "hour": event_dt.hour,
                "day_of_week": event_dt.weekday(),
                **action_data,
            }
            events.append(event)

    return events


def calculate_risk_scores(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Рассчитывает risk_score для каждого события на основе контекста."""
    for event in events:
        score = 0.0

        # Ночное время (0-6 утра)
        hour = datetime.fromisoformat(event["timestamp"]).hour
        if hour < 6:
            score += 0.3

        # Выходные дни
        weekday = datetime.fromisoformat(event["timestamp"]).weekday()
        if weekday >= 5:
            score += 0.2

        # Подозрительные действия
        if event["action"] in ACTIONS_SUSPICIOUS:
            score += 0.5

        # Необычная страна
        if event["location_country"] not in ("RU",):
            score += 0.15

        # Большой объём данных
        if event["bytes_sent"] > 500_000 or event["bytes_received"] > 2_000_000:
            score += 0.2

        # Неудачный статус
        if event["status"] in ("failed", "blocked"):
            score += 0.15

        event["risk_score"] = min(score, 1.0)

    return events


def generate_dataset(
    output_dir: str | Path = "data",
    user_count: int = USER_COUNT,
    days: int = DAYS_TO_GENERATE,
) -> tuple[Path, Path]:
    """Генерирует полный датасет событий и сохраняет в CSV.

    Returns:
        Кортеж путей к файлам events.csv и users.csv
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    start_date = datetime(2026, 1, 1, tzinfo=timezone.utc)

    users = generate_users(user_count)
    users_file = output_dir / "users.csv"
    with open(users_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "user_id", "username", "full_name", "role",
            "department", "is_anomaly_user", "home_location",
            "typical_work_hours", "typical_actions",
        ])
        writer.writeheader()
        for user in users:
            writer.writerow({
                **user,
                "typical_work_hours": ",".join(map(str, user["typical_work_hours"])),
                "typical_actions": ",".join(str(a) for a in user["typical_actions"]),
            })

    events = []
    for user in users:
        user_events = generate_events_for_user(user, start_date, days)
        events.extend(user_events)

    events = calculate_risk_scores(events)

    # Сортировка по времени
    events.sort(key=lambda e: e["timestamp"])

    events_file = output_dir / "events.csv"
    fieldnames = [
        "event_id", "timestamp", "user_id", "username", "full_name",
        "role", "department", "action", "resource", "location_city",
        "location_country", "ip_address", "device_type", "browser",
        "os", "bytes_sent", "bytes_received", "status", "risk_score",
        "hour", "day_of_week",
    ]
    with open(events_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(events)

    anomaly_count = sum(1 for u in users if u["is_anomaly_user"])
    event_count = len(events)
    anomaly_events = sum(1 for e in events if e["risk_score"] > 0.3)

    print(f"[UEBA Data Gen] Generated:")
    print(f"  - Users: {user_count} (anomaly: {anomaly_count})")
    print(f"  - Events: {event_count} (high risk: {anomaly_events})")
    print(f"  - Files: {events_file}, {users_file}")

    return events_file, users_file


if __name__ == "__main__":
    generate_dataset()
