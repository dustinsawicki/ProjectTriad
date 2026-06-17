"""Deterministic state machine orchestrating the four Foundry agents.

Uses the new Foundry Agent Service APIs:
- Conversations (replaces threads) for stateful context
- Responses (replaces runs) for agent execution
- Agent references (replaces agent IDs) for targeting agents

Each transition creates a response with the agent_reference; tool calls are
executed locally by `TOOL_REGISTRY` and submitted back as conversation items.

If Foundry is unavailable, falls back to simulation mode for demos.
"""
from __future__ import annotations

import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..config import get_settings
from ..db import SessionLocal
from ..repositories import claims as repo
from ..routers.events import record_event

log = logging.getLogger(__name__)


def _emit(claim_id: str, event_type: str, correlation_id: str, detail: dict | None = None, agent: str | None = None) -> None:
    """Push a pipeline lifecycle event into the supervisor event buffer."""
    record_event({
        "event_id": f"evt-{uuid.uuid4().hex[:12]}",
        "event_type": event_type,
        "claim_id": claim_id,
        "claim_number": f"CLM-{claim_id[:8]}",
        "agent": agent,
        "correlation_id": correlation_id,
        "occurred_utc": datetime.now(timezone.utc).isoformat(),
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


def _simulate_pipeline(claim_id: str, policy_number: str) -> PipelineResult:
    """Simulated agent pipeline for demos when Foundry is unavailable."""
    correlation_id = f"corr-{uuid.uuid4().hex[:12]}"
    result = PipelineResult(correlation_id=correlation_id, claim_id=claim_id)

    # Simulate FNOL processing (1-2s)
    time.sleep(random.uniform(1.0, 2.0))
    result.fnol = {
        "validated": True,
        "policy_number": policy_number,
        "policy_status": "active",
        "documents_processed": random.randint(1, 3),
        "extraction_confidence": round(random.uniform(0.85, 0.99), 2),
    }
    _emit(claim_id, "fnol_complete", correlation_id, result.fnol, agent="FnolDocumentAgent")

    # Simulate Triage (1-3s)
    time.sleep(random.uniform(1.0, 3.0))
    fraud_score = round(random.uniform(0.05, 0.85), 3)
    route = "siu_referral" if fraud_score > 0.7 else random.choice(["fast_track", "standard"])
    result.triage = {
        "route": route,
        "fraud_score": fraud_score,
        "coverage_confirmed": True,
        "priority": random.choice(["low", "medium", "high"]),
        "flags": random.sample(["high_value", "new_policy", "repeat_claimant", "consistent_docs", "low_risk"], k=random.randint(1, 3)),
    }
    result.route = route
    _emit(claim_id, "triage_complete", correlation_id, {"route": route, "fraud_score": fraud_score}, agent="TriageCoverageAgent")

    # Simulate Assessment (2-4s) — only for fast_track/standard
    if route in ("fast_track", "standard"):
        time.sleep(random.uniform(2.0, 4.0))
        settlement = round(random.uniform(3000, 45000), 2)
        result.assessment = {
            "settlement_amount": settlement,
            "confidence": round(random.uniform(0.78, 0.97), 2),
            "method": random.choice(["comparative_analysis", "itemized_review", "model_prediction"]),
            "comparable_claims": random.randint(3, 12),
            "recommendation": "approve" if fraud_score < 0.4 else "review",
        }
        _emit(claim_id, "assessment_complete", correlation_id, {"settlement_amount": settlement}, agent="AssessmentSettlementAgent")

        # Simulate Guardrails (1-2s)
        time.sleep(random.uniform(1.0, 2.0))
        outcome = "pass" if fraud_score < 0.5 else random.choice(["pass", "flag", "block"])
        result.guardrail = {
            "outcome": outcome,
            "rules_checked": random.randint(5, 15),
            "rules_passed": random.randint(4, 15),
            "compliance_score": round(random.uniform(0.85, 1.0), 2),
            "warnings": [] if outcome == "pass" else [random.choice([
                "Settlement exceeds 90th percentile for loss type",
                "Claimant has 2+ claims in rolling 90 days",
                "Repair estimate exceeds vehicle market value",
            ])],
        }
        _emit(claim_id, "guardrail_complete", correlation_id, {"outcome": outcome}, agent="GuardrailsAgent")

    _emit(claim_id, "pipeline_complete", correlation_id, {"route": result.route, "mode": "simulation"})
    return result


def _persist_results(result: PipelineResult) -> None:
    """Write pipeline results back to the database so queue, audit, and supervisor reflect them."""
    try:
        s = SessionLocal()
        cid = uuid.UUID(result.claim_id)

        # Triage decision → route + fraud
        if result.triage:
            repo.set_triage_decision(s, cid, result.triage)
            fraud = result.triage.get("fraud_score")
            if fraud is not None:
                repo.insert_fraud_signal(s, cid, "pipeline_triage", float(fraud), result.triage)

            repo.insert_agent_decision(
                s, claim_id=cid, agent_name="TriageCoverageAgent",
                decision_type="triage", payload=result.triage, status="accepted",
            )
            repo.insert_audit_event(
                s, claim_id=cid, decision_id=None, rule_id=None,
                actor="agent", actor_name="TriageCoverageAgent",
                action="triage_claim",
                outcome=result.triage.get("route", "unknown"),
                rationale=result.triage,
                correlation_id=result.correlation_id,
            )

        # FNOL audit
        if result.fnol:
            repo.insert_agent_decision(
                s, claim_id=cid, agent_name="FnolDocumentAgent",
                decision_type="fnol_validation", payload=result.fnol, status="accepted",
            )
            repo.insert_audit_event(
                s, claim_id=cid, decision_id=None, rule_id=None,
                actor="agent", actor_name="FnolDocumentAgent",
                action="validate_fnol",
                outcome="validated" if result.fnol.get("validated") else "rejected",
                rationale=result.fnol,
                correlation_id=result.correlation_id,
            )

        # Assessment → reserve + settlement
        if result.assessment:
            amt = result.assessment.get("settlement_amount")
            if amt is not None:
                repo.set_reserve(s, cid, float(amt))

            repo.insert_agent_decision(
                s, claim_id=cid, agent_name="AssessmentSettlementAgent",
                decision_type="assessment", payload=result.assessment, status="accepted",
            )
            repo.insert_audit_event(
                s, claim_id=cid, decision_id=None, rule_id=None,
                actor="agent", actor_name="AssessmentAgent",
                action="assess_claim",
                outcome=result.assessment.get("recommendation", "approve"),
                rationale=result.assessment,
                correlation_id=result.correlation_id,
            )

        # Guardrail
        if result.guardrail:
            g_outcome = result.guardrail.get("outcome", "pass")
            repo.insert_agent_decision(
                s, claim_id=cid, agent_name="GuardrailsAgent",
                decision_type="guardrail_check", payload=result.guardrail, status="accepted",
            )
            repo.insert_audit_event(
                s, claim_id=cid, decision_id=None, rule_id=None,
                actor="agent", actor_name="GuardrailsAgent",
                action="guardrail_review",
                outcome=g_outcome,
                rationale=result.guardrail,
                correlation_id=result.correlation_id,
            )

            # Only settle if guardrails pass
            if g_outcome == "pass" and result.assessment:
                amt = result.assessment.get("settlement_amount")
                if amt is not None:
                    repo.settle(s, cid, float(amt))
                    repo.insert_audit_event(
                        s, claim_id=cid, decision_id=None, rule_id=None,
                        actor="system", actor_name="Orchestrator",
                        action="auto_settle",
                        outcome="settled",
                        rationale={"settlement_amount": amt, "route": result.route},
                        correlation_id=result.correlation_id,
                    )

        # Pipeline completion audit
        repo.insert_audit_event(
            s, claim_id=cid, decision_id=None, rule_id=None,
            actor="system", actor_name="Orchestrator",
            action="pipeline_complete",
            outcome=result.route,
            rationale={"route": result.route, "correlation_id": result.correlation_id},
            correlation_id=result.correlation_id,
        )

        s.commit()
    except Exception:  # noqa: BLE001
        log.exception("Failed to persist pipeline results for %s", result.claim_id)
    finally:
        s.close()


def _execute_tool_calls(tool_calls: list[Any]) -> list[dict[str, Any]]:
    """Execute tool calls locally and return output items for the conversation."""
    from ..tools.registry import TOOL_REGISTRY
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
    """Run a single agent to completion using the Responses API with conversations."""
    from ..agents.registry import get_project_client
    client = get_project_client()
    openai = client.get_openai_client()

    conversation = openai.conversations.create(
        metadata={"correlation_id": correlation_id, "agent": agent_name},
    )

    response = openai.responses.create(
        input=[{"type": "message", "role": "user", "content": user_msg}],
        conversation=conversation.id,
        extra_body={
            "agent_reference": {"name": agent_name, "type": "agent_reference"},
        },
    )

    for _ in range(max_turns):
        tool_calls = [item for item in response.output if getattr(item, "type", None) == "function_call"]
        if not tool_calls:
            break
        tool_outputs = _execute_tool_calls(tool_calls)
        response = openai.responses.create(
            input=tool_outputs,
            conversation=conversation.id,
            extra_body={
                "agent_reference": {"name": agent_name, "type": "agent_reference"},
            },
        )

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
    """Drive a single claim through all four agents.

    Tries Foundry Agent Service first; falls back to simulation mode if unavailable.
    """
    # Try live agents first
    try:
        from ..agents.registry import ensure_agents
        settings = get_settings()
        if not settings.foundry_project_endpoint:
            raise ValueError("No Foundry endpoint configured")

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
            g_input = json.dumps({"claim_id": claim_id, "assessment": result.assessment, "correlation_id": correlation_id})
            g_raw = _run_agent(agent_names["GuardrailsAgent"], g_input, correlation_id)
            result.guardrail = _safe_json(g_raw)
            _emit(claim_id, "guardrail_complete", correlation_id, {"outcome": result.guardrail.get("outcome")})

        _emit(claim_id, "pipeline_complete", correlation_id, {"route": result.route})
        _persist_results(result)
        return result

    except Exception as e:  # noqa: BLE001
        log.warning("Foundry agents unavailable (%s), using simulation mode", e)
        sim = _simulate_pipeline(claim_id, policy_number)
        _persist_results(sim)
        return sim
