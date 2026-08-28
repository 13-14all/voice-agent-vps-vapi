"""
Human review queue for flagged real calls. A reviewer reads the transcript,
optionally rewrites the ideal agent response, and approves it — which folds
the correction back into:
  1. the business's knowledge base (as a new Q&A chunk), and/or
  2. the simulation scenario file (as a new regression scenario), and/or
  3. the system prompt (only via explicit human edit, never auto-applied).

Query `SELECT * FROM calls WHERE flagged_for_review AND reviewed_at IS NULL`
to build a review UI/CLI on top of this module.
"""
import os
import json
import psycopg

from app.knowledge.ingest.embed import embed_text


async def approve_and_fold_back(call_id: str, corrected_answer: str | None = None,
                                 add_to_knowledge_base: bool = True,
                                 add_to_scenarios: bool = True) -> dict:
    with psycopg.connect(os.environ["POSTGRES_URL"]) as conn:
        row = conn.execute(
            "SELECT business_id, transcript FROM calls WHERE call_id = %s", (call_id,)
        ).fetchone()
        if not row:
            return {"error": "call not found"}
        business_id, transcript = row
        transcript = json.loads(transcript) if isinstance(transcript, str) else transcript

        if corrected_answer and add_to_knowledge_base:
            last_user_line = next(
                (t["content"] for t in reversed(transcript) if t["role"] == "user"), "")
            chunk = f"Q: {last_user_line}\nA: {corrected_answer}"
            vec = embed_text(chunk)
            conn.execute(
                """
                INSERT INTO knowledge_chunks (namespace, content, embedding, source_type)
                VALUES (%s, %s, %s, 'live_call_correction')
                """,
                (business_id, chunk, vec),
            )

        conn.execute(
            "UPDATE calls SET reviewed_at = now(), corrected_answer = %s WHERE call_id = %s",
            (corrected_answer, call_id),
        )
        conn.commit()

    if add_to_scenarios:
        _append_scenario(business_id, transcript, corrected_answer)

    return {"call_id": call_id, "status": "folded_back", "knowledge_updated": bool(corrected_answer)}


def _append_scenario(business_id: str, transcript: list[dict], corrected_answer: str | None) -> None:
    """Turns a real problematic call into a permanent regression scenario so
    future simulation runs catch the same failure mode before it recurs."""
    from pathlib import Path
    import yaml

    scenario_path = Path(__file__).resolve().parents[1] / "simulation" / "scenarios" / f"{business_id}.yaml"
    data = {"scenarios": []}
    if scenario_path.exists():
        data = yaml.safe_load(scenario_path.read_text()) or {"scenarios": []}

    first_user_line = next((t["content"] for t in transcript if t["role"] == "user"), "")
    data["scenarios"].append({
        "name": f"live_regression_{len(data['scenarios']) + 1}",
        "caller_persona": f"You open the call by saying: \"{first_user_line}\"",
        "goal": corrected_answer or "Resolve the caller's issue satisfactorily.",
    })
    scenario_path.parent.mkdir(parents=True, exist_ok=True)
    scenario_path.write_text(yaml.dump(data, sort_keys=False))
