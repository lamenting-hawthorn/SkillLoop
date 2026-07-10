from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from skillloop.dataset import (
    build_manifest,
    parse_split_spec,
    split_records,
    write_jsonl,
    write_manifest,
)
from skillloop.export.dpo import export_dpo_records
from skillloop.export.okf import export_okf_bundle
from skillloop.export.sft import export_sft_records
from skillloop.schema import AgentTrace
from skillloop.store import SkillLoopStore

from ._shared import evaluations_by_trace, proposals_by_trace
from .requests import ExportRequest


@dataclass
class ExportResult:
    format: str
    records: int
    output_files: dict[str, Path]
    manifest_path: Path | None
    okf_bundle: Path | None = None


class ExportService:
    def __init__(self, store: SkillLoopStore) -> None:
        self._store = store

    def export(self, traces: list[AgentTrace], req: ExportRequest) -> ExportResult:
        if req.min_score is not None:
            filtered: list[AgentTrace] = []
            for trace in traces:
                evaluations = self._store.list_evaluations(trace.id)
                best_score = max((evaluation.score for evaluation in evaluations), default=None)
                if best_score is not None and best_score >= req.min_score:
                    filtered.append(trace)
            traces = filtered

        evaluations_by_trace_map = evaluations_by_trace(self._store, traces)
        proposals_by_trace_map = proposals_by_trace(self._store, traces)

        if req.format == "okf":
            bundle_path = export_okf_bundle(self._store, Path(req.out))
            return ExportResult(
                format=req.format,
                records=0,
                output_files={},
                manifest_path=None,
                okf_bundle=bundle_path,
            )

        if req.format == "sft":
            records = export_sft_records(
                traces,
                evaluations_by_trace=evaluations_by_trace_map,
                proposals_by_trace=proposals_by_trace_map,
            )
        elif req.format == "dpo":
            records = export_dpo_records(
                traces,
                evaluations_by_trace=evaluations_by_trace_map,
                proposals_by_trace=proposals_by_trace_map,
            )
        else:
            raise SystemExit(f"Unsupported export format: {req.format}")

        split_spec = parse_split_spec(req.splits)
        split_map = split_records(records, split_spec)
        output_files: dict[str, Path] = {}
        out = Path(req.out).resolve()
        if len(split_map) == 1 and "train" in split_map:
            output_files["train"] = write_jsonl(out, split_map["train"])
        else:
            for split_name, split_items in split_map.items():
                split_path = out.with_name(f"{out.stem}.{split_name}{out.suffix or '.jsonl'}")
                output_files[split_name] = write_jsonl(split_path, split_items)

        manifest = build_manifest(
            kind=req.format,
            split_outputs=output_files,
            split_records_map=split_map,
            source_traces=traces,
            evaluations_by_trace=evaluations_by_trace_map,
            proposals_by_trace=proposals_by_trace_map,
            export_metadata={"min_score": req.min_score, "split_spec": req.splits or "train=1.0"},
        )
        manifest_path = (
            Path(req.manifest_out).resolve()
            if req.manifest_out
            else out.with_suffix(out.suffix + ".manifest.json")
        )
        write_manifest(manifest_path, manifest)
        return ExportResult(
            format=req.format,
            records=len(records),
            output_files=output_files,
            manifest_path=manifest_path,
        )


__all__ = ["ExportResult", "ExportService"]
