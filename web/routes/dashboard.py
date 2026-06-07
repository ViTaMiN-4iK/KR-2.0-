"""Blueprint главного дашборда."""

from __future__ import annotations

import requests

from flask import Blueprint, render_template, request, current_app

dashboard_bp = Blueprint("dashboard", __name__)


def get_api_url() -> str:
    return current_app.config.get("API_BASE_URL", "http://localhost:8000")


def _fetch_stats() -> dict:
    """Получает данные с API."""
    base = get_api_url()
    try:
        with requests.Session() as s:
            alerts_resp = s.get(base + "/api/alerts/stats", timeout=10.0)
            alerts_data = alerts_resp.json() if alerts_resp.status_code == 200 else {}

            alerts_list_resp = s.get(
                base + "/api/alerts/",
                params={"page_size": 10},
                timeout=10.0,
            )
            recent_alerts = []
            if alerts_list_resp.status_code == 200:
                recent_alerts = alerts_list_resp.json().get("alerts", [])

            users_resp = s.get(base + "/api/users", params={"page_size": 20}, timeout=10.0)
            users_data = users_resp.json() if users_resp.status_code == 200 else {}

        return alerts_data, recent_alerts, users_data, None
    except requests.RequestException as e:
        return {}, [], {}, f"API недоступен: {e}"


@dashboard_bp.route("/dashboard")
def index():
    stats, recent_alerts, users, error = _fetch_stats()
    return render_template(
        "dashboard.html",
        stats=stats,
        recent_alerts=recent_alerts,
        users=users,
        error=error,
    )


@dashboard_bp.route("/api/dashboard/stats")
def dashboard_stats():
    base = get_api_url()
    try:
        with requests.Session() as s:
            alerts_resp = s.get(base + "/api/alerts/stats", timeout=10.0)
            alerts_data = alerts_resp.json() if alerts_resp.status_code == 200 else {}

            alerts_list_resp = s.get(
                base + "/api/alerts/",
                params={"page_size": 10, "status": "open"},
                timeout=10.0,
            )
            recent_alerts = []
            if alerts_list_resp.status_code == 200:
                recent_alerts = alerts_list_resp.json().get("alerts", [])

            users_resp = s.get(base + "/api/users/", params={"page_size": 20}, timeout=10.0)
            users_data = users_resp.json() if users_resp.status_code == 200 else {}

        return {
            "alerts": alerts_data,
            "recent_alerts": recent_alerts,
            "users": users_data,
        }
    except requests.RequestException as e:
        return {
            "alerts": {},
            "recent_alerts": [],
            "users": {},
            "error": "API недоступен",
        }, 503
