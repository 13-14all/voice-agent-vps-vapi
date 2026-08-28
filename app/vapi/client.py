"""
Thin REST wrapper around the Vapi API (https://docs.vapi.ai/api-reference).
Plain httpx rather than the official SDK to keep this service dependency-light.
"""
import os
import httpx

BASE_URL = "https://api.vapi.ai"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['VAPI_API_KEY']}",
        "Content-Type": "application/json",
    }


async def create_or_update_assistant(business, custom_llm_url: str, server_url: str) -> dict:
    """Creates the assistant on first provision; PATCHes it on every later
    run so config/businesses/*.yaml stays the single source of truth."""
    body = {
        "name": business.business_name,
        "firstMessage": business.vapi_first_message,
        "model": {
            "provider": "custom-llm",
            "url": custom_llm_url,
            "model": business.vapi_model_label,
        },
        "voice": {"provider": business.vapi_voice_provider, "voiceId": business.vapi_voice_id},
        "serverUrl": server_url,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        if business.vapi_assistant_id:
            resp = await client.patch(
                f"{BASE_URL}/assistant/{business.vapi_assistant_id}",
                headers=_headers(), json=body,
            )
        else:
            resp = await client.post(f"{BASE_URL}/assistant", headers=_headers(), json=body)
        resp.raise_for_status()
        return resp.json()


async def import_phone_number(phone_number: str, twilio_account_sid: str,
                               twilio_auth_token: str, assistant_id: str) -> dict:
    """Imports an existing Twilio number into Vapi and assigns it to this
    assistant. Use Vapi's free/managed numbers via the dashboard instead if
    you don't want to bring your own Twilio account."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{BASE_URL}/phone-number",
            headers=_headers(),
            json={
                "provider": "twilio",
                "number": phone_number,
                "twilioAccountSid": twilio_account_sid,
                "twilioAuthToken": twilio_auth_token,
                "assistantId": assistant_id,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_call(call_id: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{BASE_URL}/call/{call_id}", headers=_headers())
        resp.raise_for_status()
        return resp.json()
