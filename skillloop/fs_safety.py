from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from skillloop.errors import PersistenceError

FILE_MODE = 0o600
DIR_MODE = 0o700


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


def ensure_secure_dir(path: str | Path, *, mode: int = DIR_MODE) -> Path:
    """Create directory (and parents) with conservative permissions."""
    out = Path(path)
    out.mkdir(mode=mode, parents=True, exist_ok=True)
    try:
        os.chmod(out, mode)
    except OSError:
        pass
    return out


def _write_atomic(path: str | Path, data: bytes, *, mode: int = FILE_MODE) -> Path:
    """Write bytes atomically via a temp file + ``os.replace`` rename.

    A crash mid-write leaves the original file intact; the temp file is never
    promoted to the final name until fully flushed. Parent dirs are created with
    conservative permissions.
    """
    out = Path(path)
    ensure_secure_dir(out.parent, mode=DIR_MODE)
    fd, tmp_name = tempfile.mkstemp(dir=str(out.parent), prefix=f".{out.name}.tmp-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, out)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return out


def atomic_write_text(
    path: str | Path,
    text: str,
    *,
    encoding: str = "utf-8",
    mode: int = FILE_MODE,
) -> Path:
    return _write_atomic(path, text.encode(encoding), mode=mode)


def atomic_write_json(
    path: str | Path,
    obj: object,
    *,
    indent: int = 2,
    ensure_ascii: bool = False,
    mode: int = FILE_MODE,
) -> Path:
    text = json.dumps(obj, indent=indent, ensure_ascii=ensure_ascii) + "\n"
    return atomic_write_text(path, text, mode=mode)
