# TrustClaims — Demo Guide

> **Audience**: Stakeholders, leadership, technical reviewers
> **Duration**: ~15 minutes (or ~5 min fast-track)
> **Environment**: Azure Container Apps — Sweden Central

---

## 1. Prerequisites

| Item | Detail |
|------|--------|
| **Web URL** | `https://ca-web-ljiihlefub3f4.blackforest-6516eaf5.swedencentral.azurecontainerapps.io` |
| **API URL** | `https://ca-api-ljiihlefub3f4.blackforest-6516eaf5.swedencentral.azurecontainerapps.io` |
| **Browser** | Edge or Chrome (latest) |
| **Auth** | Bypassed for PoC — no login required |

---

## 2. Demo Flow

### 2.1 Dashboard Overview (3 min)

1. Open the **Web URL** above — you land on the **Dashboard**.
2. Walk through the **KPI cards** across the top:
   - **Total Claims** — volume of claims in the system
   - **Open / Settled / Denied** — current pipeline status
   - **SIU Referrals** — claims flagged for Special Investigations Unit
   - **Total Reserve** — outstanding financial exposure
   - **Avg Fraud Score** — mean fraud probability across all claims
3. Scroll down to the **charts**:
   - **Claims by Status** (donut) — shows pipeline distribution
   - **Top Loss Types** (horizontal bar) — collision, theft, weather, etc.
   - **Fraud Score Distribution** (histogram) — most claims cluster low; tail shows high-risk
   - **Claims Over Time** (area) — intake volume trend
   - **Routing Breakdown** (pie) — STP vs. desk vs. field vs. SIU
4. Point out the **Financial Summary** card:
   - Reported → Reserve → Settled → Savings
5. Show the **Pipeline Health** progress bars:
   - Conversion rates between pipeline stages and denial rate

> **Talking point**: _"This dashboard gives operations leadership a single-pane view of the entire claims pipeline — volume, risk exposure, and processing health — all updated in real time."_

---

### 2.2 Claims Queue (4 min)

1. Click **Claims** in the top nav.
2. Highlight the **filter bar** at the top:
   - Set **Status** → `open` to see only unprocessed claims
   - Set **Route** → `siu` to see fraud-flagged claims
   - Set **Min Fraud** → `0.70` to surface high-risk cases
3. Point out the **color-coded badges**:
   - Status pills: sky (open), indigo (triaged), amber (assessed), green (settled), red (denied)
   - Route: red **SIU** badge stands out for fraud referrals
4. Click any **claim number** (e.g., `CLM-000042`) to open the claim detail view.
5. On the detail page, walk through:
   - Policy and party information
   - Loss description and reported amount
   - Agent decision trail (triage → assessment → settlement/denial)
   - Fraud signals and scores

> **Talking point**: _"Adjusters see a prioritized, filterable queue. The system has already triaged, assessed, and routed each claim — the adjuster reviews and approves the AI's recommendation."_

---

### 2.3 Audit Log (3 min)

1. Click **Audit** in the top nav.
2. Scroll through the event log showing every agent action:
   - **When** — timestamp of the event
   - **Actor** — which AI agent (Triage, Assessment, SIU, Supervisor)
   - **Action** — what it did (e.g., `triage_claim`, `assess_liability`, `flag_fraud`)
   - **Outcome** — allow / block / escalate
   - **Rationale** — JSON payload showing the agent's reasoning
3. Point out the **outcome badges**: green (allow) vs. red (block)

> **Talking point**: _"Every AI decision is fully auditable. Regulators and compliance teams can trace exactly what each agent decided, when, and why — with the reasoning preserved."_

---

### 2.4 SIU Graph (2 min — optional)

1. Navigate to **Web URL** `/siu/graph?claim_id=<any-claim-id>`
2. Show the **force-directed network graph** linking:
   - Claims ↔ Parties ↔ Policies ↔ Addresses ↔ Phone numbers
3. Highlight clusters that indicate potential fraud rings

> **Talking point**: _"The SIU graph surfaces hidden relationships across claims — shared addresses, phone numbers, or parties that may indicate organized fraud."_

---

### 2.5 Supervisor Replay (2 min — optional)

1. Navigate to **Web URL** `/supervisor`
2. Show the supervisor workbook with:
   - Agent performance metrics
   - Decision override capabilities
   - Live event stream

---

## 3. Fast-Track Demo (5 min)

If time is short, hit these three screens only:

| # | Screen | Key Message |
|---|--------|-------------|
| 1 | **Dashboard** | _"Real-time operational intelligence"_ |
| 2 | **Claims Queue** (filter to SIU) | _"AI-triaged, risk-prioritized queue"_ |
| 3 | **Audit Log** | _"Full transparency and regulatory compliance"_ |

---

## 4. Architecture Highlights (for technical audience)

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Next.js 14, React 18, Recharts | Modern SPA with server components |
| **API** | FastAPI (Python 3.12) | RESTful endpoints, agent orchestration |
| **Database** | Azure SQL | Claims, policies, parties, audit events |
| **Compute** | Azure Container Apps | Serverless containers, auto-scaling |
| **Registry** | Azure Container Registry | Private image hosting |
| **Identity** | Managed Identity | No secrets in code or config |
| **Infrastructure** | Bicep + `azd` | Full IaC, one-command deployment |

### Additional v2 Services (when enabled)
- **Cosmos DB** — Link-graph fraud detection
- **Event Hubs** — Event-driven claim processing
- **Blob Storage** — Document/photo storage
- **AI Search** — RAG over historical claims corpus
- **Document Intelligence** — OCR for uploaded documents
- **External APIs** — 6 mock services (ISO, weather, police, AVM, medical, payment)

---

## 5. Key Differentiators

1. **Agentic AI** — Multiple specialized agents (Triage, Assessment, SIU, Supervisor) collaborate autonomously
2. **Human-in-the-loop** — Agents recommend; humans approve
3. **Full auditability** — Every decision logged with rationale
4. **Event-driven** — Decoupled processing via Event Hubs
5. **Graph-based fraud detection** — Network analysis surfaces fraud rings
6. **One-command deployment** — `azd up` provisions everything

---

## 6. Common Questions

**Q: Is the data real?**
A: No — all data is synthetically generated. The yellow banner at the top of every page confirms this.

**Q: How do I reset the data?**
A: Run `python infra/data/gen_sql.py --reseed` to regenerate all synthetic claims, parties, and audit events.

**Q: Can I deploy this to my own subscription?**
A: Yes — clone the repo, run `azd init` then `azd up`. All infrastructure is defined in Bicep.

**Q: What model powers the agents?**
A: The agents are designed for GPT-4o. In the PoC, agent decisions are pre-seeded to avoid API costs.

---

*Generated for TrustClaims PoC — dustinsawicki/ProjectTriad*
