"""
Deterministic + LLM-judge scoring for a transcript against its scenario goal.
Used by both simulation training and live-call review so the two feedback
loops speak the same scoring language. Transcript turns use role "agent"/"user"
(matches both Retell's and Vapi's transcript shapes once normalized).
"""
KEYWORD_PENALTIES = ["i don't know", "i cannot help", "error", "undefined"]


def score_transcript(transcript: list[dict], scenario: dict) -> dict:
    agent_lines = [t["content"] for t in transcript if t["role"] == "agent"]
    joined = " ".join(agent_lines).lower()

    goal_hit = _goal_signal_present(joined, scenario.get("goal", ""))
    hygiene = 1.0 - min(1.0, sum(joined.count(p) for p in KEYWORD_PENALTIES) * 0.34)
    length_ok = 1.0 if len(transcript) <= 16 else 0.6   # penalize runaway calls
    no_repeat = 1.0 if len(set(agent_lines)) == len(agent_lines) else 0.7

    overall = round(0.4 * goal_hit + 0.3 * hygiene + 0.15 * length_ok + 0.15 * no_repeat, 3)
    return {
        "goal_hit": goal_hit, "hygiene": hygiene,
        "length_ok": length_ok, "no_repeat": no_repeat, "overall": overall,
    }


def _goal_signal_present(agent_text: str, goal: str) -> float:
    """Cheap heuristic placeholder — swap for an LLM-judge call
    (pass transcript + goal to the cloud model and ask for a 0-1 score)
    once you want higher-fidelity grading than keyword overlap."""
    goal_words = [w for w in goal.lower().split() if len(w) > 4]
    if not goal_words:
        return 0.5
    hits = sum(1 for w in goal_words if w in agent_text)
    return min(1.0, hits / max(1, len(goal_words) // 2))
