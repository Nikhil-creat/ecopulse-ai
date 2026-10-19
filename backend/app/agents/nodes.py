import logging
import statistics
from datetime import datetime, timezone

from langchain_core.runnables import RunnableConfig

from app.agents.llm import narrate
from app.agents.schemas import (AgentState, Citation, CnnCrossCheck, IntegrityReport, PolicyAction, PolicyPlan,
                                RiskReport, StationIntegrity)
from app.agents.thresholds import CATEGORY_TO_LEVEL, CPCB_24H, LEVEL_ORDER, WHO_2021_24H
from app.agents.tools import ToolBox
from app.schemas.sensor import ReadingOut
from app.services.aqi import aqi_category, compute_aqi

log = logging.getLogger(__name__)


def _tb(config: RunnableConfig) -> ToolBox:
    return config["configurable"]["toolbox"]


# --------------------------------------------------------------------------- 1. Data Integrity Agent
def check_station(r: ReadingOut, series: list[ReadingOut], city_median_pm25: float | None,
                  now: datetime | None = None) -> StationIntegrity:
    now = now or datetime.now(timezone.utc)
    issues: list[str] = []
    penalty = 0.0

    age_h = (now - r.time).total_seconds() / 3600
    if age_h > 2:
        issues.append(f"stale reading ({age_h:.1f} h old)")
        penalty += 0.3
    if r.quality_flag == 2:
        issues.append("failed ingestion quality check")
        penalty += 1.0
    elif r.quality_flag == 1:
        issues.append("flagged suspect at ingestion")
        penalty += 0.3
    if r.pm25 is not None and r.pm10 is not None and r.pm25 > r.pm10 * 1.05:
        issues.append("PM2.5 exceeds PM10 (physically inconsistent)")
        penalty += 0.3

    hist = [s.pm25 for s in series[:-1] if s.pm25 is not None]
    if r.pm25 is not None and len(hist) >= 8:
        med = statistics.median(hist)
        mad = statistics.median(abs(x - med) for x in hist) * 1.4826 or 1.0
        z = (r.pm25 - med) / max(mad, 1.0)
        if abs(z) > 6:
            issues.append(f"sudden spike/drop vs 24h baseline (robust z={z:.1f})")
            penalty += 0.35
    recent = [s.pm25 for s in series[-8:] if s.pm25 is not None]
    if len(recent) >= 8 and len(set(recent)) == 1:
        issues.append("flatline: identical PM2.5 values (possible stuck sensor)")
        penalty += 0.4
    if r.pm25 is not None and city_median_pm25 is not None and city_median_pm25 > 20:
        if r.pm25 > 4 * city_median_pm25 + 10 or r.pm25 < city_median_pm25 / 4:
            issues.append(f"spatial outlier vs city median ({city_median_pm25:.0f})")
            penalty += 0.3

    score = round(max(0.0, 1.0 - penalty), 2)
    return StationIntegrity(station_id=r.station_id, score=score, trusted=score >= 0.5 and r.quality_flag < 2,
                            issues=issues)


async def integrity_node(state: AgentState, config: RunnableConfig) -> dict:
    tb = _tb(config)
    readings = await tb.latest_readings(city=state.get("city"), station_id=state.get("station_id"))
    pm25s = [r.pm25 for r in readings if r.pm25 is not None]
    median = statistics.median(pm25s) if len(pm25s) >= 3 else None
    results = [check_station(r, await tb.recent_series(r.station_id, 24), median) for r in readings]
    trusted = [x.station_id for x in results if x.trusted]
    summary = (f"{len(trusted)}/{len(results)} stations trusted"
               + (f"; issues: {sum(len(x.issues) for x in results)}" if results else "; no readings found"))
    report = IntegrityReport(stations=results, trusted_station_ids=trusted, summary=summary)
    update: dict = {"readings": readings, "integrity": report, "trace": [f"integrity: {summary}"]}
    if not trusted:
        update["halt_reason"] = "no trusted sensor data available" if readings else "no sensor readings found"
    return update


def route_after_integrity(state: AgentState) -> str:
    return "halt" if state.get("halt_reason") else "risk"


async def halt_node(state: AgentState, config: RunnableConfig) -> dict:
    return {"trace": [f"halted: {state.get('halt_reason')}"]}


# --------------------------------------------------------------------------- 2. Forecast & Health Risk Agent
def cross_check_cnn(aqi: float | None, smog: float | None, captured_at: datetime | None,
                    model_source: str | None, now: datetime | None = None) -> CnnCrossCheck:
    now = now or datetime.now(timezone.utc)
    if smog is None or aqi is None:
        return CnnCrossCheck(status="unavailable", note="no satellite/CNN analysis available for this region")
    if captured_at and (now - captured_at).total_seconds() > 24 * 3600:
        return CnnCrossCheck(status="stale", note="latest imagery analysis is older than 24 h")
    caveat = " (heuristic scoring, untrained CNN: low confidence)" if model_source == "heuristic" else ""
    if (aqi >= 200 and smog <= 30) or (aqi <= 100 and smog >= 60):
        return CnnCrossCheck(status="discrepancy",
                             note=f"sensor AQI {aqi:.0f} vs imagery smog index {smog:.0f}: sources disagree{caveat}")
    return CnnCrossCheck(status="consistent", note=f"sensor AQI {aqi:.0f} agrees with smog index {smog:.0f}{caveat}")


def _advice(level: str) -> list[str]:
    base = {
        "low": ["Normal outdoor activity is generally fine."],
        "moderate": ["People with asthma/COPD, children and older adults should reduce prolonged intense outdoor exertion."],
        "high": ["Sensitive groups (asthma, COPD, heart disease, children, older adults) should avoid outdoor exercise.",
                 "Everyone else should limit prolonged outdoor exertion; keep reliever inhalers accessible."],
        "very_high": ["Move exercise indoors; minimise time outside and avoid busy roads.",
                      "Use a well-fitted FFP2/N95-type respirator if you must go out; keep windows closed."],
        "severe": ["Stay indoors where possible with windows closed and an air purifier running.",
                   "Seek medical care for worsening breathlessness or chest pain."],
    }
    return base[level]


async def risk_node(state: AgentState, config: RunnableConfig) -> dict:
    tb = _tb(config)
    trusted_ids = set(state["integrity"].trusted_station_ids)
    trusted = [r for r in state["readings"] if r.station_id in trusted_ids]

    def med(field: str) -> float | None:
        vals = [getattr(r, field) for r in trusted if getattr(r, field) is not None]
        return round(statistics.median(vals), 1) if vals else None

    pm25, pm10 = med("pm25"), med("pm10")
    cur_aqi = med("aqi") or compute_aqi(pm25, pm10)

    worst = max(trusted, key=lambda r: r.pm25 or 0)
    fc = await tb.forecast(worst.station_id, "pm25")
    peak_aqi = compute_aqi(fc.peak_value, None) if fc else None
    effective = max(x for x in (cur_aqi, peak_aqi) if x is not None) if (cur_aqi or peak_aqi) else None
    category = aqi_category(effective) if effective is not None else None
    level = CATEGORY_TO_LEVEL.get(category or "", "low")

    region = state.get("city") or (trusted[0].city or "")
    sat = await tb.satellite_context(region) if region else None
    cnn = cross_check_cnn(cur_aqi, sat.smog_severity_index if sat else None,
                          sat.captured_at if sat else None, (sat.meta or {}).get("model_source") if sat else None)

    citations: list[Citation] = []
    try:
        seen: set[int] = set()
        for q in (f"{category or 'air quality'} air quality health advice asthma outdoor exercise",
                  "PM2.5 24-hour guideline value WHO CPCB standard"):
            for h in await tb.guidelines(q, k=2):
                if h.id not in seen:
                    seen.add(h.id)
                    citations.append(Citation(source=h.source, title=h.doc_title, snippet=h.content[:240]))
    except Exception as exc:  # noqa: BLE001 - RAG may be unseeded
        log.warning("guideline retrieval failed: %r", exc)

    fact = (f"city={region}; current_aqi={cur_aqi}; pm25={pm25}; pm10={pm10}; effective_aqi_incl_forecast={effective}; "
            f"category={category}; forecast_model={fc.model if fc else None}; "
            f"forecast_points={[ (p.horizon_hours, p.predicted) for p in fc.points] if fc else None}; "
            f"cnn_cross_check={cnn.status}: {cnn.note}")
    narrative = await narrate(
        "Write a 3-4 sentence health-risk summary for the public and authorities. Mention the forecast model name "
        "and the satellite cross-check status.",
        fact + "\nguidelines: " + " | ".join(c.snippet for c in citations)) or (
        f"{region}: AQI {cur_aqi} ({category}); PM2.5 {pm25} ug/m3"
        + (f"; forecast peak PM2.5 {fc.peak_value:.0f} ug/m3 ({fc.model})" if fc else "; no forecast available")
        + f". Satellite cross-check: {cnn.status}.")

    report = RiskReport(
        level=level, current_aqi=cur_aqi, category=category, current_pm25=pm25,
        who_pm25_exceedance=round(pm25 / WHO_2021_24H["pm25"], 2) if pm25 is not None else None,
        cpcb_pm25_exceedance=round(pm25 / CPCB_24H["pm25"], 2) if pm25 is not None else None,
        forecast=fc, cnn_cross_check=cnn, vulnerable_group_advice=_advice(level), citations=citations,
        narrative=narrative)
    return {"risk": report, "trace": [f"risk: level={level}, aqi={cur_aqi}, forecast={'yes' if fc else 'no'}, cnn={cnn.status}"]}


# --------------------------------------------------------------------------- 3. Policy & Mitigation Agent
def plan_actions(level: str, pm25: float | None, pm10: float | None, no2: float | None) -> list[PolicyAction]:
    A = PolicyAction
    acts: list[PolicyAction] = []
    idx = LEVEL_ORDER.index(level)
    if idx >= 1:
        acts.append(A(category="communication", action="Publish a public air-quality advisory for sensitive groups",
                      rationale="AQI is above the Satisfactory band", priority="immediate"))
    if idx >= 2:
        acts += [
            A(category="construction", action="Enforce dust control: water sprinkling, covered material, road sweeping",
              rationale="Stage-1 style response for Poor air", priority="within_24h"),
            A(category="public_health", action="Advise schools to move outdoor activity indoors",
              rationale="Children are a sensitive group", priority="within_24h")]
    if idx >= 3:
        acts += [
            A(category="traffic", action="Reroute heavy diesel freight around the urban core and prioritise arterial signal timing",
              rationale="Reduce combustion emissions and idling in residential/school zones", priority="immediate"),
            A(category="industry", action="Intensify emission enforcement on industrial units and restrict diesel generator sets",
              rationale="Very Poor air warrants stricter source control", priority="within_24h")]
    if idx >= 4:
        acts += [
            A(category="construction", action="Pause non-essential construction and demolition",
              rationale="Severe episode", priority="immediate"),
            A(category="industry", action="Consult the pollution control board on temporary throttling of high-emission units",
              rationale="Severe episode; requires authority orders", priority="immediate")]
    if pm10 and pm25 and pm10 > 2.5 * pm25 and idx >= 1:
        acts.append(A(category="construction", action="Prioritise road-dust mitigation",
                      rationale=f"PM10/PM2.5 ratio is high ({pm10 / pm25:.1f}), indicating coarse dust", priority="within_24h"))
    if no2 and no2 > CPCB_24H["no2"] and idx >= 1:
        acts.append(A(category="traffic", action="Target traffic management at congestion hotspots",
                      rationale=f"NO2 {no2:.0f} ug/m3 exceeds the CPCB 24h standard", priority="within_24h"))
    return acts


async def policy_node(state: AgentState, config: RunnableConfig) -> dict:
    tb = _tb(config)
    risk: RiskReport = state["risk"]
    trusted = [r for r in state["readings"] if r.station_id in set(state["integrity"].trusted_station_ids)]

    def med(field: str) -> float | None:
        v = [getattr(r, field) for r in trusted if getattr(r, field) is not None]
        return statistics.median(v) if v else None

    actions = plan_actions(risk.level, med("pm25"), med("pm10"), med("no2"))
    sources: list[str] = []
    snippets: list[str] = []
    try:
        for h in await tb.guidelines(f"graded response measures {risk.category or ''} traffic industry construction",
                                     doc_type="policy", k=3):
            sources.append(f"{h.source}: {h.doc_title}")
            snippets.append(h.content[:300])
    except Exception as exc:  # noqa: BLE001
        log.warning("policy retrieval failed: %r", exc)

    narrative = await narrate(
        "Write a 3-4 sentence action brief for city authorities summarising the recommended measures. State that "
        "measures are recommendations requiring official approval.",
        f"risk_level={risk.level}; actions={[a.action for a in actions]}; playbook: {' | '.join(snippets)}") or (
        f"Risk level {risk.level}: {len(actions)} recommended measure(s). These are decision-support recommendations "
        "and require approval by the competent authority.")
    return {"policy": PolicyPlan(actions=actions, sources=sorted(set(sources)), narrative=narrative),
            "trace": [f"policy: {len(actions)} actions"]}
