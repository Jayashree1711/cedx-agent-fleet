# Agent Topology Architecture - CASE_ID: CEDX-3E31C1 (E-commerce Operations)

The Tiny CEDX Agent Fleet governs the processing and validation of e-commerce orders, ensuring that stock allocation, address checking, carrier rating, and fraud assessment are executed with strict independent verification.

Below is the structured topology mapping agent roles, message schemas, and state validation paths.

## Agent Roster & Directed Calling Graph

```mermaid
graph TD
    %% Define Node Styles
    classDef orchestrator fill:#2b3e50,stroke:#3b5998,stroke-width:2px,color:#fff;
    classDef worker fill:#1e3d2f,stroke:#2e6b4e,stroke-width:2px,color:#fff;
    classDef verifier fill:#4d1e2f,stroke:#8b2e3e,stroke-width:2px,color:#fff;
    classDef database fill:#333,stroke:#666,stroke-dasharray: 5 5,color:#ccc;
    classDef tool fill:#444,stroke:#888,color:#eee;

    %% Elements
    Orchestrator[Orchestrator Agent<br/>role: orchestrator]:::orchestrator
    Worker[Worker Agent<br/>role: worker / Fulfillment Planner]:::worker
    Verifier[Verifier Agent<br/>role: verifier / Independent Auditor]:::verifier
    DB[(SQLite Persistent State<br/>out/pipeline.db)]:::database
    Tools[Deterministic Tool Layer<br/>Inventory, Address, Carrier, Fraud]:::tool

    %% Flow/Contracts
    Orchestrator -->|1. Ingestion State| DB
    Orchestrator -->|2. Event: WorkerInput| Worker
    Worker -->|3. Synthesizes Tools| Tools
    Worker -->|4. Proposal: WorkerOutput| Orchestrator
    Orchestrator -->|5. Audit Query| Verifier
    Verifier -->|6. Verdict: VerifierVerdict| Orchestrator
    
    %% Overrule loop
    Verifier -.->|Reject / Overrule| Worker
    Orchestrator -->|7. Append Event Log| DB
```

### 1. Orchestrator Agent (`orchestrator`)
* **Role Summary:** Coordinates workflow progression through sequential `PipelineState` transitions. It routes typed event messages, enforces policy boundaries (step and cost limits), manages repair loops upon Verifier rejection, and runs the Model Router.
* **Contracts:** 
  * Input: Ingested order records from SQLite.
  * Output: Transformed `PipelineState` to next workflow stage or routed exceptions to `out/exception_queue.json`.
  * Permissions (`can_call`): `["worker", "verifier"]`

### 2. Worker Agent (`worker`)
* **Role Summary:** Acts as the Fulfillment Planning Agent. It queries the deterministic Tool Layer to synthesize carrier rates, stock availability, and address checks to draft a structured fulfillment package.
* **Contracts:**
  * Input: `WorkerInput` (normalized record + tools outputs).
  * Output: `WorkerOutput` (Pydantic model containing stock, carrier selection, shipping cost, address verification status, fraud risk score, and a drafted branded package).
  * Permissions (`can_call`): `[]` (receives instructions exclusively from Orchestrator).

### 3. Verifier Agent (`verifier`)
* **Role Summary:** Acts as the Independent Critic and Auditor. It reviews the Worker's drafted package directly against the normalized source order and deterministic tools outputs. Operating without access to the Worker's internal reasoning, it validates details (e.g. flagging hallucinated carriers like `"SpaceX Rocket"`) and possesses authority to overrule the proposal.
* **Contracts:**
  * Input: Normalized record + Worker's `delivered_fields`.
  * Output: `VerifierVerdict` (pass/fail verdict, status, and detail discrepancies).
  * Permissions (`can_call`): `[]` (independent critic role).

---

## State Machine Transition Path

The system enforces a governed state machine to prevent records from bypassing compliance checkpoints:

$$\text{INGESTED} \longrightarrow \text{NORMALIZED} \longrightarrow \text{VALIDATED} \longrightarrow \text{ASSEMBLED} \longrightarrow \text{VERIFIED} \longrightarrow \text{OPS\_APPROVED} \longrightarrow \text{COMPLIANCE\_APPROVED (conditional)} \longrightarrow \text{DELIVERED}$$

1. **INGESTED:** Loaded into SQLite with input hash.
2. **NORMALIZED:** Mapped schema-drift fields.
3. **VALIDATED:** Checked for STALE, MISSING_INPUT, and OUTLIER.
4. **ASSEMBLED:** Worker drafted package.
5. **VERIFIED:** Verifier certified correctness.
6. **OPS_APPROVED:** Operator signed off.
7. **COMPLIANCE_APPROVED:** If amount $\ge$ $45,000$, compliance officer signs off (otherwise skips).
8. **DELIVERED:** Written to `out/packages/` and cryptographically chained to `out/audit.json`.
