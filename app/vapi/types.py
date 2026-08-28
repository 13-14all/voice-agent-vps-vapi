"""
Minimal typed shapes for Vapi's two integration surfaces:

1. Custom LLM: an OpenAI-compatible `/chat/completions` endpoint. Vapi sends
   a normal OpenAI chat-completion request (model, messages, stream) plus an
   extra `call` object with call metadata — that's how we know which
   business this call belongs to.
   https://docs.vapi.ai/customization/custom-llm/using-your-server

2. Server URL: webhook events (assistant-request, end-of-call-report,
   status-update, tool-calls, hang). We only model what we read.
   https://docs.vapi.ai/server-url/events
"""
from typing import Any, Optional
from pydantic import BaseModel


class VapiCallInfo(BaseModel):
    id: Optional[str] = None
    assistantId: Optional[str] = None
    phoneNumberId: Optional[str] = None
    customer: dict[str, Any] = {}
    metadata: dict[str, Any] = {}


class OpenAIMessage(BaseModel):
    role: str            # "system" | "user" | "assistant" | "tool"
    content: str = ""


class ChatCompletionRequest(BaseModel):
    """What Vapi POSTs to our Custom LLM endpoint."""
    model: Optional[str] = None
    messages: list[OpenAIMessage] = []
    stream: bool = True
    call: Optional[VapiCallInfo] = None
    metadata: dict[str, Any] = {}
