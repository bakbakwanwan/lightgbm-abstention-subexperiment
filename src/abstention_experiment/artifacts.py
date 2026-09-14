from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def distribution_values(frame: pd.DataFrame) -> dict[str, float]:
    values: dict[str, float] = {}
    for column in ("p_attack", "confidence"):
        series = frame[column]
        values[f"{column}_min"] = float(series.min())
        for quantile, name in zip((0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99), ("p01", "p05", "p25", "p50", "p75", "p95", "p99")):
            values[f"{column}_{name}"] = float(series.quantile(quantile))
        values[f"{column}_max"] = float(series.max())
    return values

