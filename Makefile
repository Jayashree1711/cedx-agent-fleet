# Uniform probe interface — graders invoke THESE targets identically on every repo,
# whatever language you build in. Wire each to your implementation. Exit codes matter.
SEED_DIR ?= seed

.PHONY: demo verify trace eval replay probe-approval probe-agent-failure probe-budget \
        probe-append-only probe-idempotency clean

# Full multi-agent pipeline, offline replay, on $(SEED_DIR).
demo:
	python3 main.py --seed_dir $(SEED_DIR) --replay_llm true

# Run the PROVIDED gate on your audit bundle. Do not modify verify_audit.py.
verify:
	python3 verify_audit.py --audit out/audit.json --transcripts transcripts --schema audit.schema.json

# Print one record's FULL agent decision path from the log alone
trace:
	python3 main.py --trace_id $(ID)

# Run your agent eval harness: >=10 golden cases + an LLM-judge per agent. Print per-agent scores.
eval:
	python3 eval_harness.py

# Reconstruct one delivered output's DATA lineage from the append-only log alone.
replay:
	python3 main.py --replay_id $(ID)

# Exit 0 ONLY if delivery of a NON-approved item is refused + logged.
probe-approval:
	python3 main.py --probe approval

# Exit 0 ONLY if a hallucinated/malformed WORKER output is caught by the Verifier and routed
# (AGENT_HALLUCINATION / AGENT_MALFORMED) — never delivered.
probe-agent-failure:
	python3 main.py --probe agent-failure

# Exit 0 ONLY if a record exceeding the per-record cost/step ceiling raises BUDGET_EXCEEDED
# and is downgraded or routed — never silently overspent.
probe-budget:
	python3 main.py --probe budget

# Exit 0 ONLY if mutating/deleting a past audit entry is refused.
probe-append-only:
	python3 main.py --probe append-only

# Exit 0 ONLY if running demo twice produces no duplicate outputs/exceptions/approvals.
probe-idempotency:
	python3 main.py --probe idempotency

clean:
	rm -rf out
