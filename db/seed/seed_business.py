"""Seed example businesses from config/businesses/*.yaml into Postgres."""
import os
import json
import yaml
import psycopg
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "businesses"


def main():
    with psycopg.connect(os.environ["POSTGRES_URL"]) as conn:
        for path in CONFIG_DIR.glob("*.yaml"):
            data = yaml.safe_load(path.read_text())
            conn.execute(
                """
                INSERT INTO businesses
                    (phone_number, business_id, business_name, system_prompt,
                     knowledge_namespace, tools, llm_tier, vapi_assistant_id,
                     vapi_voice_provider, vapi_voice_id, vapi_model_label,
                     vapi_first_message)
                VALUES (%(phone_number)s, %(business_id)s, %(business_name)s,
                        %(system_prompt)s, %(knowledge_namespace)s, %(tools)s,
                        %(llm_tier)s, %(vapi_assistant_id)s, %(vapi_voice_provider)s,
                        %(vapi_voice_id)s, %(vapi_model_label)s, %(vapi_first_message)s)
                ON CONFLICT (phone_number) DO UPDATE SET
                    business_name = EXCLUDED.business_name,
                    system_prompt = EXCLUDED.system_prompt,
                    vapi_voice_provider = EXCLUDED.vapi_voice_provider,
                    vapi_voice_id = EXCLUDED.vapi_voice_id,
                    vapi_model_label = EXCLUDED.vapi_model_label,
                    vapi_first_message = EXCLUDED.vapi_first_message
                """,
                {
                    **data,
                    "tools": json.dumps(data.get("tools", [])),
                    "vapi_assistant_id": data.get("vapi_assistant_id"),
                    "vapi_voice_provider": data.get("vapi_voice_provider", "11labs"),
                    "vapi_voice_id": data.get("vapi_voice_id", "burt"),
                    "vapi_model_label": data.get("vapi_model_label", "gpt-4o"),
                    "vapi_first_message": data.get(
                        "vapi_first_message",
                        "Hello, thanks for calling! How can I help you today?",
                    ),
                },
            )
        conn.commit()
    print("Seed complete.")


if __name__ == "__main__":
    main()
