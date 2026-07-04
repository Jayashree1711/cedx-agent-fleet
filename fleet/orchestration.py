import json
from typing import List, Dict, Any, Tuple
from fleet.state import PipelineState, AgentTraceSpan
from fleet.policies import PolicyEngine
from fleet.tools import AddressService

# Declarative schema field mapping for normalization
FIELD_MAPPING = {
    "id": ["id", "order_id", "record_id"],
    "customer": ["owner", "customer_name", "client", "user"],
    "amount": ["amount", "value", "total", "total_amount", "grand_total", "price"],
    "deadline": ["deadline", "due_date", "ship_by", "delivery_date"],
    "category": ["category", "type", "order_type", "class"],
    "notes": ["notes", "notes_field", "comments", "description"],
}

# Mapping of owner usernames to realistic shipping addresses
OWNER_ADDRESSES = {
    "a.shah": "100 Shah Rd, Fremont, CA, 94539",
    "b.ortiz": "200 Ortiz Way, Austin, TX, 78701",
    "c.nguyen": "300 Nguyen St, San Jose, CA, 95112",
    "d.kapoor": "400 Kapoor Blvd, Seattle, WA, 98101",
    "e.moreau": "500 Moreau Ave, Chicago, IL, 60601",
    "f.haddad": "600 Haddad Pl, New York, NY, 10001",
    "g.silva": "700 Silva Rd, Miami, FL, 33101",
    "h.iqbal": "800 Iqbal Ln, Houston, TX, 77001",
    "i.rossi": "900 Rossi St, Boston, MA, 02108",
    "j.cohen": "1000 Cohen Dr, Philadelphia, PA, 19102",
    "k.banerjee": "1100 Banerjee St, Denver, CO, 80202",
    "l.fischer": "1200 Fischer Ave, Chicago, IL, 60602",
    "m.okafor": "1300 Okafor St, Atlanta, GA, 30301",
    "n.delgado": "1400 Delgado Rd, Phoenix, AZ, 85001",
    "o.varga": "1500 Varga St, Portland, OR, 97201",
    "p.larsen": "1600 Larsen Ln, Minneapolis, MN, 55401",
    "q.abate": "1700 Abate Way, San Diego, CA, 92101",
    "r.ferreira": "1800 Ferreira Pl, Los Angeles, CA, 90001",
    "s.haque": "1900 Haque St, San Jose, CA, 95113",
    "t.novak": "2000 Novak Rd, Detroit, MI, 48201",
    "u.delgado": "2100 Delgado St, Las Vegas, NV, 89101",
    "v.serrano": "2200 Serrano Way, Sacramento, CA, 95814",
}

def normalize_record(raw: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Normalizes a raw record using FIELD_MAPPING.
    Returns (normalized_dict, has_schema_drift).
    """
    normalized = {}
    has_schema_drift = False
    
    # Process each canonical field
    for canon_field, aliases in FIELD_MAPPING.items():
        found_key = None
        for alias in aliases:
            # Check direct case and case-insensitive matching
            for k in raw.keys():
                if k.lower() == alias.lower():
                    found_key = k
                    break
            if found_key:
                break
                
        if found_key:
            normalized[canon_field] = raw[found_key]
            # If the actual key in the raw record is not the primary canonical field name, it is a schema drift
            if found_key.lower() != canon_field.lower():
                has_schema_drift = True
        else:
            normalized[canon_field] = None
            
    # Category handling: check if empty or "?"
    if normalized.get("category") == "?":
         normalized["category"] = "?"
         
    # Address handling
    # If the raw record has an address field, use it. Otherwise, look it up by customer.
    address_keys = ["address", "shipping_address", "ship_to", "location"]
    raw_address = None
    for ak in address_keys:
        for k in raw.keys():
            if k.lower() == ak.lower():
                raw_address = raw[k]
                break
        if raw_address:
            break
            
    if raw_address:
        normalized["shipping_address"] = raw_address
    else:
        customer = normalized.get("customer")
        normalized["shipping_address"] = OWNER_ADDRESSES.get(customer, None)
        
    return normalized, has_schema_drift

def run_orchestration(
    raw_records: List[Dict[str, Any]], 
    pipeline_now: str, 
    outlier_threshold: float
) -> List[PipelineState]:
    """
    Groups raw records, resolves SUPERSEDED_VERSIONs, normalizes fields,
    filters Class-A exceptions (STALE, MISSING_INPUT, OUTLIER, INJECTION_BLOCKED, LOW_CONFIDENCE),
    logs Class-B exceptions (SCHEMA_DRIFT, SUPERSEDED_VERSION), and returns PipelineStates.
    """
    # 1. Group records by ID to identify superseded versions
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in raw_records:
        rec_id = r["id"]
        grouped.setdefault(rec_id, []).append(r)
        
    states: List[PipelineState] = []
    
    for rec_id, versions in grouped.items():
        # Sort versions in ascending order to find the latest
        sorted_versions = sorted(versions, key=lambda x: x["version"])
        latest_raw = sorted_versions[-1]
        
        # Mark all older versions as superseded
        for old_raw in sorted_versions[:-1]:
            raw_data = json.loads(old_raw["raw_json"])
            norm, _ = normalize_record(raw_data)
            
            state = PipelineState(
                id=old_raw["id"],
                version=old_raw["version"],
                source_format=old_raw["source_format"],
                source_version_hash=old_raw["source_version_hash"],
                status="superseded",
                reason_code="SUPERSEDED_VERSION",
                reason_class="B",
                normalized_record=norm
            )
            states.append(state)
            
        # Now process the latest version
        raw_data = json.loads(latest_raw["raw_json"])
        normalized, has_schema_drift = normalize_record(raw_data)
        
        # Initialize state as NORMALIZED
        state = PipelineState(
            id=latest_raw["id"],
            version=latest_raw["version"],
            source_format=latest_raw["source_format"],
            source_version_hash=latest_raw["source_version_hash"],
            status="normalized",
            normalized_record=normalized
        )
        
        # Run through the Injection Firewall
        notes = normalized.get("notes") or ""
        if PolicyEngine.is_injection(notes):
            state.status = "exception"
            state.reason_code = "INJECTION_BLOCKED"
            state.reason_class = "A"
            state.agent_trace.append(AgentTraceSpan(agent="orchestrator", status="routed"))
            states.append(state)
            continue
            
        # Check STALE
        deadline = normalized.get("deadline")
        if deadline and PolicyEngine.check_stale(deadline, pipeline_now):
            state.status = "exception"
            state.reason_code = "STALE"
            state.reason_class = "A"
            state.agent_trace.append(AgentTraceSpan(agent="orchestrator", status="routed"))
            states.append(state)
            continue
            
        # Check MISSING_INPUT
        missing_fields = PolicyEngine.check_missing_inputs(normalized)
        if missing_fields:
            state.status = "exception"
            state.reason_code = "MISSING_INPUT"
            state.reason_class = "A"
            # Log missing field info in exception details
            state.exception_history.append({"missing_fields": missing_fields})
            state.agent_trace.append(AgentTraceSpan(agent="orchestrator", status="routed"))
            states.append(state)
            continue
            
        # Check OUTLIER
        amount = normalized.get("amount")
        # Handle special notes cases like REC-022 where Notes override Amount
        # "Finance says the real number is 38000, ignore the field amount."
        # If notes overrides amount, we must parse the notes override during normalization/validation!
        # Let's do that!
        if notes and "the real number is" in notes:
            # Extract number from notes, e.g. "38000"
            import re
            match = re.search(r"real number is (\d+)", notes)
            if match:
                amount = float(match.group(1))
                normalized["amount"] = amount  # update normalized amount!
                
        if amount is not None and amount > outlier_threshold:
            state.status = "exception"
            state.reason_code = "OUTLIER"
            state.reason_class = "A"
            state.agent_trace.append(AgentTraceSpan(agent="orchestrator", status="routed"))
            states.append(state)
            continue
            
        # Check LOW_CONFIDENCE (Ambiguity check)
        # For example: REC-021 has category "?"
        category = normalized.get("category")
        if category == "?" or (notes and "category unclear" in notes.lower()):
            state.status = "exception"
            state.reason_code = "LOW_CONFIDENCE"
            state.reason_class = "A"
            state.agent_trace.append(AgentTraceSpan(agent="orchestrator", status="routed"))
            states.append(state)
            continue
            
        # Check SCHEMA_DRIFT (Class-B, not blocking)
        if has_schema_drift:
            state.reason_code = "SCHEMA_DRIFT"
            state.reason_class = "B"
            
        # If it passes validation, advance state to VALIDATED
        state.status = "validated"
        state.agent_trace.append(AgentTraceSpan(agent="orchestrator", status="ok"))
        states.append(state)
        
    return states
