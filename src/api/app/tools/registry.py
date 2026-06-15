"""Tool implementations exposed to the Foundry agents.

Each function:
- Takes JSON-serializable args (already parsed by the orchestrator).
- Opens its own short-lived DB session via `session_scope()`.
- Returns a JSON-serializable dict that the agent receives as the tool result.

This module is the agents' ONLY way to read or write claim data.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from ..db import session_scope
from ..repositories import claims as repo


# ---- FNOL & Document Agent tools -----------------------------------------

def lookup_policy(policy_number: str) -> dict[str, Any]:
    with session_scope() as s:
        p = repo.get_policy_by_number(s, policy_number)
        if not p:
            return {"found": False}
        return {
            "found": True,
            "policy_id": str(p["PolicyId"]),
            "policy_number": p["PolicyNumber"],
            "product_line": p["ProductLine"],
            "status": p["Status"],
            "effective_date": p["EffectiveDate"].isoformat(),
            "expiration_date": p["ExpirationDate"].isoformat(),
            "coverage": p["CoverageJson"],
        }


def list_documents(claim_id: str) -> dict[str, Any]:
    with session_scope() as s:
        docs = repo.list_documents(s, UUID(claim_id))
        return {"documents": [
            {"document_id": str(d["DocumentId"]), "doc_type": d["DocType"],
             "title": d["Title"], "raw_text": d["RawText"]}
            for d in docs
        ]}


def save_extraction(document_id: str, extracted: dict[str, Any]) -> dict[str, Any]:
    with session_scope() as s:
        repo.update_document_extraction(s, UUID(document_id), extracted)
    return {"ok": True, "document_id": document_id}


# ---- Triage agent tools --------------------------------------------------

def evaluate_coverage(claim_id: str) -> dict[str, Any]:
    with session_scope() as s:
        bundle = repo.get_claim_bundle(s, UUID(claim_id))
        if not bundle:
            return {"error": "claim not found"}
        c, p = bundle["claim"], bundle["policy"]
        return {
            "claim_id": str(c["ClaimId"]),
            "loss_type": c["LossType"],
            "loss_datetime": c["LossDateTime"].isoformat(),
            "reported_amount": float(c["ReportedAmount"]) if c["ReportedAmount"] is not None else None,
            "policy_status": p["Status"],
            "product_line": p["ProductLine"],
            "coverage": p["CoverageJson"],
        }


def find_linked_parties(claim_id: str) -> dict[str, Any]:
    with session_scope() as s:
        # PoC heuristic: derive zip from any document mentioning a 5-digit ZIP isn't worth it for the demo;
        # instead, surface parties that share a phone across the whole book — sufficient to demo link analysis.
        bundle = repo.get_claim_bundle(s, UUID(claim_id))
        if not bundle:
            return {"matches": []}
        # In a real impl we'd resolve this claim's parties from a ClaimParty join; for PoC we sample any
        # party from the same insured zip. For demo richness we return any 3 fraud-ring parties.
        matches = s.execute(  # type: ignore[attr-defined]
            __import__("sqlalchemy").text("""
            SELECT TOP 5 p.PartyId, p.FullName, p.Phone, p.AddressJson
            FROM dbo.Party p
            JOIN (SELECT Phone, COUNT(*) AS n FROM dbo.Party WHERE Phone IS NOT NULL GROUP BY Phone HAVING COUNT(*) >= 3) shared
              ON shared.Phone = p.Phone
            ORDER BY NEWID();
        """)
        ).fetchall()
        return {"matches": [
            {"party_id": str(m.PartyId), "full_name": m.FullName, "phone": m.Phone,
             "address": json.loads(m.AddressJson) if m.AddressJson else None}
            for m in matches
        ]}


def score_fraud(claim_id: str, signal_type: str, score: float, rationale: dict[str, Any]) -> dict[str, Any]:
    with session_scope() as s:
        sid = repo.insert_fraud_signal(s, UUID(claim_id), signal_type, float(score), rationale or {})
    return {"signal_id": str(sid), "score": float(score)}


# ---- Assessment agent tools ----------------------------------------------

def get_documents_with_extractions(claim_id: str) -> dict[str, Any]:
    with session_scope() as s:
        docs = repo.list_documents(s, UUID(claim_id))
        return {"documents": [
            {
                "document_id": str(d["DocumentId"]),
                "doc_type": d["DocType"],
                "title": d["Title"],
                "raw_text": d["RawText"],
                "extracted": d["ExtractedJson"],
            }
            for d in docs
        ]}


def propose_settlement(
    claim_id: str,
    settlement_amount: float,
    rationale: str,
    line_items: list[dict[str, Any]] | None = None,
    deductible_applied: float | None = None,
    document_citations: list[str] | None = None,
) -> dict[str, Any]:
    from ..config import get_settings
    s_cfg = get_settings()
    payload = {
        "settlement_amount": float(settlement_amount),
        "line_items": line_items or [],
        "deductible_applied": deductible_applied,
        "document_citations": document_citations or [],
        "rationale": rationale,
        "model": s_cfg.foundry_model_deployment,
        "version": "2024-08-06",
    }
    with session_scope() as s:
        did = repo.insert_agent_decision(
            s, claim_id=UUID(claim_id), agent_name="AssessmentSettlementAgent",
            decision_type="settlement", payload=payload, status="proposed",
        )
    return {"decision_id": str(did), "status": "proposed"}


def flag_subrogation(claim_id: str, subrogation: bool, reason: str | None = None) -> dict[str, Any]:
    payload = {"subrogation": bool(subrogation), "reason": reason or ""}
    with session_scope() as s:
        did = repo.insert_agent_decision(
            s, claim_id=UUID(claim_id), agent_name="AssessmentSettlementAgent",
            decision_type="escalate" if subrogation else "coverage", payload=payload, status="proposed",
        )
    return {"decision_id": str(did)}


# ---- Guardrails agent tools ----------------------------------------------

def list_active_rules() -> dict[str, Any]:
    with session_scope() as s:
        return {"rules": [
            {"rule_id": str(r["RuleId"]), "rule_code": r["RuleCode"], "category": r["Category"],
             "description": r["Description"], "predicate": r["PredicateJson"], "version": r["Version"]}
            for r in repo.list_active_rules(s)
        ]}


def get_decision(decision_id: str) -> dict[str, Any]:
    from sqlalchemy import text
    with session_scope() as s:
        row = s.execute(text("SELECT * FROM dbo.AgentDecision WHERE DecisionId = :id"), {"id": decision_id}).fetchone()
        if not row:
            return {"found": False}
        d = dict(row._mapping)  # type: ignore[attr-defined]
        bundle = repo.get_claim_bundle(s, d["ClaimId"])
        return {
            "found": True,
            "decision_id": str(d["DecisionId"]),
            "claim_id": str(d["ClaimId"]),
            "agent_name": d["AgentName"],
            "decision_type": d["DecisionType"],
            "payload": json.loads(d["PayloadJson"]) if isinstance(d["PayloadJson"], str) else d["PayloadJson"],
            "status": d["Status"],
            "policy_coverage": bundle["policy"]["CoverageJson"] if bundle else {},
        }


def record_audit_event(
    claim_id: str,
    decision_id: str | None,
    outcome: str,
    rule_code: str | None = None,
    rationale: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with session_scope() as s:
        rule_id = None
        if rule_code:
            r = repo.get_rule_by_code(s, rule_code)
            if r:
                rule_id = r["RuleId"]
        eid = repo.insert_audit_event(
            s,
            claim_id=UUID(claim_id) if claim_id else None,
            decision_id=UUID(decision_id) if decision_id else None,
            rule_id=rule_id,
            actor="agent", actor_name="GuardrailsAgent",
            action=f"guardrail.{rule_code or 'unspecified'}",
            outcome=outcome, rationale=rationale,
            correlation_id=(rationale or {}).get("correlation_id"),
        )
    return {"event_id": str(eid)}


def block_decision(decision_id: str) -> dict[str, Any]:
    with session_scope() as s:
        repo.update_decision_status(s, UUID(decision_id), "blocked")
    return {"ok": True}


# ---- Registry for the orchestrator --------------------------------------

TOOL_REGISTRY = {
    "lookup_policy": lookup_policy,
    "list_documents": list_documents,
    "save_extraction": save_extraction,
    "evaluate_coverage": evaluate_coverage,
    "find_linked_parties": find_linked_parties,
    "score_fraud": score_fraud,
    "get_documents_with_extractions": get_documents_with_extractions,
    "propose_settlement": propose_settlement,
    "flag_subrogation": flag_subrogation,
    "list_active_rules": list_active_rules,
    "get_decision": get_decision,
    "record_audit_event": record_audit_event,
    "block_decision": block_decision,
}
