from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class WorkerInput(BaseModel):
    normalized_record: Dict[str, Any]
    tools_output: Dict[str, Any]

class WorkerOutput(BaseModel):
    allocated_stock: bool
    carrier: str
    service_level: str
    shipping_cost: float
    address_verified: bool
    fraud_risk: str  # low, medium, high
    brand_package: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float
    abstain: bool = False
    abstain_reason: Optional[str] = None

class VerifierVerdict(BaseModel):
    verdict: str  # pass, fail, needs_human
    status: str   # ok, rejected, overruled
    reason: Optional[str] = None
    discrepancies: List[str] = Field(default_factory=list)

# Defining the Roster structure for verify_audit.py
ROSTER = [
    {
        "name": "orchestrator",
        "role": "orchestrator",
        "models": ["gpt-4o-mini", "gpt-4o", "gemini-1.5-flash", "gemini-1.5-pro"],
        "prompt_version": "1.0",
        "can_call": ["worker", "verifier"]
    },
    {
        "name": "worker",
        "role": "worker",
        "models": ["gpt-4o-mini", "gpt-4o", "gemini-1.5-flash", "gemini-1.5-pro"],
        "prompt_version": "1.0",
        "can_call": []
    },
    {
        "name": "verifier",
        "role": "verifier",
        "models": ["gpt-4o-mini", "gpt-4o", "gemini-1.5-flash", "gemini-1.5-pro"],
        "prompt_version": "1.0",
        "can_call": []
    }
]
