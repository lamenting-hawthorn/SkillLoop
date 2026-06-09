# Trace Schema

Current normalized trace schema: `1.1`.

Schema `1.1` remains backward compatible with old `1.0` traces that omit `schema_version`, runtime metadata, adapter metadata, and span-ready tool-call fields. Loaders default missing trace schemas to `1.0` and missing tool-call status to `success`, `error`, or `unknown` from the legacy `success` field.

## AgentTrace

```json
{
  "id": "hex",
  "schema_version": "1.1",
  "source": "generic_jsonl|hermes|hermes_state_db|...",
  "created_at": "ISO-8601",
  "runtime": {
    "name": "hermes|openai|anthropic|...",
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

## Exports

SFT export format:

```json
{"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
```

DPO export format:

```json
{"prompt":"...","chosen":"...","rejected":"..."}
```

DPO export is conservative in V1 and only exports explicit preference pairs in trace metadata.
