"""Blueprint для работы с алертами."""

from __future__ import annotations

import requests

from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash

alerts_bp = Blueprint("alerts", __name__, url_prefix="/alerts")


def get_api_url() -> str:
    try:
        return current_app.config.get("API_BASE_URL", "http://localhost:8000")
    except RuntimeError:
        return "http://localhost:8000"


@alerts_bp.route("/")
def list_alerts():
    status = request.args.get("status", "")
    risk_level = request.args.get("risk_level", "")
    page = request.args.get("page", 1, type=int)

    params = {"page": page, "page_size": 25}
    if status:
        params["status"] = status
    if risk_level:
        params["risk_level"] = risk_level

    try:
        with requests.Session() as s:
            resp = s.get(get_api_url() + "/api/alerts/", params=params, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()

            stats_resp = s.get(get_api_url() + "/api/alerts/stats", timeout=10.0)
            stats = stats_resp.json() if stats_resp.status_code == 200 else {}

        return render_template(
            "alerts.html",
            alerts=data.get("alerts", []),
            total=data.get("total", 0),
            page=data.get("page", 1),
            page_size=data.get("page_size", 25),
            filters={"status": status, "risk_level": risk_level},
            stats=stats,
        )
    except requests.ConnectionError:
        flash("API недоступен. Проверьте, что FastAPI-сервер запущен.", "error")
        return render_template("alerts.html", alerts=[], total=0, stats={})


@alerts_bp.route("/<alert_id>")
def alert_detail(alert_id: str):
    try:
        with requests.Session() as s:
            api = get_api_url()
            resp = s.get(api + "/api/alerts/" + alert_id, timeout=10.0)
            resp.raise_for_status()
            alert = resp.json()

            user_events_resp = s.get(
                api + "/api/users/" + alert["user_id"] + "/events/",
                params={"page_size": 50},
                timeout=10.0,
            )
            user_events = []
            if user_events_resp.status_code == 200:
                user_events = user_events_resp.json().get("events", [])

            user_resp = s.get(api + "/api/users/" + alert["user_id"], timeout=10.0)
            user_profile = None
            if user_resp.status_code == 200:
                user_profile = user_resp.json()

        return render_template(
            "investigate.html",
            alert=alert,
            user_events=user_events,
            user_profile=user_profile,
            anomaly_items=alert.get("anomaly_context", {}).get("items", []),
        )
    except requests.ConnectionError:
        flash("API недоступен.", "error")
        return redirect(url_for("alerts.list_alerts"))


@alerts_bp.route("/<alert_id>/update", methods=["POST"])
def update_alert(alert_id: str):
    new_status = request.form.get("status", "")
    notes = request.form.get("notes", "")
    resolved_by = request.form.get("resolved_by", "analyst")

    if not new_status:
        flash("Статус не указан.", "error")
        return redirect(url_for("alerts.alert_detail", alert_id=alert_id))

    try:
        with requests.Session() as s:
            resp = s.patch(
                get_api_url() + "/api/alerts/" + alert_id,
                json={
                    "status": new_status,
                    "notes": notes,
                    "resolved_by": resolved_by,
                },
                timeout=10.0,
            )
            resp.raise_for_status()
        flash("Статус алерта обновлён на '" + new_status + "'.", "success")
    except requests.ConnectionError:
        flash("API недоступен.", "error")
    except requests.HTTPError as e:
        try:
            msg = e.response.json().get("detail", str(e))
        except Exception:
            msg = str(e)
        flash("Ошибка: " + msg, "error")

    return redirect(url_for("alerts.alert_detail", alert_id=alert_id))


@alerts_bp.route("/<alert_id>/report")
def generate_report(alert_id: str):
    try:
        with requests.Session() as s:
            resp = s.post(
                get_api_url() + "/api/reports/generate",
                json={
                    "alert_id": alert_id,
                    "include_user_events": True,
                    "include_comparison": True,
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            report_data = resp.json()

            pdf_resp = s.get(
                get_api_url() + report_data["pdf_url"],
                timeout=60.0,
            )
            pdf_resp.raise_for_status()

        from flask import make_response
        response = make_response(pdf_resp.content)
        response.headers["Content-Type"] = "application/pdf"
        safe_id = report_data["report_id"]
        response.headers["Content-Disposition"] = (
            f"attachment; filename=ueba_report_{safe_id}.pdf"
        )
        return response

    except requests.ConnectionError:
        flash("API недоступен.", "error")
    except requests.HTTPError:
        flash("Ошибка при генерации отчёта.", "error")

    return redirect(url_for("alerts.alert_detail", alert_id=alert_id))
