from __future__ import annotations

from pathlib import Path
import zipfile
from typing import Any

from .data import sha256_file
from .layer2_common import read_json, resolve_bundle_path, utc_now, write_json


def package_transfer_bundle(export_dir: Path, archive_path: Path) -> dict[str, Any]:
    if archive_path.exists():
        raise FileExistsError(f"Transfer archive already exists: {archive_path}")
    manifest_path = export_dir / "manifest.json"
    manifest = read_json(manifest_path)
    members = manifest.get("transfer_contract", {}).get("copy_to_llm_environment")
    if not isinstance(members, list) or not members:
        raise ValueError("Export manifest has no transfer member list")
    if members.count("manifest.json") != 1 or any(not isinstance(item, str) for item in members):
        raise ValueError("Transfer member list is invalid")
    resolved = [(relative, resolve_bundle_path(export_dir, relative)) for relative in members]
    missing = [relative for relative, path in resolved if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Transfer members are missing: {missing}")
    if any(relative.startswith("local/") or relative == "local" for relative, _ in resolved):
        raise ValueError("Local evaluation artifacts must not enter the transfer archive")

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative, path in resolved:
            archive.write(path, arcname=relative)

    package_manifest = {
        "package_schema_version": "e9-transfer-package-v1",
        "created_at": utc_now(),
        "run_id": manifest["run_id"],
        "archive": {
            "filename": archive_path.name,
            "sha256": sha256_file(archive_path),
            "bytes": archive_path.stat().st_size,
        },
        "members": members,
    }
    write_json(archive_path.with_suffix(".manifest.json"), package_manifest)
    return package_manifest
