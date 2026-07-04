import os
import json
import hashlib
from typing import Dict, Any, Tuple
from pathlib import Path
from pydantic import ValidationError
from fleet.state import PipelineState, AgentTraceSpan
from fleet.agents import WorkerInput, WorkerOutput
from fleet.tools import AddressService, InventoryService, CarrierService, FraudService

def canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def sha(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(canon(obj)).hexdigest()

def get_transcript_by_id(record_id: str, transcripts_dir: str = "transcripts") -> Dict[str, Any]:
    """
    Searches the transcripts directory for a JSON file that matches the record ID.
    """
    tdir = Path(transcripts_dir)
    if not tdir.exists():
        return None
    for tf in tdir.glob("*.json"):
        try:
            t = json.loads(tf.read_text(encoding="utf-8"))
            if t.get("record_id") == record_id:
                return t
        except Exception:
            continue
    return None

def mock_llm_call(
    agent_name: str,
    model: str,
    prompt: str,
    record_id: str,
    replay: bool,
    transcripts_dir: str = "transcripts"
) -> Tuple[str, str]:
    """
    Calls the LLM or reads from a transcript file if replay is enabled.
    Returns (response_string, response_hash_hex).
    """
    if replay:
        # Replay mode: find corresponding transcript
        t = get_transcript_by_id(record_id, transcripts_dir)
        if t:
            raw_resp = t.get("response")
            # If response is a dict/object, convert to string
            if not isinstance(raw_resp, str):
                raw_resp = json.dumps(raw_resp, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            resp_hash = hashlib.sha256(raw_resp.encode("utf-8")).hexdigest()
            return raw_resp, resp_hash
            
    # Real LLM call fallback / Mock fallback
    # In real mode (or fallback), we simulate the LLM returning a structured JSON response
    # We can inject a hallucination or malformed output if notes dictate
    notes_lower = prompt.lower()
    
    # 1. Probe Hallucination simulation
    if "simulate agent hallucination" in notes_lower or "simulate hallucination" in notes_lower:
        output_data = {
            "allocated_stock": True,
            "carrier": "SpaceX Rocket",  # Hallucinated carrier!
            "service_level": "Super Orbit",
            "shipping_cost": 5000.0,
            "address_verified": True,
            "fraud_risk": "low",
            "brand_package": {
                "order_id": record_id,
                "carrier": "SpaceX Rocket",
                "fulfillment_status": "hallucinated"
            },
            "confidence_score": 0.95,
            "abstain": False
        }
    # 2. Probe Malformed simulation
    elif "simulate agent malformed" in notes_lower or "simulate malformed" in notes_lower:
        return "{\n  \"allocated_stock\": True,\n  \"carrier\": JSON_ERROR\n}", "malformed_hash"
    # 3. Standard clean response
    else:
        # Extract details from prompt to generate brand_package
        # We can parse the prompt or normalized record context passed
        # For simulation, we return standard clean parameters
        output_data = {
            "allocated_stock": True,
            "carrier": "USPS",
            "service_level": "Ground Advantage",
            "shipping_cost": 5.50,
            "address_verified": True,
            "fraud_risk": "low",
            "brand_package": {
                "order_id": record_id,
                "carrier": "USPS",
                "service_level": "Ground Advantage",
                "shipping_cost": 5.50,
                "estimated_delivery": "3-5 business days",
                "fulfillment_status": "allocated"
            },
            "confidence_score": 1.0,
            "abstain": False
        }
        
    resp_str = json.dumps(output_data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    resp_hash = hashlib.sha256(resp_str.encode("utf-8")).hexdigest()
    return resp_str, resp_hash

def run_assembly(state: PipelineState, replay_llm: bool, transcripts_dir: str = "transcripts") -> PipelineState:
    """
    Implements Stage 3 (Assembly) using the Worker Agent.
    """
    if state.status == "exception" or state.status == "superseded":
        return state
        
    state.status = "assembled"
    
    # 1. Invoke deterministic tool layer
    norm = state.normalized_record
    category = norm.get("category")
    amount = norm.get("amount") or 0.0
    notes = norm.get("notes") or ""
    address = norm.get("shipping_address") or ""
    
    addr_res = AddressService.validate_address(address)
    stock_res = InventoryService.check_stock(category, amount)
    carrier_res = CarrierService.rate_shop()
    fraud_res = FraudService.check_fraud(norm.get("customer", ""), amount, notes)
    
    tools_output = {
        "address_validation": addr_res,
        "inventory": stock_res,
        "carrier_rates": carrier_res,
        "fraud_check": fraud_res
    }
    
    # 2. Prepare prompt / input contract for Worker
    worker_input = WorkerInput(normalized_record=norm, tools_output=tools_output)
    
    # 3. Model Router selection
    # Trivial / clean records use cheap model. If notes indicate manual review or higher price, escalate.
    is_complex = amount > 20000 or "review" in notes.lower() or "unclear" in notes.lower()
    model = "gemini-1.5-pro" if is_complex else "gemini-1.5-flash"
    
    prompt = f"Order: {json.dumps(norm)}\nTools: {json.dumps(tools_output)}"
    
    # Track metrics
    import time
    start_time = time.time()
    
    # Bounded retry loop for malformed worker output
    max_retries = 2
    retries = 0
    worker_output = None
    resp_str = ""
    resp_hash = ""
    
    while retries <= max_retries:
        try:
            resp_str, resp_hash = mock_llm_call(
                agent_name="worker",
                model=model,
                prompt=prompt,
                record_id=state.id,
                replay=replay_llm,
                transcripts_dir=transcripts_dir
            )
            
            # Parse and validate response against Pydantic contract
            output_dict = json.loads(resp_str)
            worker_output = WorkerOutput(**output_dict)
            break
        except (json.JSONDecodeError, ValidationError) as e:
            retries += 1
            if retries > max_retries:
                # Mark as malformed
                state.status = "exception"
                state.reason_code = "AGENT_MALFORMED"
                state.reason_class = "A"
                
                # Record span
                latency = int((time.time() - start_time) * 1000)
                span = AgentTraceSpan(
                    agent="worker",
                    model=model,
                    prompt_version="1.0",
                    tokens_in=150,
                    tokens_out=50,
                    cost_usd=0.0001,
                    latency_ms=latency,
                    retries=retries - 1,
                    status="killed",
                    verdict="fail"
                )
                state.agent_trace.append(span)
                state.cost_usd += 0.0001
                state.steps += 1
                return state
                
    latency = int((time.time() - start_time) * 1000)
    
    # If worker output is valid, check if worker abstained (LOW_CONFIDENCE)
    if worker_output.abstain:
        state.status = "exception"
        state.reason_code = "LOW_CONFIDENCE"
        state.reason_class = "A"
        state.exception_history.append({"reason": worker_output.abstain_reason})
        
        span = AgentTraceSpan(
            agent="worker",
            model=model,
            prompt_version="1.0",
            tokens_in=150,
            tokens_out=50,
            cost_usd=0.0001,
            latency_ms=latency,
            retries=retries,
            status="abstained"
        )
        state.agent_trace.append(span)
        state.cost_usd += 0.0001
        state.steps += 1
        return state
        
    # Standard successful execution: save worker output in PipelineState
    state.delivered_fields = worker_output.brand_package
    state.delivered_fields_hash = sha(worker_output.brand_package)
    state.transcript_hash = "sha256:" + resp_hash
    
    # Save transcript file if not in replay mode to enable future replays
    if not replay_llm:
        os.makedirs(transcripts_dir, exist_ok=True)
        transcript_data = {
            "record_id": state.id,
            "response": output_dict,
            "response_hash": "sha256:" + resp_hash,
            "delivered_fields_hash": state.delivered_fields_hash,
            "agent": "worker",
            "model": model,
            "prompt_version": "1.0"
        }
        with open(os.path.join(transcripts_dir, f"{resp_hash}.json"), "w", encoding="utf-8") as f:
            json.dump(transcript_data, f, indent=2)
            
    # Record worker trace span
    span = AgentTraceSpan(
        agent="worker",
        model=model,
        prompt_version="1.0",
        tokens_in=180,
        tokens_out=120,
        cost_usd=0.0002,
        latency_ms=latency,
        retries=retries,
        transcript_hash=state.transcript_hash,
        status="ok"
    )
    state.agent_trace.append(span)
    state.cost_usd += 0.0002
    state.steps += 1
    
    return state
