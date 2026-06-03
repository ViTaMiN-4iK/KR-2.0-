"""Jinja2-фильтры для шаблонов."""

from __future__ import annotations

from flask import Flask


def register(app: Flask) -> None:
    """Регистрирует кастомные фильтры в Jinja2."""

    @app.template_filter("risk_badge")
    def risk_badge(value: str) -> str:
        """Возвращает CSS-класс для уровня риска."""
        mapping = {
            "critical": "badge-critical",
            "high": "badge-high",
            "medium": "badge-medium",
            "low": "badge-low",
        }
        return mapping.get(value.lower(), "badge-low")

    @app.template_filter("status_badge")
    def status_badge(value: str) -> str:
        """Возвращает CSS-класс для статуса."""
        mapping = {
            "open": "badge-open",
            "investigating": "badge-investigating",
            "confirmed": "badge-confirmed",
            "false_positive": "badge-false-positive",
            "resolved": "badge-resolved",
        }
        return mapping.get(value.lower(), "badge-open")

    @app.template_filter("score_color")
    def score_color(value: float) -> str:
        """Цвет для отображения скора."""
        if value >= 0.8:
            return "#c62828"
        elif value >= 0.6:
            return "#e65100"
        elif value >= 0.4:
            return "#f9a825"
        return "#2e7d32"

    @app.template_filter("datetime_format")
    def datetime_format(value: str) -> str:
        """Форматирует ISO datetime в читаемый вид."""
        if not value:
            return "-"
        try:
            if "T" in value:
                dt = value.replace("T", " ").split(".")[0]
                return dt
            return value
        except Exception:
            return value

    @app.template_filter("truncate_middle")
    def truncate_middle(value: str, length: int = 40) -> str:
        """Обрезает строку посередине."""
        if not value or len(value) <= length:
            return value
        half = (length - 3) // 2
        return f"{value[:half]}...{value[-half:]}"
