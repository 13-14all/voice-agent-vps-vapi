"""
CLI: create/update the Vapi assistant for one business from its
config/businesses/<name>.yaml, and (optionally) import/attach a phone number.

Usage:
    python -m app.vapi.provision --business kb_plumbing
    python -m app.vapi.provision --business kb_plumbing --attach-number +17195551234 \\
        --twilio-sid ACxxxx --twilio-token xxxx
"""
import argparse
import asyncio
import os

from app.core.config_loader import load_business_config_by_id
from app.vapi.client import create_or_update_assistant, import_phone_number

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://your-vps-domain.com")


async def provision(business_id: str, attach_number: str | None,
                     twilio_sid: str | None, twilio_token: str | None) -> None:
    business = load_business_config_by_id(business_id)

    custom_llm_url = f"{PUBLIC_BASE_URL}/vapi/chat/completions"
    server_url = f"{PUBLIC_BASE_URL}/vapi/webhook"

    assistant = await create_or_update_assistant(business, custom_llm_url, server_url)
    print(f"Assistant ready: {assistant.get('id')} ({business.business_name})")
    print("-> Save this id into businesses.vapi_assistant_id so future runs PATCH instead of create.")

    if attach_number:
        result = await import_phone_number(attach_number, twilio_sid, twilio_token, assistant["id"])
        print(f"Phone number {attach_number} attached: {result}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--business", required=True, help="business_id, e.g. kb_plumbing")
    parser.add_argument("--attach-number", default=None, help="E.164 phone number to import")
    parser.add_argument("--twilio-sid", default=None)
    parser.add_argument("--twilio-token", default=None)
    args = parser.parse_args()
    asyncio.run(provision(args.business, args.attach_number, args.twilio_sid, args.twilio_token))
