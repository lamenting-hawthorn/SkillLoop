from __future__ import annotations

import hashlib
import os
from pathlib import Path


def resolve_under_root(root: str | Path, path: str | Path, *, label: str) -> Path:
    """Resolve path and require it to stay under root."""
    boundary = Path(root).expanduser().resolve()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = boundary / candidate
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(boundary)
    except ValueError as exc:
        raise ValueError(f"{label} must stay under {boundary}: {resolved}") from exc
    return resolved


def safe_path_segment(value: str, *, label: str) -> str:
    segment = str(value)
    if not segment or segment in {".", ".."}:
        raise ValueError(f"{label} must be a non-empty safe path segment")
    if len(segment) > 255:
        raise ValueError(f"{label} is too long")
    separators = {"/", "\\", os.sep}
    if os.altsep:
        separators.add(os.altsep)
    if any(separator and separator in segment for separator in separators):
        raise ValueError(f"{label} must not contain path separators")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in segment):
        raise ValueError(f"{label} must not contain control characters")
    return segment


def ensure_not_symlink_escape(path: str | Path, boundary: str | Path, *, label: str) -> Path:
    """Reject paths whose existing target or symlinked ancestors escape boundary."""
    allowed = Path(boundary).expanduser().resolve()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = allowed / candidate
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(f"{label} must not escape {allowed}: {resolved}") from exc
    return resolved


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
