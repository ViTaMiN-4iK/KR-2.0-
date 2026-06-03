"""Blueprint для работы с пользователями."""

from __future__ import annotations

from flask import Blueprint, render_template, request, current_app
import httpx

users_bp = Blueprint("users", __name__, url_prefix="/users")


def get_api_url() -> str:
    return current_app.config.get("API_BASE_URL", "http://localhost:8000")


@users_bp.route("/")
def list_users():
    department = request.args.get("department", "")
    role = request.args.get("role", "")
    risk_status = request.args.get("risk_status", "")
    page = request.args.get("page", 1, type=int)

    params = {"page": page, "page_size": 25}
    if department:
        params["department"] = department
    if role:
        params["role"] = role
    if risk_status:
        params["risk_status"] = risk_status

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(get_api_url() + "/api/users", params=params)
            resp.raise_for_status()
            data = resp.json()

        return render_template(
            "users.html",
            users=data.get("users", []),
            total=data.get("total", 0),
            page=data.get("page", 1),
            filters={
                "department": department,
                "role": role,
                "risk_status": risk_status,
            },
        )
    except httpx.ConnectError:
        return render_template("users.html", users=[], total=0)


@users_bp.route("/<user_id>")
def user_profile(user_id: str):
    try:
        with httpx.Client(timeout=10.0) as client:
            api = get_api_url()
            resp = client.get(api + "/api/users/" + user_id)
            if resp.status_code == 404:
                return render_template("user_profile.html", user=None, events=[], error="Пользователь не найден")
            resp.raise_for_status()
            user = resp.json()

            events_resp = client.get(
                api + "/api/users/" + user_id + "/events",
                params={"page_size": 100},
            )
            events = []
            if events_resp.status_code == 200:
                events = events_resp.json().get("events", [])

        return render_template("user_profile.html", user=user, events=events, error=None)
    except httpx.HTTPStatusError as e:
        return render_template("user_profile.html", user=None, events=[], error=f"Ошибка API: {e.response.status_code}")
    except httpx.ConnectError:
        return render_template("user_profile.html", user=None, events=[], error="API недоступен")
