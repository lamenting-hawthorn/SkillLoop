from __future__ import annotations

from skillloop.schema import AgentTrace, Evaluation

EVALUATOR_NAME = "rubric_legacy"
EVALUATOR_VERSION = "0.1"

ERROR_WORDS = ("traceback", "error", "failed", "exception")
SUCCESS_WORDS = ("done", "verified", "tests pass", "passed", "created", "saved")
CORRECTION_WORDS = ("wrong", "incorrect", "no,", "actually", "don't", "do not", "remember")


def evaluate_trace(trace: AgentTrace) -> Evaluation:
    """Simple legacy heuristic for replay comparisons.

    This intentionally mirrors the pre-evidence era: mostly lexical, no tool span
    provenance, and less resistant to claimed success.
    """
    score = 50
    tags: list[str] = []
    notes: list[str] = []
    all_text = "\n".join(message.content.lower() for message in trace.messages)
    assistant_messages = [message for message in trace.messages if message.role == "assistant" and message.content.strip()]
    user_messages = [message for message in trace.messages if message.role == "user"]

    if assistant_messages:
        score += 20
        tags.append("has_final_answer")
    else:
        score -= 20
        tags.append("missing_final_answer")
        notes.append("No assistant answer found in trace.")

    if any(word in all_text for word in SUCCESS_WORDS):
        score += 15
        tags.append("success_signal")
    if any(word in all_text for word in ERROR_WORDS):
        score -= 20
        tags.append("error_signal")
        notes.append("Trace contains error/failure language.")
    if any(any(word in message.content.lower() for word in CORRECTION_WORDS) for message in user_messages):
        score -= 15
        tags.append("user_correction")
        notes.append("User correction/preference signal detected; candidate for learning.")

    return Evaluation(
        trace_id=trace.id,
        score=max(0, min(100, score)),
        tags=tags,
        notes=notes or ["Legacy lexical heuristic."],
        evaluator_name=EVALUATOR_NAME,
        evaluator_version=EVALUATOR_VERSION,
        evidence=[{"kind": "legacy_lexical_summary"}],
        created_from_trace_schema_version=trace.schema_version,
    )
