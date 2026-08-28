"""
Persists a CallRecord produced from Vapi's `end-of-call-report` server event
(app/vapi/webhook.py). Kept separate from the webhook handler so the same
persistence path can be reused/tested without a live Vapi event.
"""
import json
import os
import psycopg

from app.core.models import CallRecord


async def persist_call(record: CallRecord, auto_score: float) -> None:
    with psycopg.connect(os.environ["POSTGRES_URL"]) as conn:
        conn.execute(
            """
            INSERT INTO calls
                (call_id, business_id, agent_id, started_at, ended_at, transcript,
                 call_successful, custom_analysis_data, auto_score,
                 flagged_for_review, flag_reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (call_id) DO UPDATE SET
                transcript = EXCLUDED.transcript,
                call_successful = EXCLUDED.call_successful,
                custom_analysis_data = EXCLUDED.custom_analysis_data,
                auto_score = EXCLUDED.auto_score,
                flagged_for_review = EXCLUDED.flagged_for_review,
                flag_reason = EXCLUDED.flag_reason
            """,
            (
                record.call_id, record.business_id, record.agent_id,
                record.started_at, record.ended_at,
                json.dumps([t.model_dump() for t in record.transcript]),
                record.call_successful, json.dumps(record.custom_analysis_data),
                auto_score, record.flagged_for_review, record.flag_reason,
            ),
        )
        conn.commit()
