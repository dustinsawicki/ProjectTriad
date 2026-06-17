"""Deterministic state machine orchestrating the four Foundry agents.

Uses the new Foundry Agent Service APIs:
- Conversations (replaces threads) for stateful context
- Responses (replaces runs) for agent execution
- Agent references (replaces agent IDs) for targeting agents

Each transition creates a response with the agent_reference; tool calls are
executed locally by `TOOL_REGISTRY` and submitted back as conversation items.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..agents.registry import ensure_agents, get_project_client
from ..routers.events import record_event
from ..tools.registry import TOOL_REGISTRY

log = logging.getLogger(__name__)


def _emit(claim_id: str, event_type: str, correlation_id: str, detail: dict | None = None) -> None:
    """Push a pipeline lifecycle event into the supervisor event buffer."""
    record_event({
        "event_id": f"evt-{uuid.uuid4().hex[:12]}",
        "event_type": event_type,
        "claim_id": claim_id,
        "claim_number": f"CLM-{claim_id[:8]}",
        "correlation_id": correlation_id,
        "occurred_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "detail": detail or {},
    })


@dataclass
class PipelineResult:
    correlation_id: str
    claim_id: str
    fnol: dict[str, Any] = field(default_factory=dict)
    triage: dict[str, Any] = field(default_factory=dict)
    assessment: dict[str, Any] | None = None
    guardrail: dict[str, Any] | None = None
    route: str = "unknown"


def _execute_tool_calls(tool_calls: list[Any]) -> list[dict[str, Any]]:
    """Execute tool calls locally and return output items for the conversation."""
    outputs = []
    for call in tool_calls:
        fn = TOOL_REGISTRY.get(call.name)
        args = json.loads(call.arguments or "{}")
        try:
            result = fn(**args) if fn else {"error": f"unknown tool {call.name}"}
        except Exception as e:  # noqa: BLE001
            log.exception("Tool %s failed: %s", call.name, e)
            result = {"error": str(e)}
        outputs.append({
            "type": "function_call_output",
            "call_id": call.call_id,
            "output": json.dumps(result, default=str),
        })
    return outputs


def _run_agent(agent_name: str, user_msg: str, correlation_id: str, max_turns: int = 10) -> str:
    """Run a single agent to completion using the Responses API with conversations.

    Creates a conversation, sends the user message, and loops to handle
    tool calls until the agent produces a final text response.
    """
    client = get_project_client()
    openai = client.get_openai_client()

    # Create a conversation (replaces thread)
    conversation = openai.conversations.create(
        metadata={"correlation_id": correlation_id, "agent": agent_name},
    )

    # Send initial user message and get first response
    response = openai.responses.create(
        input=[{"type": "message", "role": "user", "content": user_msg}],
        conversation=conversation.id,
        extra_body={
            "agent_reference": {"name": agent_name, "type": "agent_reference"},
        },
    )

    # Tool call loop: handle requires_action by executing tools and resubmitting
    for _ in range(max_turns):
        # Collect any tool calls from the response output
        tool_calls = [item for item in response.output if getattr(item, "type", None) == "function_call"]
        if not tool_calls:
            break

        # Execute tools and submit results back
        tool_outputs = _execute_tool_calls(tool_calls)
        response = openai.responses.create(
            input=tool_outputs,
            conversation=conversation.id,
            extra_body={
                "agent_reference": {"name": agent_name, "type": "agent_reference"},
            },
        )

    # Extract final text from response output
    parts = []
    for item in response.output:
        if getattr(item, "type", None) == "message":
            for content in item.content:
                if hasattr(content, "text"):
                    parts.append(content.text)
    return "\n".join(parts) if parts else "{}"


def _safe_json(text: str) -> dict[str, Any]:
    text = text.strip().strip("`")
    if text.startswith("json"):
        text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
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
    agent_names = ensure_agents()
    result = PipelineResult(correlation_id=correlation_id, claim_id=claim_id)

    # 1. FNOL & Document
    fnol_input = json.dumps({"claim_id": claim_id, "policy_number": policy_number, "correlation_id": correlation_id})
    fnol_raw = _run_agent(agent_names["FnolDocumentAgent"], fnol_input, correlation_id)
    result.fnol = _safe_json(fnol_raw)
    _emit(claim_id, "fnol_complete", correlation_id, result.fnol)
    if result.fnol.get("validated") is False:
        result.route = "invalid_policy"
        _emit(claim_id, "policy_invalid", correlation_id)
        return result

    # 2. Triage & Coverage
    triage_input = json.dumps({"claim_id": claim_id, "fnol_summary": result.fnol, "correlation_id": correlation_id})
    triage_raw = _run_agent(agent_names["TriageCoverageAgent"], triage_input, correlation_id)
    result.triage = _safe_json(triage_raw)
    result.route = result.triage.get("route", "desk")
    _emit(claim_id, "triage_complete", correlation_id, {"route": result.route, "fraud_score": result.triage.get("fraud_score")})

    # 3. Assessment (only for stp/desk)
    if result.route in ("stp", "desk"):
        a_input = json.dumps({"claim_id": claim_id, "triage": result.triage, "correlation_id": correlation_id})
        a_raw = _run_agent(agent_names["AssessmentSettlementAgent"], a_input, correlation_id)
        result.assessment = _safe_json(a_raw)
        _emit(claim_id, "assessment_complete", correlation_id, {"settlement_amount": result.assessment.get("settlement_amount")})

        # 4. Guardrails
        g_input = json.dumps({
            "claim_id": claim_id,
            "assessment": result.assessment,
            "correlation_id": correlation_id,
        })
        g_raw = _run_agent(agent_names["GuardrailsAgent"], g_input, correlation_id)
        result.guardrail = _safe_json(g_raw)
        _emit(claim_id, "guardrail_complete", correlation_id, {"outcome": result.guardrail.get("outcome")})

    _emit(claim_id, "pipeline_complete", correlation_id, {"route": result.route})
    return result
