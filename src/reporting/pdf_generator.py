"""PDF report generation using ReportLab — English-only output."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

# Prefer Helvetica (built-in, broad glyph coverage) over Arial
_FONT = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"


def _clean(text: Any) -> str:
    """Return ASCII-only string — replaces unsupported chars with '?'."""
    if text is None:
        return "n/a"
    # Remove any char with codepoint >= 128
    out = "".join(c if ord(c) < 128 else "?" for c in str(text))
    # Collapse multiple ? to single ?
    out = re.sub(r"\?+", "?", out)
    return out.strip() or "n/a"


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

        def s(name: str, **kw: Any) -> ParagraphStyle:
            return ParagraphStyle(name, parent=base, **kw)

        return {
            "title": s("T", fontName=_FONT_BOLD, fontSize=22,
                        textColor=colors.HexColor("#1a237e"), spaceAfter=12, alignment=TA_CENTER),
            "subtitle": s("ST", fontName=_FONT, fontSize=12,
                           textColor=colors.HexColor("#37474f"), alignment=TA_CENTER, spaceAfter=20),
            "section": s("SEC", fontName=_FONT_BOLD, fontSize=14,
                          textColor=colors.HexColor("#1a237e"), spaceBefore=14, spaceAfter=6),
            "body": s("B", fontName=_FONT, fontSize=10, leading=14, spaceAfter=5),
            "footer": s("FT", fontName=_FONT, fontSize=8,
                         textColor=colors.HexColor("#90a4ae"), alignment=TA_CENTER),
            "h_c": s("HC", fontName=_FONT_BOLD, fontSize=9,
                      textColor=colors.HexColor("#c62828")),
            "h_m": s("HM", fontName=_FONT_BOLD, fontSize=9,
                      textColor=colors.HexColor("#e65100")),
            "h_l": s("HL", fontName=_FONT_BOLD, fontSize=9,
                      textColor=colors.HexColor("#2e7d32")),
            "cell": s("CL", fontName=_FONT, fontSize=8, leading=10, alignment=TA_LEFT),
            "cell_hdr": s("CH", fontName=_FONT_BOLD, fontSize=8, leading=10, alignment=TA_LEFT,
                           textColor=colors.white),
            "cell_bold": s("CB", fontName=_FONT_BOLD, fontSize=8, leading=10, alignment=TA_LEFT),
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

        # Helper: build a Paragraph-wrapped table cell
        def pc(text: str, style: str = "cell") -> Paragraph:
            return Paragraph(_clean(text), st[style])

        # === HEADER ===
        story.append(Paragraph(self._logo_text, st["title"]))
        story.append(Paragraph("Anomaly Investigation Report", st["subtitle"]))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a237e")))
        story.append(Spacer(1, 6 * mm))

        ts = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC")
        story.append(pc(f"Report Date: {ts}", "footer"))
        story.append(pc(f"Alert ID: {alert.get('alert_id', 'n/a')}", "footer"))
        story.append(pc(f"Event ID: {alert.get('event_id', 'n/a')}", "footer"))
        story.append(pc("Analyst: ________________________________", "footer"))
        story.append(Spacer(1, 6 * mm))

        # === 1. ALERT INFORMATION ===
        story.append(Paragraph("1. Alert Information", st["section"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c5cae9")))
        story.append(Spacer(1, 4 * mm))

        risk = _clean(alert.get("risk_level", "low"))
        rmap = {"critical": ("CRITICAL", "h_c"), "high": ("HIGH", "h_c"),
                "medium": ("MEDIUM", "h_m"), "low": ("LOW", "h_l")}
        rlabel, rstyle = rmap.get(risk.lower(), ("UNKNOWN", "body"))
        story.append(Paragraph(f"Risk Level: {rlabel}", st[rstyle]))
        story.append(Spacer(1, 3 * mm))

        def fmt(v: Any) -> str:
            if isinstance(v, float):
                return f"{v:.4f}"
            return str(v) if v is not None else "n/a"

        rows = [
            [pc("Field", "cell_hdr"), pc("Value", "cell_hdr")],
            [pc("User"), pc(f"{alert.get('username', 'n/a')} ({_clean(alert.get('user_id', ''))[:8]}...)")],
            [pc("Event Time"), pc(alert.get("timestamp", "n/a"))],
            [pc("Anomaly Score"), pc(fmt(alert.get("anomaly_score", 0)))],
            [pc("Detected By"), pc(alert.get("detected_by_model", "n/a"))],
            [pc("Status"), pc(alert.get("status", "open"))],
            [pc("Created"), pc(alert.get("created_at", "n/a")[:19].replace("T", " "))],
        ]
        t2 = Table(rows, colWidths=[52 * mm, 118 * mm])
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
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
        story.append(pc(alert.get("reason", "No reason provided")))
        story.append(Spacer(1, 8 * mm))

        # === 3. IDENTIFIED RISK FACTORS ===
        ctx = alert.get("anomaly_context", {})
        items = ctx.get("items", []) if isinstance(ctx, dict) else []
        if items:
            story.append(Paragraph("3. Identified Risk Factors", st["section"]))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c5cae9")))
            story.append(Spacer(1, 4 * mm))
            story.append(pc("Comparison of detected behavior against the user's baseline profile:"))
            story.append(Spacer(1, 3 * mm))

            for item in items:
                label = _clean(item.get("label", "n/a"))
                actual = _clean(item.get("actual", "n/a"))
                baseline = _clean(item.get("baseline", "n/a"))
                detail = _clean(item.get("detail", "n/a"))

                # Card-style block: label in bold, values below
                card = Table([
                    [Paragraph(f"<b>{label}</b>", st["cell_bold"]),
                     Paragraph(f"Detected: <b>{actual}</b><br/>"
                               f"Baseline: <i>{baseline}</i><br/>"
                               f"{detail}", st["cell"])],
                ], colWidths=[38 * mm, 132 * mm])
                card.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#e8eaf6")),
                    ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#fff8e1")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9fa8da")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]))
                story.append(card)
                story.append(Spacer(1, 2 * mm))
            story.append(Spacer(1, 8 * mm))

        # === 4. KEY FEATURES ===
        features = alert.get("features", {})
        section_num = 4 if items else 4
        story.append(Paragraph(f"{section_num}. Key Features", st["section"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c5cae9")))
        story.append(Spacer(1, 4 * mm))

        if features:
            feat_rows = [[pc("Feature", "cell_hdr"), pc("Value", "cell_hdr")]]
            for k, v in list(features.items())[:15]:
                feat_rows.append([pc(k), pc(fmt(v))])
            t4 = Table(feat_rows, colWidths=[85 * mm, 85 * mm])
            t4.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3949ab")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#e8eaf6")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9fa8da")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(t4)
        else:
            story.append(pc("No feature data available."))
        story.append(Spacer(1, 8 * mm))

        # === 5. RECOMMENDATIONS ===
        rec_section = (section_num + 1) if items else (section_num + 1)
        story.append(Paragraph(f"{rec_section}. Recommendations", st["section"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c5cae9")))
        story.append(Spacer(1, 4 * mm))
        for i, rec in enumerate(self._generate_recommendations(alert), 1):
            story.append(pc(f"{i}. {rec}"))
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
            "[ ] False positive -- explain: ____________________________",
            "[ ] Requires further investigation",
        ]:
            story.append(pc(line))
        story.append(Spacer(1, 20 * mm))

        # === FOOTER ===
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cfd8dc")))
        story.append(Spacer(1, 4 * mm))
        story.append(pc(f"UEBA Security System | {ts}", "footer"))

        doc.build(story)
        logger.info(f"PDF report generated: {output_path}")
        return str(output_path)

    def _generate_recommendations(self, alert: dict[str, Any]) -> list[str]:
        risk = _clean(alert.get("risk_level", "low"))
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

        reason = _clean(alert.get("reason", ""))
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

        def pc(text: str, style: str = "cell") -> Paragraph:
            return Paragraph(_clean(text), st[style])

        story.append(Paragraph(self._logo_text, st["title"]))
        story.append(Paragraph("User Behavior Report", st["subtitle"]))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a237e")))
        story.append(Spacer(1, 8 * mm))

        story.append(Paragraph("User Profile", st["section"]))
        rows = [
            [pc("Field", "cell_hdr"), pc("Value", "cell_hdr")],
            [pc("User ID"), pc(user.get("user_id", "n/a"))],
            [pc("Username"), pc(user.get("username", "n/a"))],
            [pc("Role"), pc(user.get("role", "n/a"))],
            [pc("Department"), pc(user.get("department", "n/a"))],
            [pc("Total Events"), pc(str(user.get("total_events", 0)))],
            [pc("Max Anomaly Score"), pc(f"{float(user.get('anomaly_score_max', 0)):.4f}")],
        ]
        t = Table(rows, colWidths=[55 * mm, 115 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfd8dc")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(t)

        doc.build(story)
        return str(output_path)
