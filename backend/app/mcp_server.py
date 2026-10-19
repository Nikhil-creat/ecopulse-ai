"""EcoPulse MCP server: exposes air-quality tools to any Model Context Protocol client.
Run: python -m app.mcp_server   (streamable HTTP on :8765, bound to localhost by compose)."""
from mcp.server.fastmcp import FastMCP

from app.agents.graph import run_pipeline
from app.agents.schemas import AgentRequest
from app.agents.tools import ToolBox
from app.db.session import SessionLocal

mcp = FastMCP("ecopulse", host="0.0.0.0", port=8765)


@mcp.tool()
async def get_air_quality(city: str) -> list[dict]:
    """Latest validated sensor readings (AQI, PM2.5, PM10, NO2, CO, temperature) for each station in a city."""
    async with SessionLocal() as s:
        return [r.model_dump(mode="json") for r in await ToolBox(s).latest_readings(city=city) if r.quality_flag < 2]


@mcp.tool()
async def get_forecast(station_id: str, pollutant: str = "pm25") -> dict:
    """Forecast at +6/12/24/48/72 h with confidence bounds. pollutant: pm25|pm10|no2|aqi|temperature."""
    async with SessionLocal() as s:
        fc = await ToolBox(s).forecast(station_id, pollutant)  # type: ignore[arg-type]
        return fc.model_dump() if fc else {"error": "not enough history"}


@mcp.tool()
async def assess_city_risk(city: str) -> dict:
    """Run the Integrity -> Health Risk -> Policy agents and return risk level, advice and recommended measures."""
    async with SessionLocal() as s:
        return (await run_pipeline(s, AgentRequest(city=city))).model_dump(mode="json")


@mcp.tool()
async def search_guidelines(query: str, k: int = 3) -> list[dict]:
    """Hybrid (vector + full-text) search over WHO / CPCB guidelines and health advisories."""
    async with SessionLocal() as s:
        hits = await ToolBox(s).guidelines(query, k=min(k, 8))
        return [{"source": h.source, "title": h.doc_title, "content": h.content} for h in hits]


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
