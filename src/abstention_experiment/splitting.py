from __future__ import annotations

import gzip
import json
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .configuration import ExperimentConfig
from .data import DAYS, EXPECTED, sha256_file


INVESTIGATION_DIR = Path(__file__).resolve().parents[2] / "scripts" / "investigation"
if str(INVESTIGATION_DIR) not in sys.path:
    sys.path.insert(0, str(INVESTIGATION_DIR))

from split_feasibility.analysis import build_group_stratified_split  # noqa: E402
from split_feasibility.run_measurement import (  # noqa: E402
    build_group_tables,
    load_target_hashes_and_labels,
    split_per_label,
)


@dataclass
class SplitPlan:
    hashes: np.ndarray
    labels: np.ndarray
    group_label: pd.DataFrame
    test_masks: dict[str, np.ndarray]
    validation: dict[str, dict[str, Any]]
    conflict_hashes: np.ndarray
    conflict_feature_group_ids: dict[int, str]


def observation_group(labels: pd.Series) -> pd.Series:
    values = np.full(len(labels), "none", dtype=object)
    attempted = labels.str.endswith("- Attempted", na=False).to_numpy(dtype=bool)
    invalid = labels.eq("DoS Hulk").to_numpy(dtype=bool)
    if (attempted & invalid).any():
        raise RuntimeError("Observation groups overlap")
    values[attempted] = "attempted"
    values[invalid] = "invalid_class"
    return pd.Series(values, index=labels.index, dtype="string")


def build_split_plan(config: ExperimentConfig, features: list[str]) -> SplitPlan:
    analysis = config.raw["analysis"]
    hashes, labels = load_target_hashes_and_labels(
        config.path("inputs", "data_dir"),
        features,
        int(config.raw["inputs"]["chunk_size"]),
    )
    group_label, group_summary = build_group_tables(hashes, labels)
    conflict_hashes = group_summary.loc[
        group_summary["n_binary_labels"].gt(1), "feature_hash"
    ].to_numpy(dtype=np.uint64)
    if len(conflict_hashes) != 15:
        raise RuntimeError(f"Expected 15 binary-label conflict groups, found {len(conflict_hashes)}")

    first_codes, unique_hashes = pd.factorize(hashes, sort=False)
    conflict_set = set(int(value) for value in conflict_hashes)
    conflict_ids = {
        int(value): f"fg_{index:010d}"
        for index, value in enumerate(unique_hashes)
        if int(value) in conflict_set
    }
    del first_codes

    masks: dict[str, np.ndarray] = {}
    validations: dict[str, dict[str, Any]] = {}
    for seed in [int(value) for value in analysis["split_seeds"]]:
        method = f"{analysis['split_method_prefix']}{seed}"
        result = build_group_stratified_split(
            group_label,
            float(analysis["test_fraction"]),
            seed,
        )
        mask = np.isin(hashes, result.test_hashes)
        per_label = split_per_label(labels, mask, method)
        split_codes = pd.Series(mask, index=pd.Index(hashes, name="feature_hash"))
        crossings = int(split_codes.groupby(level=0, observed=True).nunique().gt(1).sum())
        validation = {
            "seed": seed,
            "target_rows": int(len(mask)),
            "train_rows": int((~mask).sum()),
            "test_rows": int(mask.sum()),
            "cross_split_feature_groups": crossings,
            "labels_missing_from_train": per_label.loc[
                per_label["train_rows"].eq(0), "Label"
            ].tolist(),
            "labels_missing_from_test": per_label.loc[
                per_label["test_rows"].eq(0), "Label"
            ].tolist(),
        }
        if validation["target_rows"] != EXPECTED["target"]:
            raise RuntimeError(f"Target row count mismatch for {method}: {validation}")
        if crossings or validation["labels_missing_from_train"] or validation["labels_missing_from_test"]:
            raise RuntimeError(f"Invalid group split for {method}: {validation}")
        masks[method] = mask
        validations[method] = validation
    return SplitPlan(
        hashes=hashes,
        labels=labels,
        group_label=group_label,
        test_masks=masks,
        validation=validations,
        conflict_hashes=conflict_hashes,
        conflict_feature_group_ids=conflict_ids,
    )


def write_split_assignments(
    config: ExperimentConfig,
    plan: SplitPlan,
    split_root: Path,
) -> dict[str, Any]:
    if split_root.exists() and any(split_root.iterdir()):
        raise FileExistsError(f"Refusing to overwrite split output: {split_root}")
    methods = list(plan.test_masks)
    for method in methods:
        (split_root / method).mkdir(parents=True, exist_ok=True)

    handles: dict[tuple[str, str], Any] = {}
    headers: dict[tuple[str, str], bool] = {}
    target_cursor = 0
    chunk_size = int(config.raw["inputs"]["chunk_size"])
    with ExitStack() as stack:
        for method in methods:
            for day in DAYS:
                raw_handle = stack.enter_context((split_root / method / f"{day}.csv.gz").open("wb"))
                gzip_handle = stack.enter_context(gzip.GzipFile(fileobj=raw_handle, mode="wb", mtime=0))
                text_handle = stack.enter_context(
                    __import__("io").TextIOWrapper(gzip_handle, encoding="utf-8", newline="")
                )
                handles[(method, day)] = text_handle
                headers[(method, day)] = False

        for day in DAYS:
            reader = pd.read_csv(
                config.path("inputs", "data_dir") / f"{day}.csv",
                usecols=["id", "Label"],
                chunksize=chunk_size,
                low_memory=False,
            )
            for chunk in reader:
                labels = chunk["Label"].astype("string")
                groups = observation_group(labels)
                target = groups.eq("none").to_numpy(dtype=bool)
                count = int(target.sum())
                target_positions = np.flatnonzero(target)
                for method, mask in plan.test_masks.items():
                    selection = mask[target_cursor : target_cursor + count]
                    if len(selection) != count:
                        raise RuntimeError("Split assignment cursor exceeded target rows")
                    split = np.full(len(chunk), "", dtype=object)
                    split[target_positions] = np.where(selection, "test", "train")
                    assignment = pd.DataFrame(
                        {
                            "day": day,
                            "id": chunk["id"].to_numpy(dtype=np.int64),
                            "Label": labels.astype(str).to_numpy(),
                            "observation_group": groups.astype(str).to_numpy(),
                            "split": split,
                        }
                    )
                    assignment.to_csv(
                        handles[(method, day)],
                        index=False,
                        header=not headers[(method, day)],
                    )
                    headers[(method, day)] = True
                target_cursor += count
    if target_cursor != EXPECTED["target"]:
        raise RuntimeError(f"Split assignment cursor={target_cursor}, expected={EXPECTED['target']}")

    file_hashes = {
        str(path.relative_to(split_root)).replace("\\", "/"): sha256_file(path)
        for path in sorted(split_root.glob("*/*.csv.gz"))
    }
    manifest = {
        "test_fraction": float(config.raw["analysis"]["test_fraction"]),
        "feature_source": "configs/features_whitelist.json#include",
        "feature_count": int(config.raw["inputs"]["expected_population"]["feature_count"]),
        "methods": plan.validation,
        "output_file_sha256": file_hashes,
    }
    (split_root / "split_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def validate_saved_split_assignments(
    config: ExperimentConfig,
    plan: SplitPlan,
    split_root: Path,
) -> dict[str, dict[str, Any]]:
    validations: dict[str, dict[str, Any]] = {}
    for method, expected_test in plan.test_masks.items():
        saved_splits: list[np.ndarray] = []
        saved_labels: list[np.ndarray] = []
        observation_counts = {"none": 0, "attempted": 0, "invalid_class": 0}
        unique_keys: set[tuple[str, int]] = set()
        for day in DAYS:
            frame = pd.read_csv(
                split_root / method / f"{day}.csv.gz",
                dtype={
                    "day": "string",
                    "id": "int64",
                    "Label": "string",
                    "observation_group": "string",
                    "split": "string",
                },
                keep_default_na=False,
            )
            if not frame["day"].eq(day).all():
                raise RuntimeError(f"Saved day value mismatch: {method}/{day}")
            keys = set(zip(frame["day"].astype(str), frame["id"].astype(int), strict=True))
            if len(keys) != len(frame) or unique_keys.intersection(keys):
                raise RuntimeError(f"Duplicate saved split key: {method}/{day}")
            unique_keys.update(keys)
            for group, count in frame["observation_group"].value_counts().items():
                observation_counts[str(group)] += int(count)
            target = frame["observation_group"].eq("none")
            if not frame.loc[target, "split"].isin(["train", "test"]).all():
                raise RuntimeError(f"Unassigned target row: {method}/{day}")
            if frame.loc[~target, "split"].ne("").any():
                raise RuntimeError(f"Observation row assigned to split: {method}/{day}")
            saved_splits.append(frame.loc[target, "split"].eq("test").to_numpy(dtype=bool))
            saved_labels.append(frame.loc[target, "Label"].astype(str).to_numpy())
        actual_test = np.concatenate(saved_splits)
        actual_labels = np.concatenate(saved_labels)
        if not np.array_equal(actual_test, expected_test):
            raise RuntimeError(f"Saved split differs from planned split: {method}")
        if not np.array_equal(actual_labels, plan.labels):
            raise RuntimeError(f"Saved Label order differs from source: {method}")
        expected_groups = config.raw["inputs"]["expected_population"]["observation_group_rows"]
        expected_observations = {
            "none": int(config.raw["inputs"]["expected_population"]["target_rows"]),
            **{key: int(value) for key, value in expected_groups.items()},
        }
        if observation_counts != expected_observations:
            raise RuntimeError(f"Saved observation counts differ: {method}/{observation_counts}")
        validations[method] = {
            "passed": True,
            "unique_keys": len(unique_keys),
            "observation_group_counts": observation_counts,
            "train_rows": int((~actual_test).sum()),
            "test_rows": int(actual_test.sum()),
            "cross_split_feature_groups": plan.validation[method]["cross_split_feature_groups"],
        }
    return validations


def read_test_index(split_root: Path, method: str, hashes: np.ndarray) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    cursor = 0
    for day in DAYS:
        frame = pd.read_csv(
            split_root / method / f"{day}.csv.gz",
            dtype={"id": "int64", "observation_group": "string", "split": "string"},
            keep_default_na=False,
        )
        if "day" not in frame.columns:
            frame.insert(0, "day", day)
        target = frame["observation_group"].eq("none").to_numpy(dtype=bool)
        count = int(target.sum())
        target_hashes = hashes[cursor : cursor + count]
        selected = target & frame["split"].eq("test").to_numpy(dtype=bool)
        target_positions = np.flatnonzero(target)
        selected_target = frame.loc[selected, ["day", "id"]].copy()
        selected_target["feature_hash"] = target_hashes[
            frame.loc[target_positions, "split"].eq("test").to_numpy(dtype=bool)
        ]
        parts.append(selected_target)
        cursor += count
    if cursor != len(hashes):
        raise RuntimeError("Test-index hash cursor mismatch")
    return pd.concat(parts, ignore_index=True)
