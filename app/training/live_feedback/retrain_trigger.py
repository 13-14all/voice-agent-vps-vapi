"""
Scheduled job (cron / systemd timer) that decides when a business needs a
retrain/re-eval pass: enough new corrections accumulated, or avg live-call
score has drifted down. Wire this to scripts/retrain_cron.sh.
"""
import os
import psycopg

from app.training.simulation.simulate_calls import run_simulation
import asyncio

NEW_CORRECTIONS_THRESHOLD = 10
SCORE_DRIFT_THRESHOLD = 0.65


def check_and_trigger(business_id: str) -> dict:
    with psycopg.connect(os.environ["POSTGRES_URL"]) as conn:
        corrections = conn.execute(
            """SELECT count(*) FROM calls
               WHERE business_id = %s AND reviewed_at > now() - interval '7 days'
                 AND corrected_answer IS NOT NULL""",
            (business_id,),
        ).fetchone()[0]
        avg_score = conn.execute(
            """SELECT avg(auto_score) FROM calls
               WHERE business_id = %s AND started_at > now() - interval '3 days'""",
            (business_id,),
        ).fetchone()[0] or 1.0

    should_run = corrections >= NEW_CORRECTIONS_THRESHOLD or avg_score < SCORE_DRIFT_THRESHOLD
    result = {"business_id": business_id, "corrections": corrections,
              "avg_score": avg_score, "simulation_triggered": should_run}

    if should_run:
        result["simulation_result"] = asyncio.run(run_simulation(business_id, num_calls=30))
    return result


if __name__ == "__main__":
    import sys, json
    print(json.dumps(check_and_trigger(sys.argv[1]), indent=2))
