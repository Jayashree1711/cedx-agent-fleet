# Architectural Decisions Document (DECISIONS.md) - CASE_ID: CEDX-3E31C1

## 1. What We Did NOT Automate (And Why)
* **Final Release Decisions on Exceptions:** If an order triggers a Class-A exception (e.g. prompt injection, missing required customer name, stale deadline, or a verifier-detected hallucination), the system quarantines the record into `exception_queue.json`. We did not automate the override/resolution of these records. A human operations agent must manually correct the underlying data (such as getting a new shipping address) or explicitly override the exception using the CLI before the record is allowed to re-enter the validation state machine. Automating exception overrides risks letting fraudulent or garbage records pass, which violates corporate governance standards.
* **Carrier Rates Negotiated Contracts:** Although carrier rate shopping is automated, resolving contract-level rate issues (e.g., if USPS is down or has rate changes) is left to the business API providers (Shippo/EasyPost) rather than internal LLM reasoning.

---

## 2. Statistical Outliers & Abstain Thresholds (Generalization)
* **Outlier Policy:** We use the robust Interquartile Range (IQR) method to classify outlier order amounts.
  $$\text{Threshold} = Q3 + 3 \times \text{IQR}$$
  Unlike hardcoding a static threshold, this dynamically adapts to the current cohort. In the default seed dataset, Q1 is $4550$, Q3 is $5225$, and IQR is $675$, placing the boundary at $7250$ USD. This dynamically flags `REC-013` ($250,000$ USD) as an outlier while letting valid transaction amounts pass.
* **Abstain Policy:** If notes indicate ambiguity (e.g., conflicting categories or missing attachments like `REC-021` or `REC-015`), the Worker Agent explicitly returns `abstain = True`, triggering the `LOW_CONFIDENCE` exception. This ensures that the system abstains from guessing rather than risking a hallucinated package.

---

## 3. Confidence-Aware Model Router Policy & Economics
* **Cheap Model:** `gemini-1.5-flash` / `gpt-4o-mini`. Used for standard orders with clean values (< $20,000$ USD) and clear categories.
* **Strong Model:** `gemini-1.5-pro` / `gpt-4o`. Escalated dynamically if the amount exceeds $20,000$ USD, if notes contain ambiguity words, or if a Verifier validation rejection occurs.
* **Cost Numbers:**
  * Cheap Model Cost per 10k runs: $10,000 \times \$0.00010 = \$1.00$
  * Strong Model Cost per 10k runs: $10,000 \times \$0.00200 = \$20.00$
  * With our router, over 95% of orders are routed through the cheap model, yielding an average cost of **$0.00019 USD per order**, which translates to only **$1.90 USD per 10,000 orders/day**.

---

## 4. Provenance and Idempotency
* **Record Lineage (Replay):** Every run computes a deterministic hash of the raw record input (`source_version_hash`).
* **Database Persistence:** Persisting state records into `out/pipeline.db` (SQLite) uses `INSERT OR REPLACE` keyed on `(id, version)`. If the same version is re-processed, it updates the existing state rather than appending duplicates, guaranteeing idempotency.
* **Resumability:** If the pipeline is interrupted between stages, SQLite state snapshots let the system resume from the last completed stage without reprocessing delivered items.

---

## 5. What Breaks First at 10,000 Records/Day?
* **Rate Limits (RPM/TPM):** Making 10,000 LLM calls per day translates to ~7 calls/minute on average, but batch spikes can easily trigger provider rate limits. Implementing an asynchronous batching worker queue with exponential backoff will be required to handle spikes.
* **SQLite Locking:** As a single-file database, SQLite will face write-locking contention under highly concurrent multi-threaded worker setups. Upgrading the state storage to PostgreSQL will be the first database change.
