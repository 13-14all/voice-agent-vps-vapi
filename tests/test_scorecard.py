from app.training.eval.scorecard import score_transcript


def test_score_transcript_basic():
    transcript = [
        {"role": "agent", "content": "Hello, how can I help?"},
        {"role": "user", "content": "What time do you open Saturday?"},
        {"role": "agent", "content": "We open at 9am on Saturday."},
    ]
    scenario = {"goal": "Find out what time the business opens on Saturday."}
    score = score_transcript(transcript, scenario)
    assert 0 <= score["overall"] <= 1
    assert score["hygiene"] == 1.0
