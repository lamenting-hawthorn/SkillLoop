from __future__ import annotations

from skillloop.eval.evidence import command_execution_evidence, file_artifact_evidence, test_execution_evidence, user_feedback_evidence
from skillloop.schema import AgentTrace, Evaluation, ToolCall

EVALUATOR_NAME = "rubric"
EVALUATOR_VERSION = "1.2"

CORRECTION_WORDS = ("wrong", "incorrect", "no,", "actually", "don't", "do not")
LEARNING_WORDS = ("remember", "i prefer", "always", "never")
ERROR_WORDS = ("traceback", "error", "failed", "exception", "401", "403", "500")
SUCCESS_WORDS = ("done", "verified", "tests pass", "tests passed", "passed", "created", "saved")


def _tool_calls(trace: AgentTrace) -> list[ToolCall]:
    return [call for message in trace.messages for call in message.tool_calls]


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _evidence(kind: str, **payload: object) -> dict[str, object]:
    return {"kind": kind, **payload}


def evaluate_trace(trace: AgentTrace) -> Evaluation:
    """Score a trace using observable evidence before lexical hints.

    This remains deterministic and lightweight, but it avoids treating user text
    as proof of success and uses tool-call success/failure flags when present.
    """
    score = 50
    tags: list[str] = []
    notes: list[str] = []
    evidence: list[dict[str, object]] = []

    assistant_messages = [m for m in trace.messages if m.role == "assistant" and m.content.strip()]
    user_messages = [m for m in trace.messages if m.role == "user"]
    calls = _tool_calls(trace)
    assistant_text = "\n".join(m.content.lower() for m in assistant_messages)
    tool_result_text = "\n".join(str(call.result or "").lower() for call in calls)
    evidence_text = f"{assistant_text}\n{tool_result_text}"

    evidence.append(
        _evidence(
            "trace_summary",
            messages=len(trace.messages),
            assistant_messages=len(assistant_messages),
            user_messages=len(user_messages),
            tool_calls=len(calls),
            trace_schema_version=trace.schema_version,
        )
    )

    if assistant_messages:
        tags.append("has_final_answer")
        score += 15
        evidence.append(_evidence("assistant_answer", count=len(assistant_messages), delta=15))
    else:
        tags.append("missing_final_answer")
        notes.append("No assistant answer found in trace.")
        score -= 20
        evidence.append(_evidence("missing_assistant_answer", delta=-20))

    successful_tools = [call for call in calls if call.success is True or call.status == "success"]
    failed_tools = [call for call in calls if call.success is False or call.status == "error"]
    unknown_tools = [call for call in calls if call not in successful_tools and call not in failed_tools]

    if successful_tools:
        tags.append("tool_success")
        delta = min(20, 8 + 4 * len(successful_tools))
        score += delta
        notes.append(f"Trace has {len(successful_tools)} successful tool call(s).")
        evidence.append(_evidence("tool_success", count=len(successful_tools), delta=delta, tool_call_ids=[call.id for call in successful_tools]))

    if failed_tools:
        tags.append("tool_failure")
        delta = -min(30, 12 + 6 * len(failed_tools))
        score += delta
        notes.append(f"Trace has {len(failed_tools)} failed tool call(s).")
        evidence.append(
            _evidence(
                "tool_failure",
                count=len(failed_tools),
                delta=delta,
                tool_call_ids=[call.id for call in failed_tools],
                exit_codes=[call.exit_code for call in failed_tools],
                error_types=[call.error_type for call in failed_tools],
            )
        )

    if unknown_tools:
        tags.append("tool_success_unknown")
        notes.append(f"Trace has {len(unknown_tools)} tool call(s) without success metadata.")
        evidence.append(_evidence("tool_success_unknown", count=len(unknown_tools), tool_call_ids=[call.id for call in unknown_tools]))

    structured_evidence = (
        command_execution_evidence(calls)
        + test_execution_evidence(calls)
        + file_artifact_evidence(calls)
        + user_feedback_evidence(trace.messages, CORRECTION_WORDS, LEARNING_WORDS)
    )
    evidence.extend(structured_evidence)
    if any(item["kind"] == "command_execution" for item in structured_evidence):
        tags.append("command_evidence")
    if any(item["kind"] == "test_execution" for item in structured_evidence):
        tags.append("test_evidence")
    if any(item["kind"] == "file_artifact" for item in structured_evidence):
        tags.append("file_artifact_evidence")
    if any(item["kind"] == "user_feedback" for item in structured_evidence):
        tags.append("user_feedback_evidence")

    if _contains_any(evidence_text, SUCCESS_WORDS):
        tags.append("success_signal")
        score += 10
        evidence.append(_evidence("success_language", delta=10))

    if _contains_any(evidence_text, ERROR_WORDS):
        tags.append("error_signal")
        notes.append("Assistant/tool evidence contains error or failure language.")
        score -= 15
        evidence.append(_evidence("error_language", delta=-15))

    if any(any(word in m.content.lower() for word in CORRECTION_WORDS) for m in user_messages):
        tags.append("user_correction")
        notes.append("User correction detected; candidate for learning, but quality is lower.")
        score -= 15
        evidence.append(_evidence("user_correction", delta=-15))

    if any(any(word in m.content.lower() for word in LEARNING_WORDS) for m in user_messages):
        tags.append("learning_signal")
        notes.append("User preference or durable learning signal detected.")
        evidence.append(_evidence("learning_language"))

    if failed_tools and not successful_tools:
        score = min(score, 65)
        evidence.append(_evidence("failed_tools_cap", max_score=65))

    score = max(0, min(100, score))
    if not notes and score >= 70:
        notes.append("Trace appears complete enough for learning/export.")

    return Evaluation(
        trace_id=trace.id,
        score=score,
        tags=tags,
        notes=notes,
        evaluator_name=EVALUATOR_NAME,
        evaluator_version=EVALUATOR_VERSION,
        evidence=evidence,
        created_from_trace_schema_version=trace.schema_version,
    )
