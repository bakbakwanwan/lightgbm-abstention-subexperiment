#!/usr/bin/env python
"""Build and validate the two D-004 split assignments.

Outputs one gzip CSV per source day and split method. Raw CSV files are read only.
Observation groups retain an empty split value and never enter train/test.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "investigation"))

from class_overlap.run_measurement import (  # noqa: E402
    DAYS,
    EXPECTED_ROWS,
    EXPECTED_TARGET_ROWS,
    iter_chunks,
    load_whitelist,
    validate_integrity,
)
from split_feasibility.analysis import (  # noqa: E402
    build_group_stratified_split,
    deterministic_stratified_row_split,
)
from split_feasibility.run_measurement import (  # noqa: E402
    build_group_tables,
    load_target_hashes_and_labels,
    split_per_label,
)

SEED = 42
TEST_FRACTION = 0.25
METHODS = ("group_seed42", "row_random_seed42")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=REPO_ROOT / "data" / "CICIDS2017_CNS2022_reprocessed",
    )
    parser.add_argument(
        "--source-zip",
        type=Path,
        default=REPO_ROOT / "data" / "CICIDS2017_improved.zip",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "results" / "d004_splits",
    )
    parser.add_argument("--chunk-size", type=int, default=100_000)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def git_state() -> tuple[str | None, bool]:
    try:
        commit = subprocess.check_output(
            ["git", "-c", f"safe.directory={REPO_ROOT.as_posix()}", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
        status = subprocess.check_output(
            ["git", "-c", f"safe.directory={REPO_ROOT.as_posix()}", "status", "--porcelain"],
            cwd=REPO_ROOT,
            text=True,
        )
        return commit, bool(status.strip())
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None, True


def observation_group(labels: pd.Series) -> pd.Series:
    values = np.full(len(labels), "none", dtype=object)
    attempted = labels.str.endswith("- Attempted", na=False).to_numpy(dtype=bool)
    invalid_class = labels.eq("DoS Hulk").to_numpy(dtype=bool)
    values[attempted] = "attempted"
    values[invalid_class] = "invalid_class"
    if (attempted & invalid_class).any():
        raise AssertionError("Observation groups overlap")
    return pd.Series(values, index=labels.index, dtype="string")


def write_assignments(
    input_dir: Path,
    output_dir: Path,
    feature_columns: list[str],
    group_test: np.ndarray,
    row_test: np.ndarray,
    chunk_size: int,
) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"Refusing to overwrite non-empty split output directory: {output_dir}"
        )
    for method in METHODS:
        (output_dir / method).mkdir(parents=True, exist_ok=True)

    handles = {}
    header_written = {}
    target_cursor = 0
    usecols = list(dict.fromkeys(feature_columns + ["Label", "id"]))
    with ExitStack() as stack:
        for method in METHODS:
            for day in DAYS:
                raw_handle = stack.enter_context((output_dir / method / f"{day}.csv.gz").open("wb"))
                gzip_handle = stack.enter_context(
                    gzip.GzipFile(fileobj=raw_handle, mode="wb", mtime=0)
                )
                text_handle = stack.enter_context(
                    __import__("io").TextIOWrapper(gzip_handle, encoding="utf-8", newline="")
                )
                handles[(method, day)] = text_handle
                header_written[(method, day)] = False

        for day, chunk_index, chunk in iter_chunks(input_dir, usecols, chunk_size):
            labels = chunk["Label"].astype("string")
            groups = observation_group(labels)
            target = groups.eq("none").to_numpy(dtype=bool)
            n_target = int(target.sum())
            group_slice = group_test[target_cursor : target_cursor + n_target]
            row_slice = row_test[target_cursor : target_cursor + n_target]
            if len(group_slice) != n_target or len(row_slice) != n_target:
                raise AssertionError("Target split cursor exceeded assignment arrays")
            target_cursor += n_target

            for method, test_slice in (
                ("group_seed42", group_slice),
                ("row_random_seed42", row_slice),
            ):
                split = np.full(len(chunk), "", dtype=object)
                target_positions = np.flatnonzero(target)
                split[target_positions] = np.where(test_slice, "test", "train")
                assignment = pd.DataFrame(
                    {
                        "id": chunk["id"].to_numpy(dtype=np.int64),
                        "Label": labels.astype(str).to_numpy(),
                        "observation_group": groups.astype(str).to_numpy(),
                        "split": split,
                    }
                )
                assignment.to_csv(
                    handles[(method, day)],
                    index=False,
                    header=not header_written[(method, day)],
                )
                header_written[(method, day)] = True
            print(f"  wrote {day} chunk {chunk_index + 1}")
    if target_cursor != EXPECTED_TARGET_ROWS:
        raise AssertionError(
            f"Target split cursor={target_cursor}, expected={EXPECTED_TARGET_ROWS}"
        )


def validate_saved_assignments(
    output_dir: Path,
    hashes: np.ndarray,
    labels: np.ndarray,
) -> tuple[dict, pd.DataFrame]:
    validation: dict = {}
    all_per_label = []
    for method in METHODS:
        target_splits: list[np.ndarray] = []
        target_labels: list[np.ndarray] = []
        observation_counts = {"attempted": 0, "invalid_class": 0, "none": 0}
        total_rows = 0
        for day in DAYS:
            path = output_dir / method / f"{day}.csv.gz"
            day_rows = 0
            day_ids: list[np.ndarray] = []
            for chunk in pd.read_csv(
                path,
                dtype={"id": "int64", "Label": "string", "observation_group": "string", "split": "string"},
                keep_default_na=False,
                chunksize=100_000,
            ):
                if list(chunk.columns) != ["id", "Label", "observation_group", "split"]:
                    raise AssertionError(f"Unexpected split columns in {path}")
                if not set(chunk["observation_group"].unique()).issubset(
                    {"none", "attempted", "invalid_class"}
                ):
                    raise AssertionError(f"Unexpected observation_group in {path}")
                target = chunk["observation_group"].eq("none")
                if not chunk.loc[target, "split"].isin(["train", "test"]).all():
                    raise AssertionError(f"Target row without train/test in {path}")
                if chunk.loc[~target, "split"].ne("").any():
                    raise AssertionError(f"Observation row assigned to train/test in {path}")
                for key, count in chunk["observation_group"].value_counts().items():
                    observation_counts[str(key)] += int(count)
                target_splits.append(chunk.loc[target, "split"].astype(str).to_numpy())
                target_labels.append(chunk.loc[target, "Label"].astype(str).to_numpy())
                day_ids.append(chunk["id"].to_numpy(dtype=np.int64))
                day_rows += len(chunk)
            ids = np.concatenate(day_ids)
            if day_rows != EXPECTED_ROWS[f"{day}.csv"]:
                raise AssertionError(f"Saved {day} rows={day_rows}")
            if len(np.unique(ids)) != len(ids):
                raise AssertionError(f"Duplicate id values in saved {day} assignment")
            total_rows += day_rows

        saved_splits = np.concatenate(target_splits)
        saved_labels = np.concatenate(target_labels)
        if not np.array_equal(saved_labels, labels):
            raise AssertionError(f"Saved Label order differs for {method}")
        test_mask = saved_splits == "test"
        group_crossings = int(
            (
                pd.DataFrame({"feature_hash": hashes, "split": saved_splits})
                .groupby("feature_hash", observed=True)["split"]
                .nunique()
                > 1
            ).sum()
        )
        per_label = split_per_label(labels, test_mask, method)
        all_per_label.append(per_label)
        validation[method] = {
            "total_rows": total_rows,
            "observation_group_counts": observation_counts,
            "target_rows": int(len(saved_splits)),
            "train_rows": int((saved_splits == "train").sum()),
            "test_rows": int(test_mask.sum()),
            "cross_split_feature_groups": group_crossings,
            "labels_missing_from_train": per_label.loc[per_label["train_rows"] == 0, "Label"].tolist(),
            "labels_missing_from_test": per_label.loc[per_label["test_rows"] == 0, "Label"].tolist(),
        }
    return validation, pd.concat(all_per_label, ignore_index=True)


def main() -> int:
    args = parse_args()
    include, exclude = load_whitelist(REPO_ROOT / "configs" / "features_whitelist.json")
    print("[1/5] 데이터 무결성 검증")
    dataset_manifest, _ = validate_integrity(
        args.input_dir, args.source_zip, include, exclude
    )

    print("[2/5] D-004 주·민감도 split 계산")
    hashes, labels = load_target_hashes_and_labels(
        args.input_dir, include, args.chunk_size
    )
    group_label, _ = build_group_tables(hashes, labels)
    group_result = build_group_stratified_split(group_label, TEST_FRACTION, SEED)
    group_test = np.isin(hashes, group_result.test_hashes)
    row_test = deterministic_stratified_row_split(labels, TEST_FRACTION, SEED)

    print("[3/5] 요일별 gzip CSV split 산출")
    write_assignments(
        args.input_dir,
        args.output_dir,
        include,
        group_test,
        row_test,
        args.chunk_size,
    )

    print("[4/5] 저장 파일 독립 재검증")
    validation, per_label = validate_saved_assignments(
        args.output_dir, hashes, labels
    )
    if validation["group_seed42"]["cross_split_feature_groups"] != 0:
        raise AssertionError("Primary group split has crossing feature groups")
    if validation["group_seed42"]["train_rows"] != 1_447_147:
        raise AssertionError("Primary train row count mismatch")
    if validation["group_seed42"]["test_rows"] != 482_382:
        raise AssertionError("Primary test row count mismatch")
    for method in METHODS:
        if validation[method]["labels_missing_from_train"] or validation[method]["labels_missing_from_test"]:
            raise AssertionError(f"Label missing from split: {method}")
        if validation[method]["observation_group_counts"] != {
            "attempted": 11_979,
            "invalid_class": 158_468,
            "none": 1_929_529,
        }:
            raise AssertionError(f"Observation group count mismatch: {method}")

    print("[5/5] manifest와 라벨별 요약 기록")
    per_label.to_csv(args.output_dir / "split_summary.csv", index=False)
    commit, dirty = git_state()
    output_hashes = {
        str(path.relative_to(args.output_dir)).replace("\\", "/"): sha256_file(path)
        for path in sorted(args.output_dir.glob("*/*.csv.gz"))
    }
    manifest = {
        "decision_id": "D-004",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "working_tree_dirty_at_creation": dirty,
        "seed": SEED,
        "test_fraction": TEST_FRACTION,
        "feature_source": "configs/features_whitelist.json#include",
        "feature_count": 59,
        "protocol_mapping": {"6": "TCP", "17": "UDP", "1": "ICMP", "0": "UNKNOWN"},
        "dataset_file_sha256": dataset_manifest["file_sha256"],
        "source_zip_sha256": dataset_manifest["source_zip_sha256"],
        "features_whitelist_sha256": sha256_file(REPO_ROOT / "configs" / "features_whitelist.json"),
        "methods": {
            "group_seed42": "primary exact-59-feature-group Label-stratified approximation",
            "row_random_seed42": "optimistic Label-stratified row-random sensitivity analysis",
        },
        "validation": validation,
        "output_file_sha256": output_hashes,
    }
    (args.output_dir / "split_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"완료: {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

