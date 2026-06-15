-- Agentic Claims Processing PoC — Azure SQL schema
-- Single datasource for the entire PoC.
-- Run with sqlcmd / pyodbc against the target DB; safe to re-run (drops + recreates).

SET XACT_ABORT ON;
SET NOCOUNT ON;

------------------------------------------------------------
-- Drop in FK-safe order
------------------------------------------------------------
IF OBJECT_ID('dbo.AuditEvent','U')      IS NOT NULL DROP TABLE dbo.AuditEvent;
IF OBJECT_ID('dbo.AgentDecision','U')   IS NOT NULL DROP TABLE dbo.AgentDecision;
IF OBJECT_ID('dbo.FraudSignal','U')     IS NOT NULL DROP TABLE dbo.FraudSignal;
IF OBJECT_ID('dbo.Document','U')        IS NOT NULL DROP TABLE dbo.Document;
IF OBJECT_ID('dbo.Claim','U')           IS NOT NULL DROP TABLE dbo.Claim;
IF OBJECT_ID('dbo.Party','U')           IS NOT NULL DROP TABLE dbo.Party;
IF OBJECT_ID('dbo.Policy','U')          IS NOT NULL DROP TABLE dbo.Policy;
IF OBJECT_ID('dbo.PolicyRule','U')      IS NOT NULL DROP TABLE dbo.PolicyRule;

------------------------------------------------------------
-- Tables
------------------------------------------------------------
CREATE TABLE dbo.Policy (
    PolicyId        UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_Policy PRIMARY KEY DEFAULT NEWID(),
    PolicyNumber    NVARCHAR(32)     NOT NULL UNIQUE,
    ProductLine     NVARCHAR(20)     NOT NULL,   -- auto | home | umbrella
    EffectiveDate   DATE             NOT NULL,
    ExpirationDate  DATE             NOT NULL,
    PremiumAnnual   DECIMAL(10,2)    NOT NULL,
    CoverageJson    NVARCHAR(MAX)    NOT NULL,   -- JSON document
    Status          NVARCHAR(20)     NOT NULL,   -- active | lapsed | cancelled
    CreatedUtc      DATETIME2(3)     NOT NULL DEFAULT SYSUTCDATETIME()
);

CREATE TABLE dbo.Party (
    PartyId    UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_Party PRIMARY KEY DEFAULT NEWID(),
    Role       NVARCHAR(20)     NOT NULL,   -- insured | claimant | witness | provider
    FullName   NVARCHAR(160)    NOT NULL,
    Email      NVARCHAR(160)    NULL,
    Phone      NVARCHAR(32)     NULL,
    AddressJson NVARCHAR(MAX)   NULL,
    DOB        DATE             NULL,
    CreatedUtc DATETIME2(3)     NOT NULL DEFAULT SYSUTCDATETIME()
);
CREATE INDEX IX_Party_Phone   ON dbo.Party(Phone);

CREATE TABLE dbo.Claim (
    ClaimId            UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_Claim PRIMARY KEY DEFAULT NEWID(),
    PolicyId           UNIQUEIDENTIFIER NOT NULL CONSTRAINT FK_Claim_Policy REFERENCES dbo.Policy(PolicyId),
    ClaimNumber        NVARCHAR(32)     NOT NULL UNIQUE,
    LossDateTime       DATETIME2(0)     NOT NULL,
    LossType           NVARCHAR(40)     NOT NULL,    -- auto_collision | auto_comp | home_property | liability
    Status             NVARCHAR(20)     NOT NULL,    -- open | triaged | assessed | settled | denied
    ReportedAmount     DECIMAL(12,2)    NULL,
    ReserveAmount      DECIMAL(12,2)    NULL,
    SettledAmount      DECIMAL(12,2)    NULL,
    TriageDecisionJson NVARCHAR(MAX)    NULL,
    AssignedAdjuster   NVARCHAR(160)    NULL,
    CreatedUtc         DATETIME2(3)     NOT NULL DEFAULT SYSUTCDATETIME(),
    UpdatedUtc         DATETIME2(3)     NOT NULL DEFAULT SYSUTCDATETIME()
);
CREATE INDEX IX_Claim_PolicyId ON dbo.Claim(PolicyId);
CREATE INDEX IX_Claim_Status   ON dbo.Claim(Status);
CREATE INDEX IX_Claim_Created  ON dbo.Claim(CreatedUtc DESC);

CREATE TABLE dbo.Document (
    DocumentId    UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_Document PRIMARY KEY DEFAULT NEWID(),
    ClaimId       UNIQUEIDENTIFIER NOT NULL CONSTRAINT FK_Doc_Claim REFERENCES dbo.Claim(ClaimId),
    DocType       NVARCHAR(40)     NOT NULL,    -- police_report | estimate | photo_caption | medical | email
    Title         NVARCHAR(200)    NULL,
    RawText       NVARCHAR(MAX)    NOT NULL,
    ExtractedJson NVARCHAR(MAX)    NULL,
    IngestedUtc   DATETIME2(3)     NOT NULL DEFAULT SYSUTCDATETIME()
);
CREATE INDEX IX_Document_ClaimId ON dbo.Document(ClaimId);

CREATE TABLE dbo.FraudSignal (
    SignalId      UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_FraudSignal PRIMARY KEY DEFAULT NEWID(),
    ClaimId       UNIQUEIDENTIFIER NOT NULL CONSTRAINT FK_Fraud_Claim REFERENCES dbo.Claim(ClaimId),
    SignalType    NVARCHAR(30)     NOT NULL,    -- rule | model | link_analysis
    Score         DECIMAL(5,4)     NOT NULL,    -- 0.0 .. 1.0
    RationaleJson NVARCHAR(MAX)    NOT NULL,
    CreatedUtc    DATETIME2(3)     NOT NULL DEFAULT SYSUTCDATETIME()
);
CREATE INDEX IX_Fraud_ClaimId ON dbo.FraudSignal(ClaimId);

CREATE TABLE dbo.AgentDecision (
    DecisionId   UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_AgentDecision PRIMARY KEY DEFAULT NEWID(),
    ClaimId      UNIQUEIDENTIFIER NOT NULL CONSTRAINT FK_Dec_Claim REFERENCES dbo.Claim(ClaimId),
    AgentName    NVARCHAR(80)     NOT NULL,
    DecisionType NVARCHAR(40)     NOT NULL,    -- coverage | settlement | denial | escalate | guardrail
    PayloadJson  NVARCHAR(MAX)    NOT NULL,
    Status       NVARCHAR(20)     NOT NULL,    -- proposed | approved | blocked | edited
    CreatedUtc   DATETIME2(3)     NOT NULL DEFAULT SYSUTCDATETIME()
);
CREATE INDEX IX_Dec_Claim ON dbo.AgentDecision(ClaimId);

CREATE TABLE dbo.PolicyRule (
    RuleId        UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_PolicyRule PRIMARY KEY DEFAULT NEWID(),
    RuleCode      NVARCHAR(40)     NOT NULL UNIQUE,
    Category      NVARCHAR(40)     NOT NULL,    -- fair_claims | state_reg | coverage_limit | anti_discrim
    Description   NVARCHAR(400)    NOT NULL,
    PredicateJson NVARCHAR(MAX)    NOT NULL,
    Version       NVARCHAR(20)     NOT NULL,
    IsActive      BIT              NOT NULL DEFAULT 1
);

CREATE TABLE dbo.AuditEvent (
    EventId       UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_AuditEvent PRIMARY KEY DEFAULT NEWID(),
    ClaimId       UNIQUEIDENTIFIER NULL CONSTRAINT FK_Audit_Claim REFERENCES dbo.Claim(ClaimId),
    DecisionId    UNIQUEIDENTIFIER NULL CONSTRAINT FK_Audit_Decision REFERENCES dbo.AgentDecision(DecisionId),
    RuleId        UNIQUEIDENTIFIER NULL CONSTRAINT FK_Audit_Rule REFERENCES dbo.PolicyRule(RuleId),
    Actor         NVARCHAR(20)     NOT NULL,    -- agent | human
    ActorName     NVARCHAR(160)    NOT NULL,
    Action        NVARCHAR(80)     NOT NULL,
    Outcome       NVARCHAR(20)     NOT NULL,    -- pass | block | approve | edit | deny
    RationaleJson NVARCHAR(MAX)    NULL,
    CorrelationId NVARCHAR(64)     NULL,
    CreatedUtc    DATETIME2(3)     NOT NULL DEFAULT SYSUTCDATETIME()
);
CREATE INDEX IX_Audit_ClaimId  ON dbo.AuditEvent(ClaimId);
CREATE INDEX IX_Audit_Created  ON dbo.AuditEvent(CreatedUtc DESC);
GO

------------------------------------------------------------
-- Append-only trigger on AuditEvent (no UPDATE, no DELETE)
------------------------------------------------------------
CREATE OR ALTER TRIGGER dbo.trg_AuditEvent_Immutable
ON dbo.AuditEvent
INSTEAD OF UPDATE, DELETE
AS
BEGIN
    RAISERROR('AuditEvent is append-only.', 16, 1);
    ROLLBACK TRANSACTION;
END
GO

------------------------------------------------------------
-- Helper procs
------------------------------------------------------------
CREATE OR ALTER PROCEDURE dbo.usp_TruncateAll
AS
BEGIN
    SET NOCOUNT ON;
    -- Trigger blocks DELETE on AuditEvent; disable for reseed only
    DISABLE TRIGGER dbo.trg_AuditEvent_Immutable ON dbo.AuditEvent;
    DELETE FROM dbo.AuditEvent;
    ENABLE  TRIGGER dbo.trg_AuditEvent_Immutable ON dbo.AuditEvent;
    DELETE FROM dbo.AgentDecision;
    DELETE FROM dbo.FraudSignal;
    DELETE FROM dbo.Document;
    DELETE FROM dbo.Claim;
    DELETE FROM dbo.Party;
    DELETE FROM dbo.Policy;
    DELETE FROM dbo.PolicyRule;
END
GO

CREATE OR ALTER PROCEDURE dbo.usp_GetClaimBundle
    @ClaimId UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;
    SELECT * FROM dbo.Claim          WHERE ClaimId   = @ClaimId;
    SELECT * FROM dbo.Policy         WHERE PolicyId  = (SELECT PolicyId FROM dbo.Claim WHERE ClaimId = @ClaimId);
    SELECT * FROM dbo.Document       WHERE ClaimId   = @ClaimId ORDER BY IngestedUtc;
    SELECT * FROM dbo.FraudSignal    WHERE ClaimId   = @ClaimId ORDER BY CreatedUtc;
    SELECT * FROM dbo.AgentDecision  WHERE ClaimId   = @ClaimId ORDER BY CreatedUtc;
    SELECT * FROM dbo.AuditEvent     WHERE ClaimId   = @ClaimId ORDER BY CreatedUtc;
END
GO

------------------------------------------------------------
-- Create DB principals for the API and Web Container App managed identities.
-- The seed script substitutes the names at runtime.
------------------------------------------------------------
-- Placeholder; the seed runner executes the dynamic CREATE USER FROM EXTERNAL PROVIDER
-- against the API's MI principal after deployment.
