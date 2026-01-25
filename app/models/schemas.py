"""Pydantic models for API requests and responses"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class GuardrailType(str, Enum):
    """Types of guardrails"""
    PII_DETECTION = "pii_detection"
    SENSITIVE_REQUEST = "sensitive_request"  # Blocks requests asking for SSN, credit cards, etc.
    TOXICITY = "toxicity"
    HALLUCINATION = "hallucination"
    PROMPT_INJECTION = "prompt_injection"


class GuardrailStatus(str, Enum):
    """Guardrail check status"""
    PASSED = "passed"
    BLOCKED = "blocked"
    FLAGGED = "flagged"


# ==================== ENTERPRISE MODELS ====================

class AgentRegister(BaseModel):
    """Register a new AI agent in the platform"""
    agent_id: str = Field(..., description="Unique identifier for the agent")
    agent_name: str = Field(..., description="Human-readable name")
    department: str = Field(..., description="Department owning the agent")
    team: Optional[str] = Field(default=None, description="Specific team within department")
    description: Optional[str] = Field(default=None, description="What this agent does")
    owner_email: str = Field(..., description="Email of the agent owner")
    environment: str = Field(default="development", description="dev/staging/production")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")


class AgentInfo(BaseModel):
    """Agent information response"""
    agent_id: str
    agent_name: str
    department: str
    team: Optional[str]
    description: Optional[str]
    owner_email: str
    environment: str
    tags: List[str]
    created_at: datetime
    is_active: bool
    total_requests: int = 0
    pii_incidents: int = 0


class DepartmentStats(BaseModel):
    """Statistics for a department"""
    department: str
    total_agents: int
    total_requests: int
    total_users: int
    pii_incidents: int
    blocked_requests: int
    avg_response_time_ms: float
    top_agents: List[Dict[str, Any]]


class UsageAnalytics(BaseModel):
    """Usage analytics response"""
    period_start: datetime
    period_end: datetime
    total_requests: int
    unique_users: int
    unique_agents: int
    pii_detected_count: int
    blocked_count: int
    passed_count: int
    by_department: List[DepartmentStats]
    by_agent: List[Dict[str, Any]]
    by_guardrail: Dict[str, int]


# ==================== GUARDRAIL MODELS ====================

class GuardrailRequest(BaseModel):
    """Request to check content against guardrails"""
    prompt: str = Field(..., description="The user prompt to check")
    agent_id: str = Field(default="default", description="ID of the AI agent")
    user_id: Optional[str] = Field(default=None, description="User making the request")
    department: Optional[str] = Field(default=None, description="User's department")
    session_id: Optional[str] = Field(default=None, description="Session ID for conversation tracking")
    guardrails: List[GuardrailType] = Field(
        default=[GuardrailType.PII_DETECTION],
        description="Guardrails to apply"
    )


class PIIDetectionResult(BaseModel):
    """Result of PII detection"""
    has_pii: bool
    pii_types: List[str] = Field(default_factory=list)
    redacted_text: Optional[str] = None
    details: Optional[str] = None


class GuardrailResult(BaseModel):
    """Result of a single guardrail check"""
    guardrail_type: GuardrailType
    status: GuardrailStatus
    confidence: float = Field(ge=0.0, le=1.0)
    details: Optional[Dict[str, Any]] = None
    processing_time_ms: float


class GuardrailResponse(BaseModel):
    """Response from guardrail checks"""
    request_id: str
    agent_id: str
    overall_status: GuardrailStatus
    results: List[GuardrailResult]
    original_prompt: str
    safe_prompt: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_processing_time_ms: float


class AuditLog(BaseModel):
    """Audit log entry for BigQuery"""
    request_id: str
    timestamp: datetime
    agent_id: str
    user_id: Optional[str]
    department: Optional[str] = None
    session_id: Optional[str] = None
    guardrail_type: str
    status: str
    prompt_length: int
    has_pii: bool
    processing_time_ms: float
    model_used: str
    metadata: Optional[Dict[str, Any]] = None
    # Full prompt logging
    original_prompt: Optional[str] = None
    redacted_prompt: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, str] = Field(default_factory=dict)


# ==================== OUTPUT GUARDRAIL MODELS ====================

class OutputCheckRequest(BaseModel):
    """Request to check AI agent output before sending to user"""
    agent_id: str = Field(..., description="ID of the AI agent")
    user_id: Optional[str] = Field(default=None, description="User who will receive this response")
    department: Optional[str] = Field(default=None, description="User's department")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    agent_response: str = Field(..., description="The AI agent's response to check")
    original_prompt: Optional[str] = Field(default=None, description="Original user prompt for context")


class OutputCheckResponse(BaseModel):
    """Response from output guardrail check"""
    request_id: str
    agent_id: str
    is_safe: bool
    violations: List[str] = Field(default_factory=list)
    safe_response: Optional[str] = None  # Redacted/modified response if needed
    blocked_reason: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SensitiveRequestResult(BaseModel):
    """Result of sensitive data request detection"""
    requests_sensitive_data: bool
    sensitive_types: List[str] = Field(default_factory=list)  # ssn, credit_card, etc.
    details: Optional[str] = None


# ==================== FEEDBACK MODELS ====================

class FeedbackRating(str, Enum):
    """Rating for agent response"""
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    INCORRECT = "incorrect"
    INAPPROPRIATE = "inappropriate"


class FeedbackSubmit(BaseModel):
    """Submit feedback for an agent interaction"""
    request_id: str = Field(..., description="ID of the original request")
    agent_id: str = Field(..., description="Agent being rated")
    user_id: Optional[str] = Field(default=None, description="User providing feedback")
    rating: FeedbackRating = Field(..., description="Overall rating")
    comment: Optional[str] = Field(default=None, description="Additional feedback text")
    suggestion: Optional[str] = Field(default=None, description="Suggestion for improvement")
    tags: List[str] = Field(default_factory=list, description="Tags like 'accuracy', 'speed', 'tone'")


class FeedbackResponse(BaseModel):
    """Response after submitting feedback"""
    feedback_id: str
    request_id: str
    agent_id: str
    status: str = "received"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ==================== API KEY AUTH MODELS ====================

class APIKeyCreate(BaseModel):
    """Create API key for an agent"""
    agent_id: str = Field(..., description="Agent to create key for")
    description: Optional[str] = Field(default=None, description="Description of key usage")
    expires_days: int = Field(default=365, description="Days until expiration")


class APIKeyResponse(BaseModel):
    """API key creation response"""
    key_id: str
    agent_id: str
    api_key: str  # Only shown once at creation
    created_at: datetime
    expires_at: datetime
    is_active: bool = True
