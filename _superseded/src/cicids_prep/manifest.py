"""dataset_manifest.json 생성 (stage1_briefing.md 1-9).

file_sha256, repo_commit_hash, manifest_created_at만 기록한다.
original_download_date는 알 수 없는 정보이므로 필드 자체를 넣지 않는다 —
검증 항목(7장)이 이 부재를 직접 확인한다.
"""

from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_commit_hash(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def build_dataset_manifest(
    input_paths: dict[str, Path], repo_root: Path
) -> dict:
    file_sha256 = {day: _sha256_file(path) for day, path in input_paths.items()}
    manifest = {
        "file_sha256": file_sha256,
        "repo_commit_hash": _repo_commit_hash(repo_root),
        "manifest_created_at": datetime.now(timezone.utc).isoformat(),
    }
    assert "original_download_date" not in manifest
    return manifest
