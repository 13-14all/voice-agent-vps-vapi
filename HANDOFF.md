# Handoff Note

**Agent focus:** Vapi.ai-specific build of the Voice Agent VPS scaffold — an
OpenAI-compatible Custom LLM brain, per-business RAG knowledge base, and the
three-loop training system (business-knowledge ingestion, agent-vs-agent
simulation, Vapi-webhook-driven live-caller feedback). Sibling to
`voice-agent-vps` (the Retell edition) — same training philosophy, different
provider integration layer (`app/vapi/` vs `app/retell/`).

**Expected output type:** Working FastAPI service exposing an OpenAI-shaped
`/vapi/chat/completions` endpoint + a `/vapi/webhook` server-event handler,
deployable via `docker/docker-compose.yml`, plus a provisioning CLI that
creates/updates Vapi assistants from config.

**Context / reading order:**
1. `README.md` — repo map and quick start
2. `docs/ARCHITECTURE.md` — call flow, static vs. dynamic routing, Vapi vs. self-hosted comparison
3. `docs/TRAINING.md` — the three training loops in detail
4. `db/migrations/001_init.sql` — schema
5. `config/businesses/*.yaml` — example tenant configs
6. `app/vapi/custom_llm.py` + `app/core/reply_engine.py` — trace one call end to end

**Acceptance criteria:**
- [ ] `docker compose -f docker/docker-compose.yml up` boots app + postgres + ollama
- [ ] Server is reachable over TLS (Vapi requires https — use a reverse proxy or tunnel for local testing)
- [ ] `python -m app.vapi.provision --business plumbing_co --attach-number +1... --twilio-sid ... --twilio-token ...` creates a working Vapi assistant
- [ ] A test call answers with the business's first message and uses its knowledge base
- [ ] `POST /vapi/webhook` with an `end-of-call-report` test payload (or a real test call) inserts a row into `calls`
- [ ] `python -m app.training.simulation.simulate_calls --business kb_plumbing --n 5` runs end-to-end and writes a results JSON
- [ ] `pytest tests/` passes

**Confirmation phrase for builder agent initialization:**
> "Hermes, please execute Queue → Immediate Tasks using context from
> Project_Ledger.txt and reference architecture notes found in
> docs/ARCHITECTURE.md §Call flow."

---
⏱️ Event Log
Action: Vapi-specific repo created
Initiator: Galaxy.ai
Timestamp: 2026-08-28
Summary: Forked the Retell-edition scaffold into a new repo built around
Vapi's OpenAI-compatible Custom LLM integration and server-event webhook.
---
