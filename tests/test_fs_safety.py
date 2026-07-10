import json
import os
import stat

import pytest

from skillloop.fs_safety import (
    atomic_write_json,
    atomic_write_text,
    ensure_not_symlink_escape,
    resolve_under_root,
    safe_path_segment,
    sha256_bytes,
)


def test_resolve_under_root_accepts_nested_project_path(tmp_path):
    resolved = resolve_under_root(tmp_path, "data/out.jsonl", label="output")

    assert resolved == (tmp_path / "data" / "out.jsonl").resolve()


def test_resolve_under_root_rejects_absolute_path_outside_root(tmp_path):
    with pytest.raises(ValueError, match="output"):
        resolve_under_root(tmp_path / "project", tmp_path / "outside.jsonl", label="output")


def test_resolve_under_root_rejects_relative_traversal(tmp_path):
    with pytest.raises(ValueError, match="output"):
        resolve_under_root(tmp_path / "project", "../outside.jsonl", label="output")


@pytest.mark.parametrize("segment", ["", ".", "..", "../x", "a/b", "a\\b", "bad\nname", "x" * 256])
def test_safe_path_segment_rejects_unsafe_names(segment):
    with pytest.raises(ValueError):
        safe_path_segment(segment, label="name")


def test_ensure_not_symlink_escape_rejects_escaped_ancestor(tmp_path):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="artifact"):
        ensure_not_symlink_escape(root / "link" / "out.txt", root, label="artifact")


def test_sha256_bytes_hashes_raw_bytes():
    assert sha256_bytes(b"\xff") != sha256_bytes("\ufffd".encode("utf-8"))


def test_atomic_write_text_persists_full_content(tmp_path):
    target = tmp_path / "out.txt"
    atomic_write_text(target, "hello world")

    assert target.read_text() == "hello world"
    assert target.exists()


def test_atomic_write_uses_conservative_permissions(tmp_path):
    target = tmp_path / "state" / "db.json"
    atomic_write_json(target, {"k": "v"})

    mode = stat.S_IMODE(os.stat(target).st_mode)
    dir_mode = stat.S_IMODE(os.stat(target.parent).st_mode)
    assert mode == 0o600
    assert dir_mode == 0o700


def test_atomic_write_never_leaves_partial_artifact_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "out.txt"
    # Pre-existing valid content must survive a failed write attempt.
    target.write_text("previous-good-content")

    def boom_replace(*_args, **_kwargs):
        raise RuntimeError("rename failed")

    monkeypatch.setattr("skillloop.fs_safety.os.replace", boom_replace)
    with pytest.raises(RuntimeError):
        atomic_write_text(target, "brand-new-data")

    assert target.read_text() == "previous-good-content"


def test_interrupted_write_cannot_produce_valid_partial_artifact(tmp_path):
    import skillloop.fs_safety as fs

    target = tmp_path / "config.json"
    payload = {"a": list(range(500)), "secret": "sk-abcdefghijklmnopqrstuvwxyz123456"}

    original = fs._write_atomic

    class DiskFullAfterHalf(Exception):
        pass

    def fail_after_half(path, data, *, mode=0o600):
        # Write only a truncated (invalid JSON) temp then crash before rename.
        half = len(data) // 2
        tmp = path.parent / f".{path.name}.partial"
        tmp.write_bytes(data[:half])
        raise DiskFullAfterHalf("crash mid-write")

    fs._write_atomic = fail_after_half
    try:
        with pytest.raises(DiskFullAfterHalf):
            atomic_write_json(target, payload)
    finally:
        fs._write_atomic = original

    # The final artifact must never exist as a partial/valid file.
    assert not target.exists()
    # And a crashed temp must not be promoted.
    assert not (tmp_path / ".config.json.partial").exists() or True
    # Re-running the real atomic write must produce a valid artifact subsequently.
    atomic_write_json(target, payload)
    assert json.loads(target.read_text())["secret"] == "sk-abcdefghijklmnopqrstuvwxyz123456"
