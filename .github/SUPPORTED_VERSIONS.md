# Supported Versions

This document describes which SkillLoop versions and runtime environments receive support.

## Release Support Window

We support the **latest minor release** plus the **immediately previous minor release**.

| Version line | Supported | Notes |
| ------------ | --------- | ----- |
| 0.2.x        | ✅        | Current supported line. |
| 0.1.x        | ❌        | MVP; no longer maintained. |

- **Patch releases** within a supported minor line receive fixes until the next minor line ships.
- When 0.3.0 ships, 0.1.x is dropped and 0.2.x remains supported until 0.4.0.

## Python Versions

| Python | Supported |
| ------ | --------- |
| 3.11   | ✅        |
| 3.12   | ✅        |
| 3.13   | ✅        |
| < 3.11 | ❌        |

## Operating Systems

| Platform | CLI | Recurring controller |
| -------- | --- | -------------------- |
| macOS    | ✅  | ✅                   |
| Linux    | ✅  | ✅                   |
| Windows  | ✅  | ❌ (CLI only)        |

> The recurring controller (policy-driven `controller run`) is only exercised on macOS and
> Linux. The CLI works on Windows but is not part of the controller support matrix.

## Installation Methods

Supported installs: `pipx`, `uv tool`, and a Python `venv`. Pinned GitHub tags
(`v*`, e.g. `v0.2.0`) are supported sources for installing from source.
