"""
The ONE function that decides what the agent says next. Both the live Vapi
Custom-LLM endpoint (app/vapi/custom_llm.py) and the agent-vs-agent
simulator (app/training/simulation/simulate_calls.py) call this exact
function, so testing a business in simulation is testing the real thing —
no drift between "what we tested" and "what callers get". This module is
intentionally provider-agnostic (it doesn't know about Vapi or Retell) so it
can be shared verbatim across integration layers.
"""
from app.core.models import BusinessConfig, Turn
from app.llm.engine import LLMEngine
from app.knowledge.stores.vector_store import retrieve_context

_engine = LLMEngine()


async def generate_agent_reply(config: BusinessConfig, transcript: list[Turn]) -> str:
    last_user_line = next((t.content for t in reversed(transcript) if t.role == "user"), "")
    context = retrieve_context(config.knowledge_namespace, last_user_line) if last_user_line else ""

    history = "\n".join(f"{t.role}: {t.content}" for t in transcript[-8:])  # short rolling window

    return await _engine.respond(
        system_prompt=config.system_prompt,
        context=context,
        user_text=f"Conversation so far:\n{history}\n\nRespond as the agent's next line only.",
        tier=config.llm_tier,
    )
