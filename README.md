# Tiny CEDX Agent Fleet - CASE_ID: CEDX-3E31C1

This is a production-grade multi-agent fleet designed for governing e-commerce operations. It handles order ingestion, schema-driven normalization, address validation, carrier rating, stock allocation, and governed double-approvals, capturing a full append-only audit trail.

---

## 1. Industry & Scope
* **Industry:** E-commerce Operations
* **Scope:** Governs the lifecycle of customer orders: ingesting from Shopify feeds, emails, or PDF invoices; performing deterministic tool validations; planning fulfillment packaging via LLM reasoning; conducting independent critic reviews; and executing double-approvals before delivering packages.
* **Tier:** Production
* **CASE_ID:** `CEDX-3E31C1`

---

## 2. Agent Topology
Our agent fleet is composed of three cooperating agents with typed communication contracts:
1. **Orchestrator Agent (`orchestrator`):** Implemented in [orchestration.py](file:///C:/Users/Jayashree/.gemini/antigravity/scratch/cedx-agent-fleet/fleet/orchestration.py). Coordinates events, budgets, state transitions, and router actions.
2. **Worker Agent (`worker`):** Implemented in [assembly.py](file:///C:/Users/Jayashree/.gemini/antigravity/scratch/cedx-agent-fleet/fleet/assembly.py). Fulfillment Planning Agent that queries the deterministic Tool Layer to draft fulfillment proposals.
3. **Verifier Agent (`verifier`):** Implemented in [review.py](file:///C:/Users/Jayashree/.gemini/antigravity/scratch/cedx-agent-fleet/fleet/review.py). Critic agent checking Worker's outputs for discrepancies and hallucinations.

All interfaces and contracts are defined in [agents.py](file:///C:/Users/Jayashree/.gemini/antigravity/scratch/cedx-agent-fleet/fleet/agents.py) and validated using Pydantic contracts.

---

## 3. How to Run
Run the uniform pipeline using Docker Compose or python directly:
```bash
# Build and run using Docker Compose (runs demo and self-verify)
docker compose up --build

# Run pipeline locally (Replay mode using committed transcripts)
python main.py --replay_llm true

# Run verify_audit gate check
python verify_audit.py
```
Outputs are written to:
- `out/packages/` (Branded packages JSONs)
- `out/audit.json` (Governed audit trail conforming to schema)
- `out/exception_queue.json` (Quarantined exception records)

---

## 4. Controls
Grading probes can be invoked directly:
* `make demo`: Runs the full fleet pipeline in offline replay mode.
* `make verify`: Validates `out/audit.json` structure and hashes.
* `make trace ID=<id>`: Prints the agent trace logs for a specific record.
* `make eval`: Runs evaluation harness and prints agent quality scores.
* `make replay ID=<id>`: Reconstructs record lineage from the audit trail.
* `make probe-approval`: Asserts that delivering an unapproved record is refused.
* `make probe-agent-failure`: Confirms the Verifier catches hallucinated carriers.
* `make probe-budget`: Verifies that budget breaches raise `BUDGET_EXCEEDED`.
* `make probe-append-only`: Verifies audit event chain prev_hash integrity.
* `make probe-idempotency`: Validates double execution yields no duplicates.

---

## 5. Planted-Problem Handling
The system handles the following planted problems:
* **Class A (Blocking):**
  - `STALE`: Deadline before `PIPELINE_NOW` (e.g. `REC-011`).
  - `MISSING_INPUT`: Null values for required fields (e.g. `REC-012`).
  - `OUTLIER`: Extreme amount outlier calculated dynamically via IQR (e.g. `REC-013`).
  - `INJECTION_BLOCKED`: Prompts containing bypass attempts caught by Injection Firewall (e.g. `REC-014`).
  - `LOW_CONFIDENCE`: Categories marked as `?` or unclear (e.g. `REC-021`).
  - `AGENT_HALLUCINATION`: Worker invents carrier like "SpaceX Rocket". Caught by Verifier, rejected, and routed.
  - `AGENT_MALFORMED`: Corrupted worker JSON formats trigger bounded retries, then exceptions.
  - `BUDGET_EXCEEDED`: Step limit breaches raise budget exception.
* **Class B (Auto-resolved):**
  - `SCHEMA_DRIFT`: Field `Value` mapped back to `amount` and logged (e.g. `REC-016`).
  - `SUPERSEDED_VERSION`: Keeps newest version of record ID, marking old ones as superseded (e.g. `REC-017` v1).

---

## 6. Generalization
The pipeline does not hardcode record IDs or outlier values. The IQR outlier threshold adapts to whatever dataset is supplied. Normalization dynamically resolves variations (`Value`, `total_amount`, etc.) through declarative mappings.

---

## 7. LLM/Agent Contract & Eval
Inter-agent events and LLM outputs are checked against versioned Pydantic schemas. The evaluation harness `eval_harness.py` runs 10 golden scenarios covering validations, schema drifts, verifier discrepancies, budget caps, and logs verifier catch rates.

---

## 8. Cost & Scale
* **Average Record Cost:** ~$0.00019 USD (cheap model by default, escalates to strong model only for large transactions or repair).
* **p95 Latency:** ~12ms (in offline replay mode).
* **Projected Cost for 10k records/day:** ~$1.90 USD.

---

## 9. Amendment
* **My Role R:** `compliance`
* **My Threshold T:** `45000`
* **Governing Rule:** Any e-commerce order whose total amount $\ge$ 45,000 USD requires compliance officer approval in the approval trail, in addition to standard operator review, prior to delivery.

---

## 10. AI Usage / Real-vs-Faked
AI was utilized to design the state transition flow and optimize schema validation. The LLM integration is fully load-bearing: the `response_hash` and `delivered_fields_hash` in committed transcripts verify that every delivered package matches a verified transcript generated by the Worker agent.

---

## 11. Tradeoffs & Next Week
* **Tradeoff:** SQLite persistence is extremely clean and crash-resilient for single-box operation but lacks high concurrent scaling.
* **Next Week Upgrade:** Migrating state persistence to PostgreSQL and implementing an asynchronous task queue (e.g. Celery) to support high concurrency.
