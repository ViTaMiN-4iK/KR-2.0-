"""Генерация PDF-отчётов об аномалиях с использованием ReportLab."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.enums import TA_CENTER
from loguru import logger


class PDFReportGenerator:
    def __init__(
        self,
        logo_text: str = "UEBA System",
        author: str = "UEBA Security Team",
    ) -> None:
        self._logo_text = logo_text
        self._author = author
        self._st = self._styles()

    def _styles(self):
        base = getSampleStyleSheet()["Normal"]

        def s(name, **kw):
            return ParagraphStyle(name, parent=base, **kw)

        return {
            "title": s("T", fontName="Helvetica-Bold", fontSize=22,
                        textColor=colors.HexColor("#1a237e"), spaceAfter=12, alignment=TA_CENTER),
            "subtitle": s("ST", fontName="Helvetica", fontSize=12,
                            textColor=colors.HexColor("#37474f"), alignment=TA_CENTER, spaceAfter=20),
            "section": s("SEC", fontName="Helvetica-Bold", fontSize=14,
                           textColor=colors.HexColor("#1a237e"), spaceBefore=14, spaceAfter=6),
            "body": s("B", fontName="Helvetica", fontSize=10, leading=14, spaceAfter=5),
            "footer": s("FT", fontName="Helvetica", fontSize=8,
                          textColor=colors.HexColor("#90a4ae"), alignment=TA_CENTER),
            "h_c": s("HC", fontName="Helvetica-Bold", fontSize=9,
                        textColor=colors.HexColor("#c62828")),
            "h_m": s("HM", fontName="Helvetica-Bold", fontSize=9,
                        textColor=colors.HexColor("#e65100")),
            "h_l": s("HL", fontName="Helvetica-Bold", fontSize=9,
                        textColor=colors.HexColor("#2e7d32")),
        }

    def generate_alert_report(
        self,
        alert: dict[str, Any],
        output_path: str | Path,
        include_user_events: bool = True,
        include_comparison: bool = True,
    ) -> str:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=20 * mm, leftMargin=20 * mm,
            topMargin=20 * mm, bottomMargin=20 * mm,
        )
        st = self._st
        story = []

        # === HEADER ===
        story.append(Paragraph(self._logo_text, st["title"]))
        story.append(Paragraph("Anomaly Investigation Report", st["subtitle"]))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a237e")))
        story.append(Spacer(1, 6 * mm))

        ts = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC")
        meta = [
            ["Report Date:", ts],
            ["Alert ID:", alert.get("alert_id", "—")],
            ["Event ID:", alert.get("event_id", "—")],
            ["Analyst:", "____________________________"],
        ]
        t = Table(meta, colWidths=[42 * mm, 128 * mm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#546e7a")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(t)
        story.append(Spacer(1, 8 * mm))

        # === 1. ALERT INFORMATION ===
        story.append(Paragraph("1. Alert Information", st["section"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c5cae9")))
        story.append(Spacer(1, 4 * mm))

        risk = alert.get("risk_level", "low")
        rmap = {"critical": ("CRITICAL", "h_c"), "high": ("HIGH", "h_c"),
                "medium": ("MEDIUM", "h_m"), "low": ("LOW", "h_l")}
        rlabel, rstyle = rmap.get(risk, ("UNKNOWN", "body"))
        story.append(Paragraph(f"Risk Level: {rlabel}", st[rstyle]))
        story.append(Spacer(1, 3 * mm))

        def _fmt(v):
            if isinstance(v, float):
                return f"{v:.4f}"
            return str(v) if v is not None else "—"

        rows = [
            ["Field", "Value"],
            ["User", f"{alert.get('username', '—')} ({alert.get('user_id', '—')[:8]}...)"],
            ["Event Time", alert.get("timestamp", "—")],
            ["Anomaly Score", _fmt(alert.get("anomaly_score", 0))],
            ["Detected By", alert.get("detected_by_model", "—")],
            ["Status", alert.get("status", "open")],
            ["Created", alert.get("created_at", "—")[:19].replace("T", " ")],
        ]
        t2 = Table(rows, colWidths=[52 * mm, 118 * mm])
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eceff1")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfd8dc")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.append(t2)
        story.append(Spacer(1, 8 * mm))

        # === 2. ANOMALY REASON ===
        story.append(Paragraph("2. Anomaly Reason", st["section"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c5cae9")))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(alert.get("reason", "No reason provided"), st["body"]))
        story.append(Spacer(1, 8 * mm))

        # === 3. IDENTIFIED RISK FACTORS ===
        ctx = alert.get("anomaly_context", {})
        items = ctx.get("items", []) if isinstance(ctx, dict) else []
        if items:
            story.append(Paragraph("3. Identified Risk Factors", st["section"]))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c5cae9")))
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph(
                "Comparison of detected behavior against the user's baseline profile:",
                st["body"],
            ))
            story.append(Spacer(1, 3 * mm))

            ctx_rows = [["Parameter", "Detected", "Baseline", "Explanation"]]
            for item in items:
                ctx_rows.append([
                    item.get("label", "—"),
                    item.get("actual", "—"),
                    item.get("baseline", "—"),
                    item.get("detail", "—"),
                ])

            t3 = Table(ctx_rows, colWidths=[36 * mm, 40 * mm, 44 * mm, 50 * mm])
            t3.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fff8e1")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfd8dc")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("BACKGROUND", (1, 1), (1, -1), colors.HexColor("#ffebee")),
                ("TEXTCOLOR", (1, 1), (1, -1), colors.HexColor("#c62828")),
                ("FONTNAME", (1, 1), (1, -1), "Helvetica-Bold"),
            ]))
            story.append(t3)
            story.append(Spacer(1, 8 * mm))

        # === 4. KEY FEATURES ===
        features = alert.get("features", {})
        section_num = 4 if not items else 4
        story.append(Paragraph(f"{section_num}. Key Features", st["section"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c5cae9")))
        story.append(Spacer(1, 4 * mm))

        if features:
            feat_rows = [["Feature", "Value"]]
            for k, v in list(features.items())[:15]:
                feat_rows.append([k, f"{float(v):.4f}"])
            t4 = Table(feat_rows, colWidths=[85 * mm, 85 * mm])
            t4.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3949ab")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#e8eaf6")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9fa8da")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(t4)
        else:
            story.append(Paragraph("No feature data available.", st["body"]))
        story.append(Spacer(1, 8 * mm))

        # === 5. RECOMMENDATIONS ===
        rec_section = (section_num + 1) if not items else (section_num + 1)
        story.append(Paragraph(f"{rec_section}. Recommendations", st["section"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c5cae9")))
        story.append(Spacer(1, 4 * mm))

        for i, rec in enumerate(self._generate_recommendations(alert), 1):
            story.append(Paragraph(f"{i}. {rec}", st["body"]))
        story.append(Spacer(1, 8 * mm))

        # === 6. INVESTIGATION NOTES ===
        notes_section = rec_section + 1
        story.append(Paragraph(f"{notes_section}. Investigation Notes", st["section"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c5cae9")))
        story.append(Spacer(1, 5 * mm))

        for line in [
            "Investigator: _____________________________________________",
            "Date: _____________________",
            "",
            "Findings:",
            "___________________________________________________________",
            "___________________________________________________________",
            "___________________________________________________________",
            "",
            "Conclusion:",
            "[ ] Confirmed as malicious activity",
            "[ ] False positive — explain: ____________________________",
            "[ ] Requires further investigation",
        ]:
            story.append(Paragraph(line, st["body"]))

        story.append(Spacer(1, 20 * mm))

        # === FOOTER ===
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cfd8dc")))
        story.append(Spacer(1, 4 * mm))
        f1 = Paragraph(f"UEBA Security System | {ts}", st["footer"])
        f2 = Paragraph(f"Author: {self._author}", st["footer"])
        ft = Table([[f1, f2]], colWidths=[85 * mm, 85 * mm])
        ft.setStyle(TableStyle([
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        story.append(ft)

        doc.build(story)
        logger.info(f"PDF report generated: {output_path}")
        return str(output_path)

    def _generate_recommendations(self, alert: dict[str, Any]) -> list[str]:
        risk = alert.get("risk_level", "low")
        recs: list[str] = []

        if risk in ("critical", "high"):
            recs.extend([
                "Immediately isolate the affected account and revoke all active sessions.",
                "Notify the security operations center (SOC) and initiate incident response.",
                "Review recent authentication logs for the user (last 30 days).",
                "Check for data exfiltration attempts (large outbound data transfers).",
                "Consider temporary account suspension pending investigation.",
            ])
        elif risk == "medium":
            recs.extend([
                "Flag the account for enhanced monitoring.",
                "Notify the user's direct supervisor about suspicious activity.",
                "Review access logs for the resources involved in the anomaly.",
                "Schedule a follow-up review in 48 hours.",
            ])
        else:
            recs.extend([
                "Log the event for future pattern analysis.",
                "Continue standard monitoring.",
            ])

        reason = alert.get("reason", "")
        if "night" in reason.lower():
            recs.append("Review legitimate after-hours work patterns for this user.")
        if "data" in reason.lower() or "volume" in reason.lower():
            recs.append("Verify the necessity of large data transfers with the data owner.")
        if "location" in reason.lower():
            recs.append("Confirm with the user whether the location change is expected.")

        return recs

    def generate_user_report(
        self,
        user: dict[str, Any],
        events: list[dict[str, Any]],
        output_path: str | Path,
    ) -> str:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=20 * mm, leftMargin=20 * mm,
            topMargin=20 * mm, bottomMargin=20 * mm,
        )
        st = self._st
        story = []

        story.append(Paragraph(self._logo_text, st["title"]))
        story.append(Paragraph("User Behavior Report", st["subtitle"]))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a237e")))
        story.append(Spacer(1, 8 * mm))

        story.append(Paragraph("User Profile", st["section"]))
        rows = [
            ["Field", "Value"],
            ["User ID", user.get("user_id", "—")],
            ["Username", user.get("username", "—")],
            ["Role", user.get("role", "—")],
            ["Department", user.get("department", "—")],
            ["Total Events", str(user.get("total_events", 0))],
            ["Max Anomaly Score", f"{float(user.get('anomaly_score_max', 0)):.4f}"],
        ]
        t = Table(rows, colWidths=[55 * mm, 115 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfd8dc")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(t)

        doc.build(story)
        return str(output_path)
