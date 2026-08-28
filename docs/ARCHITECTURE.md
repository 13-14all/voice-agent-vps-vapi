## Call flow

```
Customer calls a Vapi-managed (or imported) number
        ↓
Vapi handles: telephony, STT, TTS, turn-taking, interruption/barge-in
        ↓
Vapi POSTs to OUR server: POST /vapi/chat/completions
   (standard OpenAI chat-completion body + a `call` object with assistantId)
        ↓
_resolve_business(): load_business_config_by_vapi_assistant_id(call.assistantId)
        ↓
_to_turns(): map OpenAI messages -> our Turn list (system message dropped —
   reply_engine injects the business's own system_prompt instead)
        ↓
app/core/reply_engine.generate_agent_reply(config, transcript):
   vector_store.retrieve_context(namespace, last_user_line)  (Postgres + pgvector)
        ↓
   LLMEngine.respond(system_prompt, context, text, tier)
        local Ollama (simple turns) ⇄ cloud model (complex/reasoning turns)
        ↓
We stream back an OpenAI-shaped SSE response — Vapi speaks it, handles the
audio entirely
        ↓
Call ends → Vapi POSTs `end-of-call-report` to /vapi/webhook:
   full transcript + analysis.successEvaluation + analysis.structuredData
        ↓
call_recorder.persist_call() → auto-scored (same scorecard as simulation),
   optionally flagged for human review
```

## One engine, many agents

Nothing in `app/` is business-specific. Everything that varies per tenant
lives in `businesses` (Postgres) / `config/businesses/*.yaml`:

- `system_prompt` — personality + instructions (used by OUR reply_engine —
  Vapi's Custom LLM mode never generates text itself, it just calls us)
- `vapi_voice_provider` / `vapi_voice_id` — which TTS voice this business uses
- `vapi_first_message` — opening line
- `knowledge_namespace` — which `knowledge_chunks` rows this tenant can see
- `tools` — which tool integrations are enabled (booking, calendar, CRM, ...)
- `llm_tier` — local / cloud / hybrid routing preference

Each business still needs one **Vapi Assistant** created
(`app/vapi/provision.py` does this from the YAML) — that's where the phone
number and voice live on Vapi's side — but every one of those assistants
points at the exact same `/vapi/chat/completions` endpoint on this server.
Adding business #50 is: write a YAML, run `provision.py` once, done.

### Two routing modes

| Mode | How it works | When to use |
|---|---|---|
| **Static (default)** | One Vapi Assistant + one Vapi phone number per business; we resolve the business from `call.assistantId` in every Custom LLM request. | Simplest, matches the Retell edition's model 1:1. |
| **Dynamic (`assistant-request`)** | A single Vapi number (or a set of forwarded numbers) has no static assistant; Vapi calls our `/vapi/webhook` `assistant-request` handler on every inbound call, and we return the right assistant config based on the dialed number. | Matches the original brainstorm's "several virtual numbers forwarded to one agent number, voice/knowledge picked by which number was dialed" idea. |

Both are implemented; pick one per business (or mix) based on how you want
to manage phone numbers.

## Vapi vs. self-hosted STT/TTS

| Concern | Vapi (this version) | Self-hosted (original version) |
|---|---|---|
| Telephony | Vapi-managed numbers or bring-your-own (Twilio import) | Twilio direct |
| STT/TTS | Vapi's pipeline (sub-700ms latency, many provider choices) | Deepgram + ElevenLabs/Piper, self-orchestrated |
| Interruption/barge-in | Built into Vapi | Hand-rolled in the media-stream loop |
| Custom LLM protocol | OpenAI-compatible `/chat/completions` — no bespoke protocol to learn | N/A |
| What we host | One HTTP endpoint (text in/out) + Postgres/pgvector + Ollama | Full telephony + STT + TTS + LLM stack |
| Post-call analysis | Vapi's `end-of-call-report` webhook (transcript + structured analysis) | We built our own from scratch |

## Hybrid LLM routing

`app/llm/engine.py` sends short, low-ambiguity turns (hours, yes/no,
greetings) to the local Ollama model to keep latency and cost down, and
routes anything longer or reasoning-heavy (booking logic, objections,
multi-step asks) to the cloud model. The heuristic is intentionally simple
and swappable — replace `_looks_simple` with a classifier once you have
labeled call data (the live-call feedback loop naturally produces this).

Note: this repo currently returns one full reply per turn as a single SSE
delta chunk rather than token-by-token streaming. For lower perceived
latency, upgrade `LLMEngine` to yield tokens and stream multiple deltas
before the final `[DONE]` — the OpenAI-compatible protocol supports it, this
scaffold just keeps the first version simple.

## Data stores

| Store    | Holds                                                        |
|----------|------------------------------------------------------------------|
| Postgres | Businesses (incl. `vapi_assistant_id`), call transcripts + Vapi's own analysis, `knowledge_chunks` (pgvector), `simulation_runs` |
