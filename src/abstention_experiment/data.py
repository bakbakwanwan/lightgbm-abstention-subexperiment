from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .configuration import ExperimentConfig

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday")
PROTOCOL_MAP = {6: "TCP", 17: "UDP", 1: "ICMP", 0: "UNKNOWN"}
PROTOCOL_CATEGORIES = ["TCP", "UDP", "ICMP", "UNKNOWN"]
EXPECTED = {"total": 2_099_976, "target": 1_929_529, "attempted": 11_979, "invalid_class": 158_468}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def load_whitelist(path: Path) -> tuple[list[str], list[str]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    include, exclude = list(value["include"]), list(value["exclude"])
    if len(include) != 59 or len(exclude) != 32 or set(include) & set(exclude):
        raise ValueError("Whitelist must contain 59 included and 32 excluded columns")
    return include, exclude


def map_protocol(series: pd.Series) -> pd.Series:
    if set(series.dropna().astype(str).unique()).issubset(set(PROTOCOL_CATEGORIES)):
        return pd.Series(pd.Categorical(series.astype(str), categories=PROTOCOL_CATEGORIES), index=series.index)
    numeric = pd.to_numeric(series, errors="raise")
    unexpected = sorted(set(numeric.unique()) - set(PROTOCOL_MAP))
    if unexpected:
        raise ValueError(f"Unexpected Protocol values: {unexpected}")
    return pd.Series(pd.Categorical(numeric.map(PROTOCOL_MAP), categories=PROTOCOL_CATEGORIES), index=series.index)


def feature_hash(frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    normalized = frame.loc[:, features].copy()
    normalized["Protocol"] = map_protocol(normalized["Protocol"])
    numeric = [name for name in features if name != "Protocol"]
    normalized[numeric] = normalized[numeric].astype("float64")
    return pd.util.hash_pandas_object(normalized, index=False, categorize=True).to_numpy(dtype=np.uint64)


def validate_sources(config: ExperimentConfig) -> dict:
    manifest = json.loads(config.path("inputs", "split_manifest").read_text(encoding="utf-8"))
    data_dir = config.path("inputs", "data_dir")
    actual = {f"{day}.csv": sha256_file(data_dir / f"{day}.csv") for day in DAYS}
    checks = {
        "dataset_sha_match": actual == manifest["dataset_file_sha256"],
        "source_zip_sha_match": sha256_file(config.path("inputs", "source_zip")) == manifest["source_zip_sha256"],
        "whitelist_sha_match": sha256_file(config.path("inputs", "whitelist")) == manifest["features_whitelist_sha256"],
    }
    if not all(checks.values()):
        raise RuntimeError(f"Input integrity validation failed: {checks}")
    return {"checks": checks, "dataset_file_sha256": actual, "source_zip_sha256": manifest["source_zip_sha256"]}


def load_analysis_frame(config: ExperimentConfig, method: str) -> tuple[pd.DataFrame, dict]:
    include, exclude = load_whitelist(config.path("inputs", "whitelist"))
    chunk_size = int(config.raw["inputs"]["chunk_size"])
    usecols = list(dict.fromkeys(["id", "Label", "Attempted Category"] + include))
    parts: list[pd.DataFrame] = []
    infinity_replaced = 0
    counts = {"total": 0, "target": 0, "attempted": 0, "invalid_class": 0, "train": 0, "test": 0}
    for day in DAYS:
        raw_reader = pd.read_csv(config.path("inputs", "data_dir") / f"{day}.csv", usecols=usecols, chunksize=chunk_size, low_memory=False)
        split_reader = pd.read_csv(config.path("inputs", "split_dir") / method / f"{day}.csv.gz", dtype={"id": "int64", "Label": "string", "observation_group": "string", "split": "string"}, keep_default_na=False, chunksize=chunk_size)
        for raw, assignment in zip(raw_reader, split_reader, strict=True):
            if len(raw) != len(assignment) or not np.array_equal(raw["id"].to_numpy(), assignment["id"].to_numpy()) or not np.array_equal(raw["Label"].astype(str).to_numpy(), assignment["Label"].astype(str).to_numpy()):
                raise RuntimeError(f"Prediction ID alignment failed for {day}")
            raw.insert(0, "day", day)
            raw["observation_group"] = assignment["observation_group"].astype("string")
            raw["split"] = assignment["split"].astype("string")
            raw["Protocol"] = map_protocol(raw["Protocol"])
            values = pd.to_numeric(raw["Flow Bytes/s"], errors="raise").to_numpy(dtype=np.float64)
            bad = np.isinf(values)
            infinity_replaced += int(bad.sum())
            raw.loc[bad, "Flow Bytes/s"] = np.nan
            numeric = [name for name in include if name != "Protocol"]
            raw[numeric] = raw[numeric].astype("float64")
            if np.isinf(raw[numeric].to_numpy(dtype=np.float64)).any():
                raise RuntimeError("Infinity remains in model input after Flow Bytes/s conversion")
            target = raw["observation_group"].eq("none")
            raw["binary_label"] = pd.Series(pd.NA, index=raw.index, dtype="Int8")
            raw.loc[target, "binary_label"] = raw.loc[target, "Label"].ne("BENIGN").astype("int8")
            for key in ("attempted", "invalid_class"):
                counts[key] += int(raw["observation_group"].eq(key).sum())
            counts["total"] += len(raw)
            counts["target"] += int(target.sum())
            counts["train"] += int(raw["split"].eq("train").sum())
            counts["test"] += int(raw["split"].eq("test").sum())
            parts.append(raw)
    frame = pd.concat(parts, ignore_index=True)
    expected_counts = {"total": EXPECTED["total"], "target": EXPECTED["target"], "attempted": EXPECTED["attempted"], "invalid_class": EXPECTED["invalid_class"]}
    if any(counts[key] != value for key, value in expected_counts.items()):
        raise RuntimeError(f"Population validation failed: {counts}")
    if counts["train"] != 1_447_147 or counts["test"] != 482_382 or infinity_replaced != 5:
        raise RuntimeError(f"Split/preprocessing validation failed: counts={counts}, infinity={infinity_replaced}")
    if set(include) | set(exclude) != set(pd.read_csv(config.path("inputs", "data_dir") / "monday.csv", nrows=0).columns):
        raise RuntimeError("Whitelist classification differs from the 91-column source header")
    return frame, {"method": method, "counts": counts, "flow_bytes_infinity_to_nan": infinity_replaced, "feature_count": len(include)}


def internal_validation_mask(train: pd.DataFrame, features: list[str], fraction: float, seed: int) -> np.ndarray:
    hashes = feature_hash(train, features)
    table = pd.DataFrame({"feature_hash": hashes, "Label": train["Label"].astype(str).to_numpy()})
    group_labels = table.groupby(["feature_hash", "Label"], observed=True).size().rename("rows").reset_index()
    sys_path = Path(__file__).resolve().parents[2] / "scripts" / "investigation"
    import sys
    if str(sys_path) not in sys.path:
        sys.path.insert(0, str(sys_path))
    from split_feasibility.analysis import build_group_stratified_split
    result = build_group_stratified_split(group_labels, fraction, seed)
    validation = np.isin(hashes, result.test_hashes)
    if not validation.any() or validation.all():
        raise RuntimeError("Internal validation is empty")
    if pd.DataFrame({"h": hashes, "v": validation}).groupby("h")["v"].nunique().max() != 1:
        raise RuntimeError("Internal validation crosses exact-feature groups")
    labels = train["Label"].astype(str)
    if set(labels[validation]) != set(labels) or set(labels[~validation]) != set(labels):
        raise RuntimeError("An original Label is missing from internal train or validation")
    return validation
