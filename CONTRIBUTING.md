# Contributing

Thanks for considering a contribution to SkillLoop.

## Development setup

```bash
python -m pip install -e '.[dev]'
```

## Run checks

```bash
python -m pytest tests/ -q
python -m compileall skillloop tests -q
```

Optional packaging check:

```bash
python -m pip wheel . --no-deps -w /tmp/skillloop-wheel-check
```

## Design constraints

Please preserve these constraints unless a change explicitly updates the architecture:

- no mandatory cloud dependency
- no global Hermes mutation in v1
- no credential storage
- review-before-apply behavior
- generated local state remains gitignored

## Adding adapters

New adapters should normalize runtime-specific trace formats into `AgentTrace` as early as possible.

Adapters should tolerate unknown fields and avoid throwing away source metadata.

## Adding exporters

Exporters should write explicit user-selected output paths and should document their JSONL record shape.

## Pull request checklist

- [ ] Tests pass
- [ ] README or docs updated if behavior changed
- [ ] No secrets or generated `.skillloop/` state committed
- [ ] Sample workflow still works
