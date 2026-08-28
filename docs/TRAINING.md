# Training the agent(s)

There are three complementary training loops. All three write into the same
two places — `knowledge_chunks` (what the agent knows) and
`app/training/simulation/scenarios/*.yaml` (what the agent is tested
against) — so improvements compound instead of living in silos. Both live
calls and simulated calls are graded by the exact same
`app/training/eval/scorecard.py`, and both live calls and simulated calls run
through the exact same `app/core/reply_engine.generate_agent_reply()` — so a
regression caught in simulation is a regression Vapi callers would have hit.

## 1. Business knowledge training (per-business RAG)

Give a business a real memory of its own policies, pricing, FAQs, and scripts.

```bash
python -m app.knowledge.ingest.ingest_docs \
    --business kb_plumbing \
    --path config/businesses/docs/plumbing/
```

This chunks each doc (`CHUNK_SIZE=800`, `CHUNK_OVERLAP=100` chars), embeds
each chunk (`app/knowledge/ingest/embed.py`, Ollama `nomic-embed-text` by
default), and stores it in `knowledge_chunks` under that business's
`knowledge_namespace`. On every turn, `reply_engine.generate_agent_reply()`
pulls the top-k most relevant chunks into the LLM prompt (RAG).

Vapi also has its own [Knowledge Base
feature](https://docs.vapi.ai/knowledge-base) for no-code assistants — we
don't use it here because Custom LLM mode gives us full control over
retrieval and lets the live-caller correction loop (below) write directly
into the same store that simulation reads from.

**Sources to feed it:** FAQ pages, price sheets, service-area lists, past
call scripts, cancellation/refund policy, hours/holiday schedule.

## 2. Agent-vs-agent simulation training

Before a change goes live, run it against synthetic callers so failures
surface in a sandbox, not on a real customer's line.

```bash
python -m app.training.simulation.simulate_calls --business kb_plumbing --n 20
```

How it works (`app/training/simulation/simulate_calls.py`):
1. One LLM instance plays a **caller persona** from
   `app/training/simulation/scenarios/<business_id>.yaml` (falls back to
   `default.yaml`) with a stated **goal**.
2. The other "instance" is `reply_engine.generate_agent_reply()` — the exact
   same function `/vapi/chat/completions` calls on a live call. No separate
   test harness to fall out of sync with production behavior.
3. They converse for up to `max_turns`, then `scorecard.py` scores the
   transcript on: goal completion, response hygiene (no "I don't know" loops
   / errors), conversation length, and non-repetition.
4. Runs and scores are logged to `simulation_runs`; full transcripts to
   `app/training/simulation/results/*.json`.

Run this after every prompt change, new knowledge ingestion, or model swap —
treat it as your regression test suite for conversation quality. You can also
trigger it via `POST /training/simulate?business_id=kb_plumbing&num_calls=20`.

## 3. Live-caller training loop

Once assistants are answering real calls, every call becomes a training
signal — and Vapi does most of the heavy lifting for us here.

```
Real call ends
     ↓
Vapi POSTs `end-of-call-report` to /vapi/webhook
   (full transcript, analysis.successEvaluation, analysis.structuredData)
     ↓
app/vapi/webhook.py verifies x-vapi-secret, then calls
   call_recorder.persist_call() → stores it, runs our own scorecard too
     ↓
flagged? (Vapi says successEvaluation=false, OR our scorecard < 0.6)
     ↓ yes                                  ↓ no
Human review queue                    stored as passive history
(review_queue.py — query below)
     ↓
Reviewer reads transcript, writes the ideal answer, calls
POST /training/review/{call_id}/approve  (with corrected_answer)
     ↓
approve_and_fold_back():
  • ideal answer embedded + inserted into knowledge_chunks
    (source_type='live_call_correction')
  • the real failure becomes a new permanent scenario in
    simulation/scenarios/<business_id>.yaml — so it can never silently
    regress again
     ↓
retrain_trigger.py (nightly cron, scripts/retrain_cron.sh):
  if 7-day corrections ≥ 10 OR 3-day avg live score < 0.65
      → automatically re-run simulation (30 calls) for that business
      → result logged to simulation_runs for a human to review
```

This closes the loop: **real failures → human-approved corrections →
knowledge base + regression scenarios → automatically re-tested.**

### Review queue query

```sql
SELECT call_id, business_id, flag_reason, started_at
FROM calls
WHERE flagged_for_review AND reviewed_at IS NULL
ORDER BY started_at;
```

Build a small internal page or CLI over this query + the approve endpoint —
that's the whole "review UI."

### Configuring what Vapi analyzes

On each Vapi assistant, set the `analysisPlan` (success evaluation prompt +
rubric, and any `structuredDataSchema` fields you want extracted — e.g. "was
an appointment booked", "customer sentiment") — those show up automatically
in the `end-of-call-report` event and get stored in
`calls.custom_analysis_data` for later querying/dashboards.

## Rolling it out safely

- Never let an unreviewed correction touch the live `system_prompt`
  automatically — only knowledge chunks and scenarios are auto-folded;
  prompt edits stay a deliberate human action.
- Keep `simulation_runs.avg_score` trending in a dashboard per business —
  a dip right after a knowledge ingestion or prompt edit is your signal to
  roll back before it reaches live callers.
