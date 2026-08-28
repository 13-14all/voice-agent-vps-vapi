from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class BusinessConfig(BaseModel):
    """Everything that makes one tenant's agent different from another's.
    Vapi owns telephony/voice/turn-taking; we own the brain (prompt + RAG)
    and, at provisioning time, tell Vapi which voice/number to attach."""
    phone_number: str
    business_id: str
    business_name: str
    system_prompt: str
    knowledge_namespace: str
    tools: list[str] = []
    llm_tier: str = "hybrid"          # "local" | "cloud" | "hybrid"

    # Vapi-side provisioning fields (used by app/vapi/provision.py and to
    # resolve which business a live call belongs to via call.assistantId).
    vapi_assistant_id: Optional[str] = None
    vapi_voice_provider: str = "11labs"
    vapi_voice_id: str = "burt"
    vapi_model_label: str = "gpt-4o"   # cosmetic label Vapi shows; actual
                                        # generation still runs through our
                                        # LLMEngine over the Custom LLM endpoint
    vapi_first_message: str = "Hello, thanks for calling! How can I help you today?"


class Turn(BaseModel):
    role: str                          # "agent" | "user"
    content: str


class CallRecord(BaseModel):
    call_id: str                       # Vapi's call.id
    business_id: str
    agent_id: Optional[str] = None     # Vapi's assistantId
    started_at: datetime
    ended_at: Optional[datetime] = None
    transcript: list[Turn] = []
    call_successful: Optional[bool] = None     # from Vapi's analysis.successEvaluation
    custom_analysis_data: dict[str, Any] = {}  # Vapi's analysis.structuredData
    outcome: Optional[str] = None
    flagged_for_review: bool = False
    flag_reason: Optional[str] = None
