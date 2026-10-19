import operator
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field, model_validator


class AgentRequest(BaseModel):
    city: str | None = None
    station_id: str | None = None

    @model_validator(mode="after")
    def _one(self) -> "AgentRequest":
        if not (self.city or self.station_id):
            raise ValueError("provide city or station_id")
        return self


class StationIntegrity(BaseModel):
    station_id: str
    score: float = Field(ge=0, le=1)
    trusted: bool
    issues: list[str]


class IntegrityReport(BaseModel):
    stations: list[StationIntegrity]
    trusted_station_ids: list[str]
    summary: str


class Citation(BaseModel):
    source: str
    title: str
    snippet: str


class CnnCrossCheck(BaseModel):
    status: Literal["consistent", "discrepancy", "stale", "unavailable"]
    note: str


class ForecastPoint(BaseModel):
    horizon_hours: int
    predicted: float
    lower: float
    upper: float


class ForecastSummary(BaseModel):
    station_id: str
    pollutant: str
    model: str
    points: list[ForecastPoint]
    peak_value: float


RiskLevel = Literal["low", "moderate", "high", "very_high", "severe"]


class RiskReport(BaseModel):
    level: RiskLevel
    current_aqi: float | None
    category: str | None
    current_pm25: float | None
    who_pm25_exceedance: float | None  # multiple of the WHO 24h guideline
    cpcb_pm25_exceedance: float | None  # multiple of the CPCB 24h standard
    forecast: ForecastSummary | None
    cnn_cross_check: CnnCrossCheck
    vulnerable_group_advice: list[str]
    citations: list[Citation]
    narrative: str


class PolicyAction(BaseModel):
    category: Literal["traffic", "industry", "construction", "public_health", "communication"]
    action: str
    rationale: str
    priority: Literal["immediate", "within_24h", "within_72h"]


class PolicyPlan(BaseModel):
    actions: list[PolicyAction]
    requires_human_approval: bool = True
    sources: list[str]
    narrative: str


class AgentRunResult(BaseModel):
    scope: str
    halted: bool
    halt_reason: str | None = None
    integrity: IntegrityReport | None = None
    risk: RiskReport | None = None
    policy: PolicyPlan | None = None
    trace: list[str]


class AgentState(TypedDict, total=False):
    city: str | None
    station_id: str | None
    readings: list[Any]  # ReadingOut
    integrity: IntegrityReport
    risk: RiskReport
    policy: PolicyPlan
    halt_reason: str | None
    trace: Annotated[list[str], operator.add]
