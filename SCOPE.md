# SCOPE — push this during the live call (tracer checkpoint)

- **Candidate name:** Jayashree
- **CASE_ID (assigned live):** CEDX-3E31C1
- **Industry chosen (from cedxsystems.com/workflows):** E-commerce Operations
- **Tier:** Production
- **Stack / language:** Python 3.11 / SQLite

## Amendment (compute from your CASE_ID)
```
H = sha256(CASE_ID)
role R      = ["risk_officer","legal_counsel","compliance","finance_controller"][ int(H[0],16) % 4 ]
threshold T = 10000 + (int(H[1:3],16) % 50) * 1000
```
- **My role R:** compliance
- **My threshold T:** 45000

## What I will build (the 5 governed stages)
- [x] Sources/Intake (parse feed.json + inbox PDF/email)
- [x] Orchestration (declarative normalize + exception queue, all reason codes)
- [x] Assembly (LLM structured output + abstain path)
- [x] Review (operator surface + approval state machine + my CASE_ID amendment)
- [x] Delivery (branded package + append-only audit + replay)

## What I will deliberately NOT build (and why)
- External production payment, ERP, WMS, and mailing server connections. These are simulated via deterministic, mock service layers (`fleet/tools/`) to keep tests sandbox-contained and self-verifiable under strict network restrictions.
