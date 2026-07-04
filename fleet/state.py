from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class AgentTraceSpan(BaseModel):
    agent: str
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cost_usd: Optional[float] = 0.0
    latency_ms: Optional[float] = 0.0
    retries: Optional[int] = 0
    transcript_hash: Optional[str] = None
    status: str  # ok, retried, rejected, overruled, routed, abstained, killed
    verdict: Optional[str] = None  # pass, fail, needs_human (for verifier)

class ApprovalTrail(BaseModel):
    state: str  # draft, in_review, changes_requested, approved, delivered, blocked
    actor: str
    ts: str
    reason: Optional[str] = None

class PipelineState(BaseModel):
    id: str
    version: int = 1
    source_format: str  # feed, eml, pdf
    source_version_hash: str
    status: str  # exception, superseded, delivered, draft, in_review, approved, etc.
    reason_code: Optional[str] = None  # STALE, MISSING_INPUT, etc.
    reason_class: Optional[str] = None  # A, B
    normalized_record: Dict[str, Any] = Field(default_factory=dict)
    delivered_fields: Optional[Dict[str, Any]] = None
    delivered_fields_hash: Optional[str] = None
    transcript_hash: Optional[str] = None
    agent_trace: List[AgentTraceSpan] = Field(default_factory=list)
    approval_trail: List[ApprovalTrail] = Field(default_factory=list)
    cost_usd: float = 0.0
    steps: int = 0
    exception_history: List[Dict[str, Any]] = Field(default_factory=list)
