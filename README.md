# Voice Agent VPS — Vapi edition

Multi-tenant AI voice agent platform built on **Vapi.ai** for telephony,
speech-to-text, text-to-speech, and turn-taking/interruption handling. This
repo supplies the one thing Vapi deliberately leaves to you when you choose
"Custom LLM": **the brain** — an OpenAI-compatible chat-completions endpoint
with per-business personality, per-business knowledge (RAG), and a training
system so agents keep improving.

This is a sibling to [`voice-agent-vps`](../voice-agent-vps) (the Retell
edition) — same philosophy, same training loops, different provider
integration layer. Compare `app/retell/` there with `app/vapi/` here if
you're deciding which platform to run.

## Why Vapi's Custom LLM

Vapi already solves telephony, STT/TTS (sub-700ms), barge-in/interruption
handling, and post-call analysis. Its "Custom LLM" mode is deliberately
**OpenAI-API-compatible** — Vapi calls your server exactly like it would call
`api.openai.com/v1/chat/completions`, so you get the full "one core engine,
per-business config" control from the previous versions of this project with
almost zero protocol code of your own.
(https://docs.vapi.ai/customization/custom-llm/using-your-server)

## Why this structure

- **One engine, N agents.** Every business gets its own **Vapi Assistant**
  (voice + first message + this server as its model), all pointing at the
  *same* `/vapi/chat/completions` endpoint. We tell them apart by the
  `assistantId` Vapi includes in every request's `call` object, then load
  that business's prompt + knowledge from Postgres.
- **Three ways to make an agent better** (see `docs/TRAINING.md`):
  1. **Business knowledge training** — ingest a business's docs/FAQs/policies
     into a per-business vector namespace (`app/knowledge/`), retrieved (RAG)
     into the prompt on every turn.
  2. **Agent-vs-agent simulation training** — one LLM plays "caller", the
     other IS the real agent brain (`app/core/reply_engine.py` — the exact
     function the live Custom LLM endpoint calls), transcripts are scored and
     bad turns become permanent regression scenarios.
  3. **Live-caller training loop** — Vapi's `end-of-call-report` server event
     gives us the full transcript + its own success evaluation; flagged calls
     go into a human review queue; approved corrections fold back into the
     knowledge base and the simulation scenario set.
- **Multiple numbers, one brain, forwarded routing (optional).** If you'd
  rather run everything through a single Vapi number with call forwarding
  (as opposed to one Vapi number per business), `app/vapi/webhook.py`
  also implements the `assistant-request` dynamic-assistant-selection event
  — Vapi asks us "which assistant for this call?" and we answer based on the
  dialed number, no static per-business assistant/number pairing required.

## Quick start

```bash
cp .env.example .env             # VAPI_API_KEY, VAPI_SERVER_SECRET, PUBLIC_BASE_URL, Ollama/cloud LLM, Postgres
./scripts/setup.sh                # installs deps, pulls Ollama models, runs DB migrations
./scripts/run_dev.sh              # starts the FastAPI app with hot reload

# Put the server behind TLS (Vapi requires https), then for each business:
python -m app.vapi.provision --business plumbing_co \
    --attach-number +17195551234 --twilio-sid ACxxxx --twilio-token xxxx
```

## Repo map

```
voice-agent-vps-vapi/
├── app/
│   ├── main.py                  # FastAPI entrypoint — mounts vapi router + training endpoints
│   ├── core/                    # config loading, models, the shared reply_engine (the "brain" call)
│   ├── llm/                     # local (Ollama) + cloud LLM hybrid router
│   ├── vapi/                    # OpenAI-compatible Custom LLM endpoint, server webhook, REST client, provisioning CLI
│   ├── knowledge/                # per-business vector store + ingestion pipeline (RAG)
│   └── training/
│       ├── simulation/          # agent-vs-agent synthetic call training
│       ├── live_feedback/       # webhook-driven recording, review queue, retrain triggers
│       └── eval/                # shared scorecard used by both training loops
├── config/
│   ├── businesses/              # one YAML per business (prompt, Vapi voice, KB, tools)
│   └── voices/                  # Vapi voice provider/id notes per business
├── db/                          # Postgres + pgvector schema, seed data
├── docker/                      # Dockerfile + compose (app, postgres/pgvector, ollama — no Vapi to host)
├── scripts/                     # setup / dev / retrain-cron helper scripts
├── docs/                        # architecture, training, handoff docs
├── tests/
├── Deliverables/                # produced artifacts (per Galaxy Ledger workflow)
└── Archive/                     # deprecated versions / old exports
```

See `docs/ARCHITECTURE.md` for the call flow and `docs/TRAINING.md` for the
full training-loop design.
