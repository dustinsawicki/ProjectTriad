"""Deterministic state machine orchestrating the four Foundry agents.

Each transition is a fresh agent run; the previous agent's structured output
is passed in as the user message for the next agent. Tool calls are executed
locally by `TOOL_REGISTRY` and the tool outputs streamed back into the run.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..agents.registry import ensure_agents, get_project_client
from ..tools.registry import TOOL_REGISTRY

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    correlation_id: str
    claim_id: str
    fnol: dict[str, Any] = field(default_factory=dict)
    triage: dict[str, Any] = field(default_factory=dict)
    assessment: dict[str, Any] | None = None
    guardrail: dict[str, Any] | None = None
    route: str = "unknown"


def _run_agent(agent_id: str, user_msg: str, correlation_id: str, timeout_s: float = 90.0) -> str:
    """Run a single agent to completion, executing any tool calls locally."""
    client = get_project_client()
    thread = client.agents.threads.create()
    client.agents.messages.create(thread_id=thread.id, role="user", content=user_msg)
    run = client.agents.runs.create(thread_id=thread.id, agent_id=agent_id)

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)
        status = run.status
        if status == "requires_action":
            outputs = []
            for call in run.required_action.submit_tool_outputs.tool_calls:  # type: ignore[union-attr]
                fn = TOOL_REGISTRY.get(call.function.name)
                args = json.loads(call.function.arguments or "{}")
                try:
                    result = fn(**args) if fn else {"error": f"unknown tool {call.function.name}"}
                except Exception as e:  # noqa: BLE001
                    log.exception("Tool %s failed: %s", call.function.name, e)
                    result = {"error": str(e)}
                outputs.append({"tool_call_id": call.id, "output": json.dumps(result, default=str)})
            client.agents.runs.submit_tool_outputs(thread_id=thread.id, run_id=run.id, tool_outputs=outputs)
        elif status in ("completed", "failed", "cancelled", "expired"):
            break
        else:
            time.sleep(0.5)

    if run.status != "completed":
        raise RuntimeError(f"Agent run did not complete: {run.status} (correlation={correlation_id})")

    msgs = list(client.agents.messages.list(thread_id=thread.id, order="desc", limit=1))
    if not msgs:
        return "{}"
    last = msgs[0]
    parts = [t.text.value for t in last.content if hasattr(t, "text")]
    return "\n".join(parts) if parts else "{}"


def _safe_json(text: str) -> dict[str, Any]:
    text = text.strip().strip("`")
    if text.startswith("json"):
        text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # find first {...} block
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {"_raw": text}


def run_pipeline(claim_id: str, policy_number: str) -> PipelineResult:
    """Drive a single claim through all four agents."""
    correlation_id = f"corr-{uuid.uuid4().hex[:12]}"
    agent_ids = ensure_agents()
    result = PipelineResult(correlation_id=correlation_id, claim_id=claim_id)

    # 1. FNOL & Document
    fnol_input = json.dumps({"claim_id": claim_id, "policy_number": policy_number, "correlation_id": correlation_id})
    fnol_raw = _run_agent(agent_ids["FnolDocumentAgent"], fnol_input, correlation_id)
    result.fnol = _safe_json(fnol_raw)
    if result.fnol.get("validated") is False:
        result.route = "invalid_policy"
        return result

    # 2. Triage & Coverage
    triage_input = json.dumps({"claim_id": claim_id, "fnol_summary": result.fnol, "correlation_id": correlation_id})
    triage_raw = _run_agent(agent_ids["TriageCoverageAgent"], triage_input, correlation_id)
    result.triage = _safe_json(triage_raw)
    result.route = result.triage.get("route", "desk")

    # 3. Assessment (only for stp/desk)
    if result.route in ("stp", "desk"):
        a_input = json.dumps({"claim_id": claim_id, "triage": result.triage, "correlation_id": correlation_id})
        a_raw = _run_agent(agent_ids["AssessmentSettlementAgent"], a_input, correlation_id)
        result.assessment = _safe_json(a_raw)

        # 4. Guardrails — operate over the most recent decision
        # The agent will look up the latest 'settlement' decision via get_decision when given the id
        # We pass the assessment payload so the agent has full context; it queries by decision_id from its rationale.
        g_input = json.dumps({
            "claim_id": claim_id,
            "assessment": result.assessment,
            "correlation_id": correlation_id,
        })
        g_raw = _run_agent(agent_ids["GuardrailsAgent"], g_input, correlation_id)
        result.guardrail = _safe_json(g_raw)

    return result
