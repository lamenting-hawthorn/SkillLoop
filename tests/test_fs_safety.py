import pytest

from skillloop.fs_safety import ensure_not_symlink_escape, resolve_under_root, safe_path_segment, sha256_bytes


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
