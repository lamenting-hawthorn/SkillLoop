# Compatibility

This page summarizes supported runtimes, operating systems, and install methods for
SkillLoop. The current release is **0.2.0** (schema **v2**).

## Python versions

| Python | Supported |
| ------ | --------- |
| 3.11   | ✅        |
| 3.12   | ✅        |
| 3.13   | ✅        |
| < 3.11 | ❌        |

## Operating systems

| Platform | CLI | Recurring controller |
| -------- | --- | -------------------- |
| macOS    | ✅  | ✅                   |
| Linux    | ✅  | ✅                   |
| Windows  | ✅  | ❌ (CLI only)        |

## Install methods

| Method            | Supported | Notes                                  |
| ----------------- | --------- | -------------------------------------- |
| `pipx install`    | ✅        | Recommended for the CLI.               |
| `uv tool install` | ✅        | Alternative to pipx.                   |
| Python `venv`     | ✅        | `pip install .` inside a venv.         |
| GitHub tag `v*`   | ✅        | `pipx install git+https://github.com/lamenting-hawthorn/skillloop.git@v0.2.0` |

## Schema / version notes

- **0.2.0** upgrades the SQLite store to **schema v2** automatically on first run
  (atomic migration, no data loss). See [migration.md](./migration.md).
- The `v1` → `v2` upgrade adds a `content_hash` column and new indexes for bulk
  insert/query paths.
- Provenance/checksums for published artifacts are produced by the release workflow and
  attached to each GitHub Release as `SHA256SUMS`.
