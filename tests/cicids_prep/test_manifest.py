from __future__ import annotations

import hashlib
from pathlib import Path

from cicids_prep.manifest import build_dataset_manifest


def test_sha256_matches_manual_computation(tmp_path: Path):
    f = tmp_path / "monday.csv"
    f.write_text("id,Label\n1,BENIGN\n", encoding="utf-8")
    expected = hashlib.sha256(f.read_bytes()).hexdigest()

    manifest = build_dataset_manifest({"monday": f}, repo_root=tmp_path)

    assert manifest["file_sha256"]["monday"] == expected


def test_manifest_never_has_original_download_date(tmp_path: Path):
    f = tmp_path / "monday.csv"
    f.write_text("id,Label\n1,BENIGN\n", encoding="utf-8")

    manifest = build_dataset_manifest({"monday": f}, repo_root=tmp_path)

    assert "original_download_date" not in manifest
    assert "manifest_created_at" in manifest


def test_repo_commit_hash_none_when_not_a_git_repo(tmp_path: Path):
    f = tmp_path / "monday.csv"
    f.write_text("id,Label\n1,BENIGN\n", encoding="utf-8")

    manifest = build_dataset_manifest({"monday": f}, repo_root=tmp_path)

    assert manifest["repo_commit_hash"] is None
