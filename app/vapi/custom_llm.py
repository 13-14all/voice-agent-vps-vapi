"""
Vapi's "Custom LLM" integration is just an OpenAI-compatible /chat/completions
endpoint — Vapi handles telephony, STT, TTS, and turn-taking, then calls this
endpoint with the running conversation every time the assistant needs to
speak. We resolve which business this call belongs to, run it through our
shared reply_engine (RAG + hybrid LLM), and stream back an OpenAI-shaped
SSE response.

Wiring on the Vapi side (done once per business by app/vapi/provision.py):
  assistant.model = {
    "provider": "custom-llm",
    "url": "https://<your-domain>/vapi/chat/completions",
    "model": "<cosmetic label>",
  }

Docs: https://docs.vapi.ai/customization/custom-llm/using-your-server
"""
import json
import time
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.config_loader import load_business_config_by_vapi_assistant_id, load_business_config
from app.core.models import Turn
from app.core.reply_engine import generate_agent_reply
from app.vapi.types import ChatCompletionRequest

router = APIRouter()


@router.post("/vapi/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    req = ChatCompletionRequest(**body)

    business = _resolve_business(req)
    transcript = _to_turns(req.messages)
    reply = await generate_agent_reply(business, transcript)

    if req.stream:
        return StreamingResponse(_sse_stream(reply), media_type="text/event-stream")
    return _one_shot_response(reply)


def _resolve_business(req: ChatCompletionRequest):
    """Vapi includes a `call` object with assistantId once the call is live —
    that's the reliable per-business key (one Vapi Assistant per business,
    all pointing at this same endpoint). Falls back to phone-number lookup
    for local testing without a real call object."""
    if req.call and req.call.assistantId:
        return load_business_config_by_vapi_assistant_id(req.call.assistantId)
    if req.call and req.call.customer.get("number"):
        return load_business_config(req.call.customer["number"])
    return load_business_config(None)


def _to_turns(messages) -> list[Turn]:
    """Vapi/OpenAI roles map directly onto our Turn roles except
    'assistant' -> 'agent' and we drop the system message (that's the
    business's system_prompt, which reply_engine already injects)."""
    turns = []
    for m in messages:
        if m.role == "system":
            continue
        role = "agent" if m.role == "assistant" else "user"
        turns.append(Turn(role=role, content=m.content))
    return turns


async def _sse_stream(reply: str):
    """Vapi expects standard OpenAI streaming chunks. We generate the full
    reply up front (see docs/ARCHITECTURE.md for a note on token streaming)
    and send it as a single delta chunk, which Vapi handles fine."""
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())

    delta_chunk = {
        "id": chunk_id, "object": "chat.completion.chunk", "created": created,
        "model": "custom-llm",
        "choices": [{"index": 0, "delta": {"role": "assistant", "content": reply},
                     "finish_reason": None}],
    }
    yield f"data: {json.dumps(delta_chunk)}\n\n"

    final_chunk = {
        "id": chunk_id, "object": "chat.completion.chunk", "created": created,
        "model": "custom-llm",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"


def _one_shot_response(reply: str) -> dict:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "custom-llm",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": reply},
            "finish_reason": "stop",
        }],
    }
