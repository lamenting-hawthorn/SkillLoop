from __future__ import annotations

from skillloop.schema import AgentTrace, Evaluation


CORRECTION_WORDS = ("wrong", "incorrect", "no,", "actually", "don't", "do not", "remember")
ERROR_WORDS = ("traceback", "error", "failed", "exception", "401", "403", "500")
SUCCESS_WORDS = ("done", "verified", "tests pass", "passed", "created", "saved")


def evaluate_trace(trace: AgentTrace) -> Evaluation:
    score = 50
    tags: list[str] = []
    notes: list[str] = []

    assistant_messages = [m for m in trace.messages if m.role == "assistant" and m.content.strip()]
    user_messages = [m for m in trace.messages if m.role == "user"]
    all_text = "\n".join(m.content.lower() for m in trace.messages)

    if assistant_messages:
        tags.append("has_final_answer")
        score += 20
    else:
        tags.append("missing_final_answer")
        notes.append("No assistant answer found in trace.")
        score -= 20

    if any(word in all_text for word in SUCCESS_WORDS):
        tags.append("success_signal")
        score += 15

    if any(word in all_text for word in ERROR_WORDS):
        tags.append("error_signal")
        notes.append("Trace contains error/failure language.")
        score -= 20

    if any(any(word in m.content.lower() for word in CORRECTION_WORDS) for m in user_messages):
        tags.append("user_correction")
        notes.append("User correction/preference signal detected; candidate for learning.")
        score -= 15

    score = max(0, min(100, score))
    if not notes and score >= 70:
        notes.append("Trace appears complete enough for learning/export.")

    return Evaluation(trace_id=trace.id, score=score, tags=tags, notes=notes)
