"""
POST /api/v1/export/pdf — render an /analyze response as a downloadable PDF.

Body: AnalyzeResponse (or a dict in the same shape).
Returns: application/pdf

The PDF includes:
  - title + timestamp + operator + tenant
  - the operator's original query
  - the AI-generated answer
  - root causes (with probabilities)
  - recommendations (with priorities + rationale)
  - evidence (top retrieved incident ids + scores)
  - agent trace
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/export", tags=["export"])


def _try_import():
    """Lazily import ReportLab components, raising RuntimeError with a helpful message if the package is absent."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        )
        return (colors, LETTER, getSampleStyleSheet, ParagraphStyle, inch,
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle)
    except ImportError as exc:
        raise RuntimeError("reportlab not installed; run pip install -r requirements.txt") from exc


@router.post("/pdf", summary="Export an /analyze response as PDF")
async def export_pdf(payload: Dict[str, Any] = Body(...)):
    """Render an /analyze response payload as a multi-section PDF and stream it as a file download.

    Sections include the query, AI answer, root causes, recommendations, retrieved evidence, and agent trace.
    """
    (colors, LETTER, getSampleStyleSheet, ParagraphStyle, inch,
     SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle) = _try_import()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle('H1', parent=styles['Heading1'], textColor=colors.HexColor('#0F1B2D'))
    h2 = ParagraphStyle('H2', parent=styles['Heading2'], textColor=colors.HexColor('#2EB99B'))
    body = ParagraphStyle('Body', parent=styles['BodyText'], leading=14)
    meta = ParagraphStyle('Meta', parent=styles['BodyText'],
                          textColor=colors.HexColor('#3F4B66'), fontSize=8)

    elems = []
    elems.append(Paragraph("Smart Grid AI · Analysis Report", h1))
    elems.append(Paragraph(
        f"Generated {datetime.utcnow().isoformat()} UTC · "
        f"operator: {payload.get('operator') or 'anonymous'} · "
        f"tenant: {payload.get('tenant_id') or 'default'} · "
        f"provider: {payload.get('provider') or 'n/a'}",
        meta,
    ))
    elems.append(Spacer(1, 12))

    # --- Query ---
    elems.append(Paragraph("Operator Query", h2))
    elems.append(Paragraph(payload.get("query") or "—", body))
    elems.append(Spacer(1, 10))

    # --- Answer ---
    elems.append(Paragraph("AI Answer", h2))
    elems.append(Paragraph(
        f"Confidence: <b>{int(round((payload.get('confidence') or 0) * 100))}%</b>", meta))
    elems.append(Paragraph((payload.get("answer") or "—").replace("\n", "<br/>"), body))
    elems.append(Spacer(1, 10))

    # --- Root causes ---
    causes = payload.get("root_causes") or []
    if causes:
        elems.append(Paragraph("Root Causes", h2))
        rows = [["Cause", "Probability", "Evidence"]]
        for rc in causes:
            rows.append([
                rc.get("cause", ""),
                f"{rc.get('probability', 0):.2f}",
                ", ".join(rc.get("evidence") or [])[:50],
            ])
        t = Table(rows, colWidths=[3.5*inch, 0.9*inch, 2.4*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#A7F1DE')),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.HexColor('#0F1B2D')),
            ('FONTSIZE',   (0, 0), (-1, -1), 9),
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('GRID',       (0, 0), (-1, -1), 0.25, colors.HexColor('#DDE5EE')),
        ]))
        elems.append(t)
        elems.append(Spacer(1, 10))

    # --- Recommendations ---
    recs = payload.get("recommendations") or []
    if recs:
        elems.append(Paragraph("Recommendations", h2))
        rows = [["Priority", "Action", "Rationale"]]
        for r in recs:
            rows.append([r.get("priority", ""), r.get("action", ""), r.get("rationale", "")])
        t = Table(rows, colWidths=[0.7*inch, 2.7*inch, 3.4*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFC59A')),
            ('FONTSIZE',   (0, 0), (-1, -1), 9),
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('GRID',       (0, 0), (-1, -1), 0.25, colors.HexColor('#DDE5EE')),
        ]))
        elems.append(t)
        elems.append(Spacer(1, 10))

    # --- Evidence ---
    retrieved = payload.get("retrieved") or []
    if retrieved:
        elems.append(Paragraph("Retrieved Evidence", h2))
        rows = [["ID", "Score", "Excerpt"]]
        for c in retrieved[:8]:
            score = c.get("score")
            rows.append([
                c.get("id", "")[:36],
                f"{score:.3f}" if isinstance(score, (int, float)) else "—",
                (c.get("text") or "")[:140] + ("…" if len(c.get("text") or "") > 140 else ""),
            ])
        t = Table(rows, colWidths=[1.8*inch, 0.7*inch, 4.3*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D5C5FF')),
            ('FONTSIZE',   (0, 0), (-1, -1), 8),
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('GRID',       (0, 0), (-1, -1), 0.25, colors.HexColor('#DDE5EE')),
        ]))
        elems.append(t)
        elems.append(Spacer(1, 10))

    # --- Agent trace ---
    trace = payload.get("agent_trace") or []
    if trace:
        elems.append(Paragraph("Agent Trace", h2))
        rows = [["Agent", "Status", "Duration (ms)", "Summary"]]
        for t in trace:
            rows.append([t.get("agent", ""), t.get("status", ""),
                         str(t.get("duration_ms", "")), t.get("summary", "")])
        tt = Table(rows, colWidths=[1.7*inch, 0.7*inch, 0.9*inch, 3.5*inch])
        tt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E6FBF6')),
            ('FONTSIZE',   (0, 0), (-1, -1), 8),
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('GRID',       (0, 0), (-1, -1), 0.25, colors.HexColor('#DDE5EE')),
        ]))
        elems.append(tt)

    doc.build(elems)
    buf.seek(0)
    fname = f"analysis_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
