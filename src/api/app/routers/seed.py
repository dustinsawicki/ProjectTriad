"""Seed demo data into Azure SQL for PoC demonstrations."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from random import choice, randint, uniform

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_session

router = APIRouter(prefix="/api/seed", tags=["seed"])

_LOSS_TYPES = ["auto_collision", "auto_comp", "home_property", "liability"]
_STATUSES = ["open", "triaged", "assessed", "settled", "denied"]
_ROUTES = ["fast_track", "standard", "siu_referral"]
_ADJUSTERS = ["Sarah Chen", "Mike Rodriguez", "Emily Watson", "James Park", "Lisa Taylor"]


def _seed_policies(s: Session) -> list[str]:
    """Insert demo policies, return policy IDs."""
    policies = []
    for i in range(1, 11):
        pid = str(uuid.uuid4())
        policies.append(pid)
        s.execute(text("""
            INSERT INTO dbo.Policy (PolicyId, PolicyNumber, ProductLine, EffectiveDate,
                ExpirationDate, PremiumAnnual, CoverageJson, Status)
            VALUES (:id, :num, :prod, :eff, :exp, :prem, :cov, 'active')
        """), {
            "id": pid,
            "num": f"POL-2024-{1000 + i}",
            "prod": choice(["auto", "home", "umbrella"]),
            "eff": "2024-01-01",
            "exp": "2025-01-01",
            "prem": round(uniform(800, 5000), 2),
            "cov": json.dumps({"deductible": choice([500, 1000, 2500]), "limit": choice([50000, 100000, 250000, 500000])}),
        })
    return policies


def _seed_claims(s: Session, policy_ids: list[str]) -> list[dict]:
    """Insert demo claims, return claim info."""
    claims = []
    now = datetime.utcnow()
    for i in range(1, 26):
        cid = str(uuid.uuid4())
        status = choice(_STATUSES)
        loss_type = choice(_LOSS_TYPES)
        reported = round(uniform(1500, 85000), 2)
        route = choice(_ROUTES)
        triage_json = json.dumps({"route": route, "confidence": round(uniform(0.7, 0.99), 2)})

        s.execute(text("""
            INSERT INTO dbo.Claim (ClaimId, PolicyId, ClaimNumber, LossDateTime, LossType,
                Status, ReportedAmount, ReserveAmount, SettledAmount, TriageDecisionJson,
                AssignedAdjuster, CreatedUtc, UpdatedUtc)
            VALUES (:id, :pol, :num, :loss_dt, :lt, :st, :rep, :res, :set, :triage,
                :adj, :created, :updated)
        """), {
            "id": cid,
            "pol": choice(policy_ids),
            "num": f"CLM-2024-{2000 + i}",
            "loss_dt": (now - timedelta(days=randint(1, 90))).isoformat(),
            "lt": loss_type,
            "st": status,
            "rep": reported,
            "res": round(reported * uniform(0.6, 1.0), 2) if status != "open" else None,
            "set": round(reported * uniform(0.5, 0.95), 2) if status == "settled" else None,
            "triage": triage_json if status != "open" else None,
            "adj": choice(_ADJUSTERS),
            "created": (now - timedelta(days=randint(1, 60))).isoformat(),
            "updated": (now - timedelta(days=randint(0, 5))).isoformat(),
        })
        claims.append({"id": cid, "num": f"CLM-2024-{2000 + i}", "status": status, "loss_type": loss_type})
    return claims


def _seed_fraud_signals(s: Session, claims: list[dict]) -> None:
    """Insert fraud signals for some claims."""
    for c in claims:
        if uniform(0, 1) > 0.4:  # ~60% of claims get fraud signals
            for _ in range(randint(1, 3)):
                s.execute(text("""
                    INSERT INTO dbo.FraudSignal (SignalId, ClaimId, SignalType, Score, RationaleJson)
                    VALUES (:id, :cid, :stype, :score, :rationale)
                """), {
                    "id": str(uuid.uuid4()),
                    "cid": c["id"],
                    "stype": choice(["rule", "model", "link_analysis"]),
                    "score": round(uniform(0.1, 0.95), 4),
                    "rationale": json.dumps({"reason": choice([
                        "Multiple claims in 30-day window",
                        "Reported amount exceeds historical median by 3x",
                        "Address linked to prior fraud ring",
                        "Inconsistent damage description vs photos",
                        "New policy with immediate high-value claim",
                    ])}),
                })


def _seed_decisions(s: Session, claims: list[dict]) -> list[str]:
    """Insert agent decisions for processed claims."""
    decision_ids = []
    for c in claims:
        if c["status"] not in ("open",):
            for agent, dtype in [
                ("triage-agent", "coverage"),
                ("fraud-detector", "escalate"),
                ("settlement-agent", "settlement"),
                ("guardrail-agent", "guardrail"),
            ]:
                if c["status"] == "triaged" and agent in ("settlement-agent", "guardrail-agent"):
                    continue
                did = str(uuid.uuid4())
                decision_ids.append(did)
                s.execute(text("""
                    INSERT INTO dbo.AgentDecision (DecisionId, ClaimId, AgentName, DecisionType,
                        PayloadJson, Status)
                    VALUES (:id, :cid, :agent, :dtype, :payload, :status)
                """), {
                    "id": did,
                    "cid": c["id"],
                    "agent": agent,
                    "dtype": dtype,
                    "payload": json.dumps({"recommendation": choice(["approve", "deny", "escalate", "review"]), "confidence": round(uniform(0.7, 0.99), 2)}),
                    "status": choice(["proposed", "approved", "blocked"]),
                })
    return decision_ids


def _seed_audit_events(s: Session, claims: list[dict]) -> None:
    """Insert audit events for claims."""
    for c in claims:
        if c["status"] == "open":
            continue
        # Agent processing events
        for agent, action in [
            ("triage-agent", "claim.triage"),
            ("fraud-detector", "claim.fraud_check"),
            ("settlement-agent", "claim.assess"),
            ("guardrail-agent", "claim.guardrail_check"),
        ]:
            s.execute(text("""
                INSERT INTO dbo.AuditEvent (EventId, ClaimId, DecisionId, RuleId,
                    Actor, ActorName, Action, Outcome, RationaleJson, CorrelationId)
                VALUES (:id, :cid, NULL, NULL, 'agent', :actor, :action, :outcome,
                    :rationale, :corr)
            """), {
                "id": str(uuid.uuid4()),
                "cid": c["id"],
                "actor": agent,
                "action": action,
                "outcome": choice(["pass", "block", "approve"]),
                "rationale": json.dumps({"summary": f"{agent} processed {c['num']}"}),
                "corr": f"corr-{c['num']}",
            })


@router.post("")
def seed_demo_data(s: Session = Depends(get_session)) -> dict:
    """Seed the database with demo data for PoC demonstrations."""
    # Check if already seeded
    result = s.execute(text("SELECT COUNT(*) FROM dbo.Policy"))
    count = result.scalar()
    if count and count > 0:
        return {"status": "already_seeded", "policies": count}

    policy_ids = _seed_policies(s)
    claims = _seed_claims(s, policy_ids)
    _seed_fraud_signals(s, claims)
    _seed_decisions(s, claims)
    _seed_audit_events(s, claims)
    s.commit()

    return {
        "status": "seeded",
        "policies": len(policy_ids),
        "claims": len(claims),
    }


@router.delete("")
def clear_demo_data(s: Session = Depends(get_session)) -> dict:
    """Clear all demo data."""
    s.execute(text("EXEC dbo.usp_TruncateAll"))
    s.commit()
    return {"status": "cleared"}
