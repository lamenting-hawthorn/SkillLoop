from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from skillloop.schema import Evaluation, Proposal, sha256_text, stable_json_dumps

PROVENANCE_VERSION = "1.0"


def callable_source_hash(func: Callable[..., Any]) -> str:
    try:
        source = inspect.getsource(func)
    except (OSError, TypeError):
        source = repr(func)
    return sha256_text(source)


def component_provenance(
    *,
    kind: str,
    name: str,
    version: str,
    func: Callable[..., Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "provenance_version": PROVENANCE_VERSION,
        "kind": kind,
        "name": name,
        "version": version,
    }
    if func is not None:
        payload["source_sha256"] = callable_source_hash(func)
        payload["callable"] = f"{func.__module__}.{func.__qualname__}"
    if extra:
        payload["extra"] = dict(extra)
    payload["component_sha256"] = sha256_text(stable_json_dumps(payload))
    return payload


def artifact_hash(payload: dict[str, Any]) -> str:
    return sha256_text(stable_json_dumps(payload))


def annotate_proposal_provenance(
    proposal: Proposal,
    *,
    source_evaluation: Evaluation | None,
    producer_name: str,
    producer_version: str,
    producer_func: Callable[..., Any],
) -> Proposal:
    if source_evaluation is not None:
        proposal.source_evaluation_id = source_evaluation.id
        proposal.source_evaluation_sha256 = (
            source_evaluation.artifact_sha256 or source_evaluation.compute_artifact_sha256()
        )
        proposal.source_evaluation_provenance = dict(source_evaluation.component_provenance or {})
    proposal.producer_provenance = component_provenance(
        kind="distiller",
        name=producer_name,
        version=producer_version,
        func=producer_func,
    )
    return proposal
