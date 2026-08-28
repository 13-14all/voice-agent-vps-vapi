"""
Loads a BusinessConfig either by the phone number dialed (dev/local, or the
`assistant-request` dynamic-routing path) or by Vapi's `assistantId` (the
primary path: one Vapi Assistant per business, resolved on every Custom LLM
call). Postgres is the source of truth in production; config/businesses/*.yaml
is used for local dev and as the human-editable authoring format that gets
synced into Postgres (and into Vapi itself, via app/vapi/provision.py).
"""
import os
import yaml
import psycopg
from functools import lru_cache
from pathlib import Path

from app.core.models import BusinessConfig

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "businesses"

_COLUMNS = (
    "phone_number, business_id, business_name, system_prompt, "
    "knowledge_namespace, tools, llm_tier, vapi_assistant_id, "
    "vapi_voice_provider, vapi_voice_id, vapi_model_label, vapi_first_message"
)
_KEYS = [c.strip() for c in _COLUMNS.split(",")]


def load_business_config(to_number: str) -> BusinessConfig:
    if os.getenv("APP_ENV") == "development":
        return _load_from_yaml(to_number)
    return _load_from_postgres(to_number)


def load_business_config_by_id(business_id_or_assistant_id: str) -> BusinessConfig:
    """Looks up by our internal business_id OR Vapi's assistantId (both are
    tried since the Custom LLM endpoint only knows the assistantId, while
    the simulator/retrain trigger only know business_id)."""
    if os.getenv("APP_ENV") == "development":
        for path in CONFIG_DIR.glob("*.yaml"):
            data = yaml.safe_load(path.read_text())
            if business_id_or_assistant_id in (data.get("business_id"), data.get("vapi_assistant_id")):
                return BusinessConfig(**data)
        return _default_config("unknown")
    with psycopg.connect(os.environ["POSTGRES_URL"]) as conn:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM businesses "
            f"WHERE (business_id = %s OR vapi_assistant_id = %s) AND active = true",
            (business_id_or_assistant_id, business_id_or_assistant_id),
        ).fetchone()
    return _row_to_config(row) if row else _default_config("unknown")


def load_business_config_by_vapi_assistant_id(assistant_id: str) -> BusinessConfig:
    return load_business_config_by_id(assistant_id)


def _load_from_postgres(to_number: str) -> BusinessConfig:
    with psycopg.connect(os.environ["POSTGRES_URL"]) as conn:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM businesses WHERE phone_number = %s AND active = true",
            (to_number,),
        ).fetchone()
    return _row_to_config(row) if row else _default_config(to_number)


def _row_to_config(row) -> BusinessConfig:
    return BusinessConfig(**dict(zip(_KEYS, row)))


@lru_cache(maxsize=64)
def _load_from_yaml(to_number: str) -> BusinessConfig:
    for path in CONFIG_DIR.glob("*.yaml"):
        data = yaml.safe_load(path.read_text())
        if data.get("phone_number") == to_number:
            return BusinessConfig(**data)
    return _default_config(to_number)


def _default_config(to_number: str) -> BusinessConfig:
    """Fallback so an unmapped number/assistant never crashes a live call."""
    return BusinessConfig(
        phone_number=to_number or "unknown",
        business_id="personal_default",
        business_name="Personal Assistant",
        system_prompt="You are a helpful personal voice assistant.",
        knowledge_namespace="kb_personal",
        tools=[],
        llm_tier="hybrid",
    )
