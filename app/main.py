"""
FastAPI entrypoint. Vapi handles telephony/STT/TTS; this app is the brain
(OpenAI-compatible Custom LLM endpoint), the post-call ingestion point
(server webhook), and the training control surface.
"""
from fastapi import FastAPI

from app.vapi.custom_llm import router as vapi_llm_router
from app.vapi.webhook import router as vapi_webhook_router

app = FastAPI(title="Voice Agent VPS (Vapi)")
app.include_router(vapi_llm_router)
app.include_router(vapi_webhook_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/training/simulate")
async def trigger_simulation(business_id: str, num_calls: int = 20):
    """Kick off an agent-vs-agent synthetic training run for one business."""
    from app.training.simulation.simulate_calls import run_simulation
    result = await run_simulation(business_id, num_calls)
    return result


@app.post("/training/review/{call_id}/approve")
async def approve_review(call_id: str, corrected_answer: str | None = None):
    """Human approves a flagged real-call transcript -> folds correction into
    the business knowledge base / eval scenario set."""
    from app.training.live_feedback.review_queue import approve_and_fold_back
    return await approve_and_fold_back(call_id, corrected_answer)
