"""
Agent-vs-agent training: one LLM plays a synthetic "caller" persona (driven by
a scenario file), the other IS the real agent brain — the exact same
`generate_agent_reply()` used by the live Vapi Custom-LLM endpoint
(app/core/reply_engine.py). So a passing simulation run means the real thing
will behave the same way; there's no separate "test agent" to drift out of
sync.

Usage:
    python -m app.training.simulation.simulate_calls --business kb_plumbing --n 20
"""
import argparse
import asyncio
import json
import uuid
from pathlib import Path

import yaml

from app.core.config_loader import load_business_config_by_id
from app.core.models import Turn
from app.core.reply_engine import generate_agent_reply
from app.llm.engine import LLMEngine
from app.training.eval.scorecard import score_transcript

SCENARIO_DIR = Path(__file__).parent / "scenarios"
RESULTS_DIR = Path(__file__).parent / "results"
_caller_engine = LLMEngine()


async def run_simulation(business_id: str, num_calls: int = 20, max_turns: int = 8) -> dict:
    config = load_business_config_by_id(business_id)
    scenarios = _load_scenarios(business_id)

    results = []
    for i in range(num_calls):
        scenario = scenarios[i % len(scenarios)]
        transcript = await _run_one_call(config, scenario, max_turns)
        score = score_transcript([t.model_dump() for t in transcript], scenario)
        results.append({
            "scenario": scenario["name"], "score": score,
            "transcript": [t.model_dump() for t in transcript],
        })

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"{business_id}_{uuid.uuid4().hex[:8]}.json"
    out_path.write_text(json.dumps(results, indent=2))

    failing = [r for r in results if r["score"]["overall"] < 0.7]
    return {
        "business_id": business_id,
        "calls_run": num_calls,
        "avg_score": sum(r["score"]["overall"] for r in results) / len(results),
        "failing_calls": len(failing),
        "results_file": str(out_path),
    }


async def _run_one_call(config, scenario: dict, max_turns: int) -> list[Turn]:
    transcript: list[Turn] = [Turn(role="agent",
        content="Hello, thanks for calling! How can I help you today?")]

    for _ in range(max_turns):
        caller_line = await _caller_engine.respond(
            system_prompt=f"{scenario['caller_persona']}\nYour goal: {scenario['goal']}. "
                          f"Reply as the caller only, one short sentence.",
            context="", user_text=transcript[-1].content, tier="local",
        )
        transcript.append(Turn(role="user", content=caller_line))

        agent_line = await generate_agent_reply(config, transcript)
        transcript.append(Turn(role="agent", content=agent_line))

        if _looks_resolved(caller_line):
            break

    return transcript


def _looks_resolved(text: str) -> bool:
    return any(w in text.lower() for w in ("thank you", "that's all", "goodbye", "bye"))


def _load_scenarios(business_id: str) -> list[dict]:
    path = SCENARIO_DIR / f"{business_id}.yaml"
    if not path.exists():
        path = SCENARIO_DIR / "default.yaml"
    return yaml.safe_load(path.read_text())["scenarios"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--business", required=True)
    parser.add_argument("--n", type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run_simulation(args.business, args.n)), indent=2))
