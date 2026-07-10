# Security Policy

## Reporting a Vulnerability

Please report security vulnerabilities **privately**. Do not open a public GitHub issue.

You can report a vulnerability in either of the following ways:

- **GitHub Security Advisories (preferred):** use the
  [Report a vulnerability](https://github.com/lamenting-hawthorn/skillloop/security/advisories/new)
  form. This keeps the report confidential until a fix is released.
- **Email:** send details to `security@example.com`. Use GPG if possible; a maintainer will acknowledge receipt within 3 business days.

You will receive an acknowledgement of your report, and we will keep you informed as we
investigate and prepare a fix. Once a fix is released we will credit you (with your consent).

## Supported Versions

See [SUPPORTED_VERSIONS.md](./SUPPORTED_VERSIONS.md) for the full support window. The
currently supported release line is:

| Version | Supported |
| ------- | --------- |
| 0.2.x   | ✅        |
| 0.1.x   | ❌        |

## What to Include in a Report

Please include as much of the following as possible:

- A description of the vulnerability and its impact
- Affected version(s) of SkillLoop and Python/runtime
- Steps to reproduce, or a proof-of-concept
- Any relevant logs or crash output (redacted of secrets)
- Suggested mitigation, if known

## Scope Notes

SkillLoop is a local-first tool. Most attack surface is the local SQLite store and any
adapters that read external trace files. Reports about unsafe handling of untrusted trace
data, state tampering, or secret exposure in reports are especially welcome.
