"""Blueprint главного дашборда."""

from __future__ import annotations

from flask import Blueprint, render_template, request, current_app
import httpx

dashboard_bp = Blueprint("dashboard", __name__)


def get_api_url() -> str:
    return current_app.config.get("API_BASE_URL", "http://localhost:8000")


def _fetch_stats() -> dict:
    """Получает данные с API."""
    base = get_api_url()
    try:
        with httpx.Client(timeout=10.0) as client:
            alerts_resp = client.get(base + "/api/alerts/stats")
            alerts_data = alerts_resp.json() if alerts_resp.status_code == 200 else {}

            alerts_list_resp = client.get(
                base + "/api/alerts/",
                params={"page_size": 10},
            )
            recent_alerts = []
            if alerts_list_resp.status_code == 200:
                recent_alerts = alerts_list_resp.json().get("alerts", [])

            users_resp = client.get(base + "/api/users", params={"page_size": 20})
            users_data = users_resp.json() if users_resp.status_code == 200 else {}

        return alerts_data, recent_alerts, users_data, None
    except httpx.ConnectError:
        return {}, [], {}, "API недоступен"


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
        with httpx.Client(timeout=10.0) as client:
            alerts_resp = client.get(base + "/api/alerts/stats")
            alerts_data = alerts_resp.json() if alerts_resp.status_code == 200 else {}

            alerts_list_resp = client.get(
                base + "/api/alerts/",
                params={"page_size": 10, "status": "open"},
            )
            recent_alerts = []
            if alerts_list_resp.status_code == 200:
                recent_alerts = alerts_list_resp.json().get("alerts", [])

            users_resp = client.get(base + "/api/users/", params={"page_size": 20})
            users_data = users_resp.json() if users_resp.status_code == 200 else {}

        return {
            "alerts": alerts_data,
            "recent_alerts": recent_alerts,
            "users": users_data,
        }
    except httpx.ConnectError:
        return {
            "alerts": {},
            "recent_alerts": [],
            "users": {},
            "error": "API недоступен",
        }, 503
