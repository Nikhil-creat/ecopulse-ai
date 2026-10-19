from datetime import datetime, timezone
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.agents.schemas import AgentRunResult

LEVEL_COLOR = {"low": "#2e9e5b", "moderate": "#d4a017", "high": "#e67e22", "very_high": "#d35400", "severe": "#b03a2e"}


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(text)), style)


def _table(rows: list[list[str]], widths: list[float], style: ParagraphStyle) -> Table:
    t = Table([[_p(c, style) for c in r] for r in rows], colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef2")),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4cc")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def build_report_pdf(result: AgentRunResult) -> bytes:
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=13)
    small = ParagraphStyle("s", parent=body, fontSize=8.5, leading=11)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], spaceBefore=10, spaceAfter=4)
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title="EcoPulse AI - Executive Health & Policy Report")
    w = A4[0] - 36 * mm
    s: list = [Paragraph("EcoPulse AI - Executive Health &amp; Policy Report", ss["Title"]),
               _p(f"Scope: {result.scope}    Generated: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC", small),
               Spacer(1, 6)]

    if result.halted or not result.risk:
        s += [Paragraph("Report unavailable", h2),
              _p(f"The agent pipeline halted: {result.halt_reason or 'insufficient data'}. "
                 "No risk assessment or policy recommendations were produced.", body)]
    else:
        r = result.risk
        color = LEVEL_COLOR.get(r.level, "#444444")
        s += [Paragraph(f'Risk level: <font color="{color}"><b>{escape(r.level.replace("_", " ").upper())}</b></font>', h2),
              _table([["Metric", "Value"],
                      ["Current AQI (CPCB)", f"{r.current_aqi} ({r.category})"],
                      ["PM2.5 (median, ug/m3)", str(r.current_pm25)],
                      ["x WHO 24h guideline (15)", str(r.who_pm25_exceedance)],
                      ["x CPCB 24h standard (60)", str(r.cpcb_pm25_exceedance)],
                      ["Satellite/CNN cross-check", f"{r.cnn_cross_check.status}: {r.cnn_cross_check.note}"]],
                     [55 * mm, w - 55 * mm], small),
              Paragraph("Summary", h2), _p(r.narrative, body)]
        if r.forecast:
            s += [Paragraph(f"Forecast ({r.forecast.model}, PM2.5 ug/m3)", h2),
                  _table([["Horizon", "Predicted", "Range"]] +
                         [[f"+{p.horizon_hours} h", f"{p.predicted}", f"{p.lower} - {p.upper}"] for p in r.forecast.points],
                         [30 * mm, 40 * mm, w - 70 * mm], small)]
        s += [Paragraph("Health guidance", h2)] + [_p(f"- {a}", body) for a in r.vulnerable_group_advice]
        if result.policy:
            s += [Paragraph("Recommended measures (require official approval)", h2), _p(result.policy.narrative, body),
                  Spacer(1, 4),
                  _table([["Priority", "Area", "Action", "Rationale"]] +
                         [[a.priority, a.category, a.action, a.rationale] for a in result.policy.actions],
                         [24 * mm, 24 * mm, (w - 48 * mm) * 0.5, (w - 48 * mm) * 0.5], small)]
        if result.integrity:
            s += [Paragraph("Data integrity", h2), _p(result.integrity.summary, body)]
            for st in result.integrity.stations:
                if st.issues:
                    s.append(_p(f"{st.station_id} (score {st.score}): " + "; ".join(st.issues), small))
        if r.citations:
            s += [Paragraph("Sources", h2)] + [_p(f"{c.source} - {c.title}", small) for c in r.citations]

    s += [Spacer(1, 10),
          _p("Decision-support output generated automatically. Not medical advice; measures are recommendations "
             "that require approval by the competent authority.", small)]
    doc.build(s)
    return buf.getvalue()
