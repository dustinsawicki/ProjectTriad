"""All SQL access for the PoC. The only layer that touches Azure SQL directly.

Kept thin and explicit (raw SQL via SQLAlchemy `text`) so future swap-in of a
real claims platform requires changing only this module.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


# ---- helpers -------------------------------------------------------------

def _row_to_dict(row) -> dict[str, Any]:
    d = dict(row._mapping)  # type: ignore[attr-defined]
    # decode JSON columns when present
    for k in ("CoverageJson", "TriageDecisionJson", "ExtractedJson", "RationaleJson", "PayloadJson", "AddressJson", "PredicateJson"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except json.JSONDecodeError:
                pass
    return d


def _rows(result) -> list[dict[str, Any]]:
    return [_row_to_dict(r) for r in result.fetchall()]


# ---- claims --------------------------------------------------------------

def list_claims(
    session: Session,
    *,
    status: str | None = None,
    route: str | None = None,
    min_fraud_score: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    sql = """
    WITH top_fraud AS (
        SELECT ClaimId, MAX(Score) AS top_fraud_score
        FROM dbo.FraudSignal GROUP BY ClaimId
    )
    SELECT c.*, tf.top_fraud_score
    FROM dbo.Claim c
    LEFT JOIN top_fraud tf ON tf.ClaimId = c.ClaimId
    WHERE (:status IS NULL OR c.Status = :status)
      AND (:min_fraud IS NULL OR tf.top_fraud_score >= :min_fraud)
    ORDER BY c.CreatedUtc DESC
    OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY;
    """
    rows = _rows(session.execute(text(sql), {
        "status": status, "min_fraud": min_fraud_score, "offset": offset, "limit": limit,
    }))
    # route is encoded inside TriageDecisionJson
    if route:
        rows = [r for r in rows if (r.get("TriageDecisionJson") or {}).get("route") == route]
    return rows


def get_claim_bundle(session: Session, claim_id: UUID) -> dict[str, Any] | None:
    claim = session.execute(text("SELECT * FROM dbo.Claim WHERE ClaimId = :id"), {"id": str(claim_id)}).fetchone()
    if claim is None:
        return None
    claim_d = _row_to_dict(claim)
    pol = session.execute(text("SELECT * FROM dbo.Policy WHERE PolicyId = :p"), {"p": str(claim_d["PolicyId"])}).fetchone()
    docs    = _rows(session.execute(text("SELECT * FROM dbo.Document      WHERE ClaimId = :id ORDER BY IngestedUtc"), {"id": str(claim_id)}))
    fraud   = _rows(session.execute(text("SELECT * FROM dbo.FraudSignal   WHERE ClaimId = :id ORDER BY CreatedUtc"), {"id": str(claim_id)}))
    decs    = _rows(session.execute(text("SELECT * FROM dbo.AgentDecision WHERE ClaimId = :id ORDER BY CreatedUtc"), {"id": str(claim_id)}))
    audit   = _rows(session.execute(text("SELECT * FROM dbo.AuditEvent    WHERE ClaimId = :id ORDER BY CreatedUtc"), {"id": str(claim_id)}))
    return {
        "claim":     claim_d,
        "policy":    _row_to_dict(pol) if pol else None,
        "documents": docs,
        "fraud_signals": fraud,
        "decisions": decs,
        "audit":     audit,
    }


def get_policy_by_number(session: Session, policy_number: str) -> dict[str, Any] | None:
    row = session.execute(text("SELECT * FROM dbo.Policy WHERE PolicyNumber = :n"), {"n": policy_number}).fetchone()
    return _row_to_dict(row) if row else None


def create_claim(
    session: Session,
    *,
    policy_id: UUID,
    loss_datetime: datetime,
    loss_type: str,
    reported_amount: float | None,
) -> tuple[UUID, str]:
    cid = uuid.uuid4()
    # ClaimNumber: pick MAX+1
    nxt = session.execute(text("""
        SELECT ISNULL(MAX(CAST(SUBSTRING(ClaimNumber, 5, 12) AS INT)), 100000) + 1 AS n FROM dbo.Claim
    """)).scalar_one()
    claim_no = f"CLM-{nxt}"
    session.execute(text("""
        INSERT INTO dbo.Claim (ClaimId, PolicyId, ClaimNumber, LossDateTime, LossType, Status, ReportedAmount)
        VALUES (:id, :pid, :no, :loss, :lt, 'open', :amt)
    """), {
        "id": str(cid), "pid": str(policy_id), "no": claim_no,
        "loss": loss_datetime, "lt": loss_type, "amt": reported_amount,
    })
    return cid, claim_no


def insert_document(session: Session, *, claim_id: UUID, doc_type: str, title: str | None, raw_text: str) -> UUID:
    did = uuid.uuid4()
    session.execute(text("""
        INSERT INTO dbo.Document (DocumentId, ClaimId, DocType, Title, RawText) VALUES (:id, :cid, :t, :title, :raw)
    """), {"id": str(did), "cid": str(claim_id), "t": doc_type, "title": title, "raw": raw_text})
    return did


def update_document_extraction(session: Session, document_id: UUID, extracted: dict[str, Any]) -> None:
    session.execute(text("UPDATE dbo.Document SET ExtractedJson = :j WHERE DocumentId = :id"),
                    {"j": json.dumps(extracted), "id": str(document_id)})


def list_documents(session: Session, claim_id: UUID) -> list[dict[str, Any]]:
    return _rows(session.execute(text("SELECT * FROM dbo.Document WHERE ClaimId = :id"), {"id": str(claim_id)}))


def set_triage_decision(session: Session, claim_id: UUID, triage: dict[str, Any]) -> None:
    session.execute(text("""
        UPDATE dbo.Claim SET TriageDecisionJson = :j, Status = 'triaged', UpdatedUtc = SYSUTCDATETIME() WHERE ClaimId = :id
    """), {"j": json.dumps(triage), "id": str(claim_id)})


def set_reserve(session: Session, claim_id: UUID, reserve: float) -> None:
    session.execute(text("UPDATE dbo.Claim SET ReserveAmount = :r, Status = 'assessed', UpdatedUtc = SYSUTCDATETIME() WHERE ClaimId = :id"),
                    {"r": reserve, "id": str(claim_id)})


def settle(session: Session, claim_id: UUID, settled: float) -> None:
    session.execute(text("UPDATE dbo.Claim SET SettledAmount = :s, Status = 'settled', UpdatedUtc = SYSUTCDATETIME() WHERE ClaimId = :id"),
                    {"s": settled, "id": str(claim_id)})


# ---- fraud / decisions / rules / audit -----------------------------------

def insert_fraud_signal(session: Session, claim_id: UUID, signal_type: str, score: float, rationale: dict[str, Any]) -> UUID:
    sid = uuid.uuid4()
    session.execute(text("""
        INSERT INTO dbo.FraudSignal (SignalId, ClaimId, SignalType, Score, RationaleJson) VALUES (:id, :cid, :t, :s, :j)
    """), {"id": str(sid), "cid": str(claim_id), "t": signal_type, "s": score, "j": json.dumps(rationale)})
    return sid


def insert_agent_decision(session: Session, *, claim_id: UUID, agent_name: str, decision_type: str, payload: dict[str, Any], status: str = "proposed") -> UUID:
    did = uuid.uuid4()
    session.execute(text("""
        INSERT INTO dbo.AgentDecision (DecisionId, ClaimId, AgentName, DecisionType, PayloadJson, Status) VALUES (:id, :cid, :n, :t, :p, :s)
    """), {"id": str(did), "cid": str(claim_id), "n": agent_name, "t": decision_type, "p": json.dumps(payload), "s": status})
    return did


def update_decision_status(session: Session, decision_id: UUID, status: str) -> None:
    session.execute(text("UPDATE dbo.AgentDecision SET Status = :s WHERE DecisionId = :id"), {"s": status, "id": str(decision_id)})


def list_active_rules(session: Session) -> list[dict[str, Any]]:
    return _rows(session.execute(text("SELECT * FROM dbo.PolicyRule WHERE IsActive = 1")))


def get_rule_by_code(session: Session, code: str) -> dict[str, Any] | None:
    row = session.execute(text("SELECT * FROM dbo.PolicyRule WHERE RuleCode = :c AND IsActive = 1"), {"c": code}).fetchone()
    return _row_to_dict(row) if row else None


def insert_audit_event(
    session: Session,
    *,
    claim_id: UUID | None,
    decision_id: UUID | None,
    rule_id: UUID | None,
    actor: str,
    actor_name: str,
    action: str,
    outcome: str,
    rationale: dict[str, Any] | None,
    correlation_id: str | None,
) -> UUID:
    eid = uuid.uuid4()
    session.execute(text("""
        INSERT INTO dbo.AuditEvent (EventId, ClaimId, DecisionId, RuleId, Actor, ActorName, Action, Outcome, RationaleJson, CorrelationId)
        VALUES (:eid, :cid, :did, :rid, :act, :name, :a, :o, :j, :corr)
    """), {
        "eid": str(eid),
        "cid": str(claim_id) if claim_id else None,
        "did": str(decision_id) if decision_id else None,
        "rid": str(rule_id) if rule_id else None,
        "act": actor, "name": actor_name, "a": action, "o": outcome,
        "j": json.dumps(rationale) if rationale else None,
        "corr": correlation_id,
    })
    return eid


# ---- link analysis (used by Triage agent's tool) -------------------------

def find_parties_sharing_identifier(session: Session, phone: str | None, address_zip: str | None) -> list[dict[str, Any]]:
    if not phone and not address_zip:
        return []
    sql = """
    SELECT TOP 25 PartyId, FullName, Phone, AddressJson, Role
    FROM dbo.Party
    WHERE (:phone IS NOT NULL AND Phone = :phone)
       OR (:zip   IS NOT NULL AND AddressJson LIKE '%' + :zip + '%')
    """
    return _rows(session.execute(text(sql), {"phone": phone, "zip": address_zip}))
