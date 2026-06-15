# Trace Schema

Current normalized trace schema: `1.1`.

Schema `1.1` remains backward compatible with old `1.0` traces that omit `schema_version`, runtime metadata, adapter metadata, and span-ready tool-call fields. Loaders default missing trace schemas to `1.0` and infer missing tool-call status from the legacy `success` field where possible.

## AgentTrace

```json
{
  "id": "hex",
  "schema_version": "1.1",
  "source": "generic_jsonl|hermes|hermes_state_db|...",
  "created_at": "ISO-8601",
  "runtime": {
    "name": "hermes|generic|...",
    "version": "optional"
  },
  "adapter": {
    "name": "generic_jsonl|hermes|hermes_state_db|...",
    "version": "1.1"
  },
  "metadata": {},
  "raw_artifact_ref": "optional path or URI to preserved raw input",
  "raw_trace_sha256": "optional SHA-256 of preserved raw input",
  "normalized_trace_sha256": "SHA-256 of canonical normalized trace without hash fields",
  "messages": [
    {
      "role": "user|assistant|system|tool",
      "content": "text",
      "tool_calls": [],
      "metadata": {}
    }
  ]
}
```

## AgentMessage

```json
{
  "role": "user|assistant|system|tool",
  "content": "message text",
  "tool_calls": [
    {
      "name": "terminal",
      "arguments": {"command": "pytest"},
      "result": "...",
      "success": true,
      "exit_code": 0
    }
  ],
  "metadata": {
    "line_no": 12
  }
}
```

Adapters should preserve source metadata where possible and tolerate unknown metadata fields.

## ToolCall

Tool calls are span-ready. They can represent either old one-shot calls or future structured spans.

```json
{
  "id": "hex or upstream tool_call_id",
  "name": "terminal",
  "arguments": {},
  "result": "redacted text or null",
  "success": true,
  "started_at": "optional ISO-8601",
  "ended_at": "optional ISO-8601",
  "duration_ms": 1234,
  "exit_code": 0,
  "status": "pending|running|success|error|cancelled|unknown",
  "error_type": "optional machine-readable error class",
  "artifact_refs": ["optional output files or durable artifact refs"]
}
```

## Evaluation

Evaluations are versioned and provenance-bearing.

```json
{
  "id": "hex",
  "trace_id": "hex",
  "evaluator": "rubric",
  "evaluator_version": "1.x",
  "score": 75,
  "passed": true,
  "tags": ["success_signal", "tool_success"],
  "evidence": [
    {
      "kind": "tool_call",
      "summary": "terminal exit_code=0",
      "weight": 1
    }
  ],
  "source_trace_schema_version": "1.1",
  "source_trace_hash": "sha256...",
  "producer_provenance": {}
}
```

Exact evidence shape may evolve, but evidence should remain structured enough to distinguish tool/user/artifact signals from assistant claims.

## Proposal

Proposals are reviewable learning artifacts, not direct mutations.

```json
{
  "id": "hex",
  "trace_id": "hex",
  "kind": "memory|skill",
  "title": "Reusable workflow candidate",
  "content": "markdown or text payload",
  "reason": "why this proposal was created",
  "status": "pending|approved|rejected|applied",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "applied_at": "optional ISO-8601",
  "source_trace_schema_version": "1.1",
  "source_trace_hash": "sha256...",
  "source_evaluation_id": "optional evaluation id",
  "source_evaluation_hash": "optional evaluation hash",
  "producer_provenance": {}
}
```

## SFT export

SFT records are chat-style records with provenance metadata.

```json
{
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "metadata": {
    "trace_id": "...",
    "evaluation_id": "..."
  }
}
```

## DPO export

DPO export is conservative in v1 and only exports explicit preference pairs in trace metadata.

```json
{
  "prompt": "...",
  "chosen": "...",
  "rejected": "...",
  "metadata": {
    "trace_id": "...",
    "evaluation_id": "..."
  }
}
```

## Dataset manifest

Dataset exports write manifests by default.

Manifests include:

- dataset kind
- output files
- split summaries
- record counts
- estimated token counts
- source trace IDs
- evaluation/proposal provenance summaries
- export metadata

Manifests are required input for training config generation.
