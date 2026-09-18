from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import re
import uuid
from typing import Any, Iterable


RUN_ID_PATTERN = re.compile(r"^e9-pilot-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_pilot_run_id(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    stamp = current.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"e9-pilot-{stamp}-{uuid.uuid4().hex[:8]}"


def require_valid_run_id(run_id: str) -> None:
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ValueError(f"Invalid E9 pilot run_id: {run_id!r}")


def _reject_nonfinite_json(value: str) -> None:
    raise ValueError(f"Non-finite JSON constant is forbidden: {value}")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_nonfinite_json)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                value = json.loads(line, parse_constant=_reject_nonfinite_json)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_number}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"JSONL line {line_number} is not an object")
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
            handle.write("\n")
            count += 1
    return count


def resolve_bundle_path(bundle_root: Path, relative_path: str) -> Path:
    candidate = (bundle_root / relative_path).resolve()
    root = bundle_root.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"Bundle path escapes its root: {relative_path!r}")
    return candidate
