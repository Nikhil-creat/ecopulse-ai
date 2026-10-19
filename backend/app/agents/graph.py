from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes import halt_node, integrity_node, policy_node, risk_node, route_after_integrity
from app.agents.schemas import AgentRequest, AgentRunResult, AgentState
from app.agents.tools import ToolBox
from app.models import AuditLog


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("integrity", integrity_node)
    g.add_node("risk", risk_node)
    g.add_node("policy", policy_node)
    g.add_node("halt", halt_node)
    g.add_edge(START, "integrity")
    g.add_conditional_edges("integrity", route_after_integrity, {"risk": "risk", "halt": "halt"})
    g.add_edge("risk", "policy")
    g.add_edge("policy", END)
    g.add_edge("halt", END)
    return g.compile()


_graph = None


async def run_pipeline(session: AsyncSession, req: AgentRequest) -> AgentRunResult:
    global _graph
    _graph = _graph or build_graph()
    scope = req.station_id or req.city or ""
    state = await _graph.ainvoke({"city": req.city, "station_id": req.station_id, "trace": []},
                                 config={"configurable": {"toolbox": ToolBox(session)}})
    result = AgentRunResult(scope=scope, halted=bool(state.get("halt_reason")), halt_reason=state.get("halt_reason"),
                            integrity=state.get("integrity"), risk=state.get("risk"), policy=state.get("policy"),
                            trace=state.get("trace", []))
    session.add(AuditLog(actor="agent_pipeline", actor_type="agent", action="run_pipeline", entity_type="scope",
                         entity_id=scope, details={"halted": result.halted,
                                                   "risk_level": result.risk.level if result.risk else None,
                                                   "trace": result.trace}))
    await session.commit()
    return result
