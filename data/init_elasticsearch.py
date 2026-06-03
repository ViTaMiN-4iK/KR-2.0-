#!/usr/bin/env python3
"""Инициализация Elasticsearch индексов через HTTP API (urllib)."""

import csv
import json
import urllib.request
import urllib.error
from pathlib import Path


ES_URL = "http://elasticsearch:9200"


def es_get(path: str) -> dict | None:
    try:
        with urllib.request.urlopen(ES_URL + path, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  GET {path}: {e}")
        return None


def es_put(path: str, body: dict) -> bool:
    try:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            ES_URL + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"  OK: {path} ({r.status})")
            return True
    except urllib.error.HTTPError as e:
        body_resp = e.read().decode()
        if e.code == 400:
            print(f"  Already exists: {path}")
        else:
            print(f"  PUT {path}: HTTP {e.code} - {body_resp[:200]}")
        return False
    except Exception as e:
        print(f"  PUT {path}: {e}")
        return False


def es_post(path: str, body: bytes) -> bool:
    try:
        req = urllib.request.Request(
            ES_URL + path,
            data=body,
            headers={"Content-Type": "application/x-ndjson"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return True
    except Exception as e:
        print(f"  POST {path}: {e}")
        return False


def create_indices():
    print("Creating indices...")
    indices = {
        "ueba-events": {
            "mappings": {
                "properties": {
                    "event_id": {"type": "keyword"},
                    "timestamp": {"type": "date"},
                    "user_id": {"type": "keyword"},
                    "username": {"type": "keyword"},
                    "full_name": {"type": "text"},
                    "role": {"type": "keyword"},
                    "department": {"type": "keyword"},
                    "action": {"type": "keyword"},
                    "resource": {"type": "keyword"},
                    "location_city": {"type": "keyword"},
                    "location_country": {"type": "keyword"},
                    "ip_address": {"type": "ip"},
                    "device_type": {"type": "keyword"},
                    "browser": {"type": "keyword"},
                    "os": {"type": "keyword"},
                    "bytes_sent": {"type": "long"},
                    "bytes_received": {"type": "long"},
                    "status": {"type": "keyword"},
                    "risk_score": {"type": "float"},
                    "hour": {"type": "integer"},
                    "day_of_week": {"type": "integer"},
                }
            },
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        },
        "ueba-alerts": {
            "mappings": {
                "properties": {
                    "alert_id": {"type": "keyword"},
                    "event_id": {"type": "keyword"},
                    "user_id": {"type": "keyword"},
                    "username": {"type": "keyword"},
                    "timestamp": {"type": "date"},
                    "anomaly_score": {"type": "float"},
                    "risk_level": {"type": "keyword"},
                    "detected_by_model": {"type": "keyword"},
                    "reason": {"type": "text"},
                    "status": {"type": "keyword"},
                    "severity": {"type": "keyword"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                    "investigation_notes": {"type": "text"},
                    "resolved_by": {"type": "keyword"},
                }
            },
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        },
        "ueba-users": {
            "mappings": {
                "properties": {
                    "user_id": {"type": "keyword"},
                    "username": {"type": "keyword"},
                    "full_name": {"type": "text"},
                    "role": {"type": "keyword"},
                    "department": {"type": "keyword"},
                    "is_anomaly_user": {"type": "boolean"},
                    "home_location": {"type": "keyword"},
                    "typical_work_hours": {"type": "keyword"},
                    "typical_actions": {"type": "keyword"},
                }
            },
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        },
    }

    for name, body in indices.items():
        es_put(f"/{name}", body)


def seed_events():
    csv_path = Path(__file__).parent / "events.csv"
    if not csv_path.exists():
        print("events.csv not found, skipping seed")
        return

    print(f"Seeding events from {csv_path}...")
    count = 0
    batch = b""

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc = {
                "event_id": row.get("event_id", ""),
                "timestamp": row.get("timestamp", ""),
                "user_id": row.get("user_id", ""),
                "username": row.get("username", ""),
                "full_name": row.get("full_name", ""),
                "role": row.get("role", ""),
                "department": row.get("department", ""),
                "action": row.get("action", ""),
                "resource": row.get("resource", ""),
                "location_city": row.get("location_city", ""),
                "location_country": row.get("location_country", ""),
                "ip_address": row.get("ip_address", ""),
                "device_type": row.get("device_type", ""),
                "browser": row.get("browser", ""),
                "os": row.get("os", ""),
                "bytes_sent": int(row.get("bytes_sent", 0) or 0),
                "bytes_received": int(row.get("bytes_received", 0) or 0),
                "status": row.get("status", ""),
                "risk_score": float(row.get("risk_score", 0) or 0),
                "hour": int(row.get("hour", 0) or 0),
                "day_of_week": int(row.get("day_of_week", 0) or 0),
            }

            batch += (json.dumps({"index": {"_id": doc["event_id"]}}, ensure_ascii=False) + "\n").encode()
            batch += (json.dumps(doc, ensure_ascii=False) + "\n").encode()
            count += 1

            if count % 2000 == 0:
                ok = es_post("/ueba-events/_bulk", batch)
                batch = b""
                print(f"  Indexed {count}...")

        if batch:
            es_post("/ueba-events/_bulk", batch)

    print(f"Done: {count} events seeded")


def seed_users():
    csv_path = Path(__file__).parent / "users.csv"
    if not csv_path.exists():
        print("users.csv not found, skipping seed")
        return

    print(f"Seeding users from {csv_path}...")
    count = 0
    batch = b""

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc = {
                "user_id": row.get("user_id", ""),
                "username": row.get("username", ""),
                "full_name": row.get("full_name", ""),
                "role": row.get("role", ""),
                "department": row.get("department", ""),
                "is_anomaly_user": row.get("is_anomaly_user", "False").lower() == "true",
                "home_location": row.get("home_location", ""),
                "typical_work_hours": [int(x) for x in row.get("typical_work_hours", "").split(",") if x],
                "typical_actions": [x for x in row.get("typical_actions", "").split(",") if x],
            }

            batch += (json.dumps({"index": {"_id": doc["user_id"]}}, ensure_ascii=False) + "\n").encode()
            batch += (json.dumps(doc, ensure_ascii=False) + "\n").encode()
            count += 1

            if count % 1000 == 0:
                es_post("/ueba-users/_bulk", batch)
                batch = b""
                print(f"  Indexed {count}...")

        if batch:
            es_post("/ueba-users/_bulk", batch)

    print(f"Done: {count} users seeded")


def seed_alerts():
    json_path = Path(__file__).parent / "alerts.json"
    if not json_path.exists():
        print("alerts.json not found, skipping seed")
        return

    print(f"Seeding alerts from {json_path}...")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    alerts = data.get("alerts", data) if isinstance(data, dict) else data

    count = 0
    batch = b""

    for alert in alerts:
        doc = {
            "alert_id": alert.get("alert_id", ""),
            "event_id": alert.get("event_id", ""),
            "user_id": alert.get("user_id", ""),
            "username": alert.get("username", ""),
                "timestamp": alert.get("timestamp", "").replace(" ", "T"),
            "anomaly_score": float(alert.get("anomaly_score", 0) or 0),
            "risk_level": alert.get("risk_level", ""),
            "detected_by_model": alert.get("detected_by_model", ""),
            "reason": alert.get("reason", ""),
            "status": alert.get("status", ""),
            "severity": alert.get("severity", ""),
            "created_at": alert.get("created_at", ""),
            "updated_at": alert.get("updated_at", ""),
            "investigation_notes": alert.get("investigation_notes", ""),
            "resolved_by": alert.get("resolved_by", ""),
        }

        batch += (json.dumps({"index": {"_id": doc["alert_id"]}}, ensure_ascii=False) + "\n").encode()
        batch += (json.dumps(doc, ensure_ascii=False) + "\n").encode()
        count += 1

        if count % 1000 == 0:
            es_post("/ueba-alerts/_bulk", batch)
            batch = b""
            print(f"  Indexed {count}...")

    if batch:
        es_post("/ueba-alerts/_bulk", batch)

    print(f"Done: {count} alerts seeded")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    # Test connection
    info = es_get("/")
    if not info:
        print("ERROR: Cannot connect to Elasticsearch")
        sys.exit(1)
    print(f"Connected to Elasticsearch {info.get('version', {}).get('number', '?')}")

    create_indices()
    seed_events()
    seed_users()
    seed_alerts()
    print("\nAll done!")
