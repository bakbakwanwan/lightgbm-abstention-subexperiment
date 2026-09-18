from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .data import DAYS, map_protocol, sha256_file
from .layer2_common import read_json, require_valid_run_id


@dataclass(frozen=True)
class InputFeatureSchema:
    schema_version: str
    source_whitelist_path: str
    source_whitelist_sha256: str
    features: tuple[str, ...]


@dataclass(frozen=True)
class ThresholdSource:
    experiment_id: str
    method: str
    target_abstention_rate: float
    confidence_threshold: float


PROMPT_FORBIDDEN_FIELDS = {
    "day",
    "id",
    "Label",
    "binary_label",
    "is_error",
    "Attempted Category",
    "p_attack",
    "confidence",
    "predicted_label",
    "abstained",
}

SIDECAR_COLUMNS = (
    "input_index",
    "day",
    "id",
    "binary_label",
    "p_attack",
    "confidence",
    "predicted_label",
    "is_error",
)


def load_input_feature_schema(path: Path) -> InputFeatureSchema:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "source_whitelist",
        "feature_count",
        "features",
        "protocol_mapping",
        "numeric_serialization",
        "prompt_excluded_fields",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError(f"Input feature schema keys must be exactly {sorted(required)}")
    features = tuple(str(value) for value in payload["features"])
    if len(features) != int(payload["feature_count"]) or len(features) != 59:
        raise ValueError("Input feature schema must contain exactly 59 features")
    if len(set(features)) != len(features) or features.count("Protocol") != 1:
        raise ValueError("Input feature schema features must be unique and contain Protocol once")
    if set(features) & PROMPT_FORBIDDEN_FIELDS:
        raise ValueError("Input feature schema contains a prompt-forbidden field")
    if set(payload["prompt_excluded_fields"]) != PROMPT_FORBIDDEN_FIELDS:
        raise ValueError("Input feature schema prompt exclusions differ from the E9 contract")
    if payload["protocol_mapping"] != {"6": "TCP", "17": "UDP", "1": "ICMP", "0": "UNKNOWN"}:
        raise ValueError("Input feature schema Protocol mapping differs from Layer 1")
    source = payload["source_whitelist"]
    return InputFeatureSchema(
        schema_version=str(payload["schema_version"]),
        source_whitelist_path=str(source["path"]),
        source_whitelist_sha256=str(source["sha256"]),
        features=features,
    )


def validate_schema_snapshot(schema: InputFeatureSchema, repo_root: Path) -> None:
    source = (repo_root / schema.source_whitelist_path).resolve()
    if sha256_file(source) != schema.source_whitelist_sha256:
        raise RuntimeError("Layer 2 feature schema snapshot does not match its source whitelist hash")
    whitelist = json.loads(source.read_text(encoding="utf-8"))
    if tuple(whitelist["include"]) != schema.features:
        raise RuntimeError("Layer 2 feature schema snapshot differs from the source whitelist order")


def load_threshold_source(metrics_path: Path, method: str, target_rate: float) -> ThresholdSource:
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    try:
        analysis = metrics["analyses"][method]
    except KeyError as exc:
        raise ValueError(f"Method {method!r} is absent from {metrics_path}") from exc
    budget_rows = analysis.get("budgets", analysis.get("offline_budgets"))
    if not isinstance(budget_rows, list):
        raise ValueError(f"No offline budget rows found for method {method!r}")
    matches = [
        row
        for row in budget_rows
        if abs(float(row["target_abstention_rate"]) - float(target_rate)) <= 1e-12
    ]
    if len(matches) != 1 or matches[0].get("confidence_threshold") is None:
        raise ValueError(f"Exactly one non-null threshold is required for target rate {target_rate}")
    return ThresholdSource(
        experiment_id=str(metrics["exp_id"]),
        method=method,
        target_abstention_rate=float(target_rate),
        confidence_threshold=float(matches[0]["confidence_threshold"]),
    )


def _stable_row_hash(day: str, row_id: int) -> str:
    return sha256(f"{day}\0{row_id}".encode("utf-8")).hexdigest()


def select_abstained_predictions(
    predictions: pd.DataFrame,
    source: ThresholdSource,
    sample_size: int | None = None,
) -> tuple[pd.DataFrame, int]:
    required = {
        "method",
        "day",
        "id",
        "observation_group",
        "split",
        "binary_label",
        "p_attack",
        "confidence",
        "predicted_label",
        "is_error",
    }
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"Prediction artifact is missing columns: {sorted(missing)}")
    method_rows = predictions.loc[predictions["method"].astype(str).eq(source.method)]
    if method_rows.empty:
        raise ValueError(f"Prediction artifact has no rows for method {source.method!r}")
    target = method_rows.loc[
        method_rows["observation_group"].astype(str).eq("none")
        & method_rows["split"].astype(str).eq("test")
    ].copy()
    confidence = pd.to_numeric(target["confidence"], errors="raise").to_numpy(dtype=np.float64)
    if not np.isfinite(confidence).all() or ((confidence < 0.5) | (confidence > 1.0)).any():
        raise ValueError("Prediction artifact contains invalid confidence values")
    if not 0.5 <= source.confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold must be within [0.5, 1.0]")
    if target.duplicated(["day", "id"]).any():
        raise ValueError("Prediction artifact contains duplicate (day, id) target rows")
    selected = target.loc[target["confidence"].le(source.confidence_threshold)].copy()
    if selected.empty:
        raise ValueError("The selected abstention set is empty")
    selected["_day_order"] = selected["day"].map({day: index for index, day in enumerate(DAYS)})
    if selected["_day_order"].isna().any():
        raise ValueError("Prediction artifact contains an unknown day identifier")
    if sample_size is not None:
        if sample_size <= 0 or sample_size > len(selected):
            raise ValueError("sample_size must be positive and not exceed the abstention set")
        selected["_sample_hash"] = [
            _stable_row_hash(str(day), int(row_id))
            for day, row_id in zip(selected["day"], selected["id"], strict=True)
        ]
        selected = selected.sort_values(["_sample_hash", "_day_order", "id"], kind="stable").head(sample_size)
    else:
        selected = selected.sort_values(["_day_order", "id"], kind="stable")
    selected = selected.drop(columns=[column for column in ("_day_order", "_sample_hash") if column in selected])
    selected.insert(0, "input_index", np.arange(len(selected), dtype=np.int64))
    return selected.reset_index(drop=True), len(target)


def load_selected_features(
    data_dir: Path,
    selected: pd.DataFrame,
    schema: InputFeatureSchema,
    chunk_size: int = 100_000,
) -> pd.DataFrame:
    required = {"input_index", "day", "id"}
    if not required.issubset(selected.columns):
        raise ValueError(f"Selected rows must contain {sorted(required)}")
    usecols = ["id", *schema.features]
    parts: list[pd.DataFrame] = []
    for day in DAYS:
        day_selection = selected.loc[selected["day"].astype(str).eq(day), ["input_index", "id"]]
        if day_selection.empty:
            continue
        wanted = set(day_selection["id"].astype("int64"))
        for chunk in pd.read_csv(data_dir / f"{day}.csv", usecols=usecols, chunksize=chunk_size, low_memory=False):
            matched = chunk.loc[chunk["id"].isin(wanted)].copy()
            if matched.empty:
                continue
            matched.insert(0, "day", day)
            parts.append(matched.merge(day_selection, on="id", how="inner", validate="one_to_one"))
    if not parts:
        raise RuntimeError("No selected feature rows were found in the source dataset")
    frame = pd.concat(parts, ignore_index=True)
    if len(frame) != len(selected) or frame["input_index"].nunique() != len(selected):
        raise RuntimeError("Selected feature rows did not join exactly once to the source dataset")
    frame["Protocol"] = map_protocol(frame["Protocol"]).astype(str)
    numeric = [feature for feature in schema.features if feature != "Protocol"]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="raise").astype("float64")
    values = frame[numeric].to_numpy(dtype=np.float64)
    frame.loc[:, numeric] = np.where(np.isfinite(values), values, np.nan)
    return frame.sort_values("input_index", kind="stable").reset_index(drop=True)


def _json_scalar(value: Any) -> str | float | int | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        numeric = float(value)
        return numeric if np.isfinite(numeric) else None
    return str(value)


def serialized_input_record(row: pd.Series, schema: InputFeatureSchema) -> dict[str, Any]:
    flow_features = {feature: _json_scalar(row[feature]) for feature in schema.features}
    if set(flow_features) & PROMPT_FORBIDDEN_FIELDS or tuple(flow_features) != schema.features:
        raise RuntimeError("Serialized prompt feature keys differ from the input schema")
    return {
        "input_index": int(row["input_index"]),
        "payload": {"flow_features": flow_features},
    }


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
            handle.write("\n")
            count += 1
    return count


def _sidecar_record(row: pd.Series) -> dict[str, Any]:
    return {column: _json_scalar(row[column]) for column in SIDECAR_COLUMNS}


def _git_state(repo_root: Path) -> tuple[str, bool]:
    safe = f"safe.directory={repo_root.as_posix()}"
    commit = subprocess.check_output(
        ["git", "-c", safe, "rev-parse", "HEAD"], cwd=repo_root, text=True
    ).strip()
    status = subprocess.check_output(
        ["git", "-c", safe, "status", "--porcelain"], cwd=repo_root, text=True
    )
    return commit, bool(status.strip())


def export_abstained_flow_bundle(
    *,
    repo_root: Path,
    predictions_path: Path,
    metrics_path: Path,
    data_dir: Path,
    feature_schema_path: Path,
    prompt_path: Path,
    run_id: str,
    method: str,
    target_rate: float,
    output_dir: Path,
    sample_size: int | None = None,
    chunk_size: int = 100_000,
) -> dict[str, Any]:
    require_valid_run_id(run_id)
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {output_dir}")
    schema = load_input_feature_schema(feature_schema_path)
    validate_schema_snapshot(schema, repo_root)
    source = load_threshold_source(metrics_path, method, target_rate)
    predictions = pd.read_parquet(predictions_path)
    selected, n_test = select_abstained_predictions(predictions, source, sample_size)

    expected_dataset_hashes = json.loads(metrics_path.read_text(encoding="utf-8"))["dataset"]
    actual_dataset_hashes = {f"{day}.csv": sha256_file(data_dir / f"{day}.csv") for day in DAYS}
    if actual_dataset_hashes != expected_dataset_hashes:
        raise RuntimeError("Source dataset hashes differ from the prediction artifact metrics")

    features = load_selected_features(data_dir, selected, schema, chunk_size)
    output_dir.mkdir(parents=True)
    transfer_dir = output_dir / "transfer"
    local_dir = output_dir / "local"
    transfer_dir.mkdir()
    local_dir.mkdir()

    transferred_schema_path = transfer_dir / feature_schema_path.name
    transferred_prompt_path = transfer_dir / prompt_path.name
    shutil.copyfile(feature_schema_path, transferred_schema_path)
    shutil.copyfile(prompt_path, transferred_prompt_path)
    prompt_payload = read_json(transferred_prompt_path)
    if prompt_payload.get("prompt_version") != "e9-v1":
        raise ValueError("Prompt asset must use prompt_version e9-v1")

    inputs_path = transfer_dir / "llm_inputs.jsonl"
    input_count = _write_jsonl(
        inputs_path,
        (serialized_input_record(row, schema) for _, row in features.iterrows()),
    )
    sidecar = selected.loc[:, [column for column in SIDECAR_COLUMNS if column != "input_index"]].copy()
    sidecar.insert(0, "input_index", np.arange(len(sidecar), dtype=np.int64))
    sidecar_path = local_dir / "evaluation_sidecar.jsonl"
    sidecar_count = _write_jsonl(
        sidecar_path,
        (_sidecar_record(row) for _, row in sidecar.iterrows()),
    )
    if input_count != sidecar_count or input_count != len(selected):
        raise RuntimeError("Transfer inputs and local evaluation sidecar row counts differ")

    selection_ids = "\n".join(
        f"{row.day}\t{int(row.id)}" for row in selected[["day", "id"]].itertuples(index=False)
    ).encode("utf-8")
    git_commit, working_tree_dirty = _git_state(repo_root)
    manifest = {
        "bundle_type": "layer2_abstained_flow_export",
        "schema_version": schema.schema_version,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "working_tree_dirty_at_creation": working_tree_dirty,
        "source": {
            "experiment_id": source.experiment_id,
            "method": source.method,
            "target_abstention_rate": source.target_abstention_rate,
            "confidence_threshold": source.confidence_threshold,
            "n_test": n_test,
            "n_abstained_before_sampling": int(
                predictions.loc[
                    predictions["method"].astype(str).eq(source.method)
                    & predictions["observation_group"].astype(str).eq("none")
                    & predictions["split"].astype(str).eq("test")
                    & predictions["confidence"].le(source.confidence_threshold)
                ].shape[0]
            ),
            "sample_size": sample_size,
            "selection_order": "sha256(day\\0id)" if sample_size is not None else "canonical_day_then_id",
        },
        "counts": {"exported_rows": input_count, "feature_count": len(schema.features)},
        "artifacts": {
            "llm_inputs": {
                "path": "transfer/llm_inputs.jsonl",
                "sha256": sha256_file(inputs_path),
                "rows": input_count,
            },
            "feature_schema": {
                "path": f"transfer/{transferred_schema_path.name}",
                "version": schema.schema_version,
                "sha256": sha256_file(transferred_schema_path),
            },
            "prompt": {
                "path": f"transfer/{transferred_prompt_path.name}",
                "version": prompt_payload["prompt_version"],
                "sha256": sha256_file(transferred_prompt_path),
            },
        },
        "integrity": {
            "predictions_sha256": sha256_file(predictions_path),
            "metrics_sha256": sha256_file(metrics_path),
            "feature_schema_sha256": sha256_file(transferred_schema_path),
            "prompt_sha256": sha256_file(transferred_prompt_path),
            "source_whitelist_sha256": schema.source_whitelist_sha256,
            "dataset_file_sha256": actual_dataset_hashes,
            "selection_day_id_sha256": sha256(selection_ids).hexdigest(),
            "llm_inputs_sha256": sha256_file(inputs_path),
            "evaluation_sidecar_sha256": sha256_file(sidecar_path),
        },
        "transfer_contract": {
            "copy_to_llm_environment": [
                "transfer/llm_inputs.jsonl",
                f"transfer/{transferred_schema_path.name}",
                f"transfer/{transferred_prompt_path.name}",
                "manifest.json",
            ],
            "keep_local": ["local/evaluation_sidecar.jsonl"],
            "prompt_payload_path": "payload.flow_features",
            "response_join_key": "input_index",
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest
