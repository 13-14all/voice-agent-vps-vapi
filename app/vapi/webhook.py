"""
Handles Vapi's Server URL events (https://docs.vapi.ai/server-url/events):

- `assistant-request` — OPTIONAL dynamic routing path: if a phone number has
  no static assistant assigned, Vapi POSTs here and expects an assistant
  config back. Useful for the "many virtual numbers forwarded to one Vapi
  number, agent/voice/knowledge picked by which number was dialed" pattern.
  This scaffold defaults to the simpler static path (one Assistant per
  business via provision.py) but implements this too since it's one
  conditional away.
- `end-of-call-report` — the training hook: full transcript + summary +
  structured analysis once a call ends. Equivalent to Retell's
  `call_analyzed`.
- `status-update`, `tool-calls`, `hang` — logged/no-ops here; extend as needed.

Auth: Vapi calls your Server URL with an `x-vapi-secret` header equal to the
shared secret you set on the assistant/phone number/account — a simple
constant-time string compare, no HMAC needed.
"""
import hmac
import os

from fastapi import APIRouter, Request, HTTPException

from app.core.config_loader import load_business_config, load_business_config_by_id
from app.core.models import CallRecord, Turn
from app.training.eval.scorecard import score_transcript
from app.training.live_feedback.call_recorder import persist_call

router = APIRouter()


def _verify_secret(request: Request) -> None:
    expected = os.environ["VAPI_SERVER_SECRET"]
    got = request.headers.get("x-vapi-secret", "")
    if not hmac.compare_digest(expected, got):
        raise HTTPException(status_code=401, detail="invalid server secret")


@router.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    _verify_secret(request)
    payload = await request.json()
    message = payload.get("message", payload)
    event = message.get("type")

    if event == "assistant-request":
        return await _handle_assistant_request(message)

    if event == "end-of-call-report":
        await _handle_end_of_call_report(message)

    return {"received": True}


async def _handle_assistant_request(message: dict) -> dict:
    """Dynamic per-number routing: look up the business by the number that
    was dialed and hand back a full assistant config pointing at our shared
    Custom LLM endpoint. Only needed if you route via a single Vapi number
    with call-forwarding rather than one Vapi number per business."""
    to_number = message.get("phoneNumber", {}).get("number") or message.get("call", {}).get("phoneNumber")
    business = load_business_config(to_number)

    base_url = os.environ["PUBLIC_BASE_URL"]
    return {
        "assistant": {
            "name": business.business_name,
            "firstMessage": business.vapi_first_message,
            "model": {
                "provider": "custom-llm",
                "url": f"{base_url}/vapi/chat/completions",
                "model": business.vapi_model_label,
            },
            "voice": {"provider": business.vapi_voice_provider, "voiceId": business.vapi_voice_id},
            "serverUrl": f"{base_url}/vapi/webhook",
        }
    }


async def _handle_end_of_call_report(message: dict) -> None:
    call = message.get("call", {})
    transcript_msgs = message.get("artifact", {}).get("messages", message.get("messages", []))
    analysis = message.get("analysis", {})

    transcript = [
        Turn(role="agent" if m.get("role") == "assistant" else "user", content=m.get("message", m.get("content", "")))
        for m in transcript_msgs if m.get("role") in ("assistant", "user")
    ]

    business_id = _business_id_from_call(call)

    record = CallRecord(
        call_id=call.get("id", "unknown"),
        business_id=business_id,
        agent_id=call.get("assistantId"),
        started_at=call.get("startedAt"),
        ended_at=call.get("endedAt"),
        transcript=transcript,
        call_successful=analysis.get("successEvaluation"),
        custom_analysis_data=analysis.get("structuredData", {}),
    )

    score = score_transcript([t.model_dump() for t in transcript], scenario={"goal": ""})
    record.flagged_for_review, record.flag_reason = _should_flag(record, score)

    await persist_call(record, auto_score=score["overall"])


def _business_id_from_call(call: dict) -> str:
    assistant_id = call.get("assistantId")
    if not assistant_id:
        return "unknown"
    try:
        return load_business_config_by_id(assistant_id).business_id
    except Exception:
        return assistant_id


def _should_flag(record: CallRecord, score: dict) -> tuple[bool, str | None]:
    if record.call_successful is False:
        return True, "vapi_call_unsuccessful"
    if score["overall"] < 0.6:
        return True, "low_auto_score"
    return False, None
