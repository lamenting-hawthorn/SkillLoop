# Trace Schema

V1 normalized trace:

```json
{
  "id": "hex",
  "source": "generic_jsonl|hermes|...",
  "created_at": "ISO-8601",
  "metadata": {},
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

SFT export format:

```json
{"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
```

DPO export format:

```json
{"prompt":"...","chosen":"...","rejected":"..."}
```

DPO export is conservative in V1 and only exports explicit preference pairs in trace metadata.
