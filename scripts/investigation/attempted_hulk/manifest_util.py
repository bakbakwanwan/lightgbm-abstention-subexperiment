"""run_manifest.json 생성 (조사 전용, cicids_prep.manifest 로직 재사용)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from cicids_prep.manifest import _repo_commit_hash, _sha256_file


def build_run_manifest(
    input_paths: dict[str, Path],
    repo_root: Path,
    resolved_columns: dict,
    notes: dict | None = None,
) -> dict:
    return {
        "file_sha256": {day: _sha256_file(p) for day, p in input_paths.items()},
        "repo_commit_hash": _repo_commit_hash(repo_root),
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "resolved_columns": resolved_columns,
        "notes": notes or {},
    }
