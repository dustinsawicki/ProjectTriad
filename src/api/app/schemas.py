"""Pydantic v2 request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=False)


class PolicyOut(_Base):
    policy_id: UUID = Field(alias="PolicyId")
    policy_number: str = Field(alias="PolicyNumber")
    product_line: str = Field(alias="ProductLine")
    coverage: dict[str, Any] = Field(alias="CoverageJson")
    status: str = Field(alias="Status")


class DocumentOut(_Base):
    document_id: UUID = Field(alias="DocumentId")
    doc_type: str = Field(alias="DocType")
    title: str | None = Field(default=None, alias="Title")
    raw_text: str = Field(alias="RawText")
    extracted: dict[str, Any] | None = Field(default=None, alias="ExtractedJson")
    ingested_utc: datetime = Field(alias="IngestedUtc")


class FraudSignalOut(_Base):
    signal_id: UUID = Field(alias="SignalId")
    signal_type: str = Field(alias="SignalType")
    score: float = Field(alias="Score")
    rationale: dict[str, Any] = Field(alias="RationaleJson")
    created_utc: datetime = Field(alias="CreatedUtc")


class AgentDecisionOut(_Base):
    decision_id: UUID = Field(alias="DecisionId")
    agent_name: str = Field(alias="AgentName")
    decision_type: str = Field(alias="DecisionType")
    payload: dict[str, Any] = Field(alias="PayloadJson")
    status: str = Field(alias="Status")
    created_utc: datetime = Field(alias="CreatedUtc")


class AuditEventOut(_Base):
    event_id: UUID = Field(alias="EventId")
    actor: str = Field(alias="Actor")
    actor_name: str = Field(alias="ActorName")
    action: str = Field(alias="Action")
    outcome: str = Field(alias="Outcome")
    rationale: dict[str, Any] | None = Field(default=None, alias="RationaleJson")
    correlation_id: str | None = Field(default=None, alias="CorrelationId")
    created_utc: datetime = Field(alias="CreatedUtc")


class ClaimSummaryOut(_Base):
    claim_id: UUID = Field(alias="ClaimId")
    claim_number: str = Field(alias="ClaimNumber")
    loss_type: str = Field(alias="LossType")
    status: str = Field(alias="Status")
    reported_amount: float | None = Field(default=None, alias="ReportedAmount")
    reserve_amount: float | None = Field(default=None, alias="ReserveAmount")
    settled_amount: float | None = Field(default=None, alias="SettledAmount")
    assigned_adjuster: str | None = Field(default=None, alias="AssignedAdjuster")
    created_utc: datetime = Field(alias="CreatedUtc")
    top_fraud_score: float | None = None
    route: str | None = None


class ClaimBundleOut(BaseModel):
    claim: ClaimSummaryOut
    policy: PolicyOut
    documents: list[DocumentOut]
    fraud_signals: list[FraudSignalOut]
    decisions: list[AgentDecisionOut]
    audit: list[AuditEventOut]


class DocumentIn(BaseModel):
    doc_type: str
    title: str | None = None
    raw_text: str


class CreateClaimIn(BaseModel):
    policy_number: str
    loss_datetime: datetime
    loss_type: str
    reported_amount: float | None = None
    documents: list[DocumentIn] = Field(default_factory=list)


class CreateClaimOut(BaseModel):
    claim_id: UUID
    claim_number: str
    pipeline_correlation_id: str


class ApproveClaimIn(BaseModel):
    settlement_amount: float
    notes: str | None = None


class SendBackIn(BaseModel):
    decision_id: UUID
    notes: str
