#!/usr/bin/env python
"""Measure whether a 75:25 exact-feature-group split is feasible."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "investigation"))

from class_overlap.analysis import feature_hash, normalize_features  # noqa: E402
from class_overlap.run_measurement import (  # noqa: E402
    EXPECTED_TARGET_ROWS,
    load_whitelist,
    iter_chunks,
    validate_integrity,
)
from split_feasibility.analysis import (  # noqa: E402
    build_group_stratified_split,
    deterministic_stratified_row_split,
    row_random_leakage,
)

TEST_FRACTION = 0.25
SEED = 42


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
        default=REPO_ROOT / "reports" / "split_feasibility",
    )
    parser.add_argument("--chunk-size", type=int, default=100_000)
    return parser.parse_args()


def write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def load_target_hashes_and_labels(
    input_dir: Path,
    feature_columns: list[str],
    chunk_size: int,
) -> tuple[np.ndarray, np.ndarray]:
    hash_parts: list[np.ndarray] = []
    label_parts: list[np.ndarray] = []
    usecols = list(dict.fromkeys(feature_columns + ["Label", "id"]))
    total = 0
    for day, chunk_index, chunk in iter_chunks(input_dir, usecols, chunk_size):
        labels = chunk["Label"]
        target = ~(
            labels.str.endswith("- Attempted", na=False) | labels.eq("DoS Hulk")
        )
        target_chunk = chunk.loc[target]
        features = normalize_features(target_chunk, feature_columns)
        hash_parts.append(feature_hash(features))
        label_parts.append(target_chunk["Label"].astype(str).to_numpy())
        total += len(target_chunk)
        print(f"  {day} chunk {chunk_index + 1}, target rows={total:,}")
    if total != EXPECTED_TARGET_ROWS:
        raise RuntimeError(f"Target rows={total}, expected={EXPECTED_TARGET_ROWS}")
    return np.concatenate(hash_parts), np.concatenate(label_parts)


def build_group_tables(hashes: np.ndarray, labels: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = pd.DataFrame({"feature_hash": hashes, "Label": labels})
    group_label = (
        rows.groupby(["feature_hash", "Label"], sort=False, observed=True)
        .size()
        .rename("rows")
        .reset_index()
    )
    group_summary = (
        group_label.groupby("feature_hash", observed=True)
        .agg(group_size=("rows", "sum"), n_labels=("Label", "size"))
        .reset_index()
    )
    binary_counts = (
        group_label.assign(binary_label=group_label["Label"].ne("BENIGN").astype(np.int8))
        .groupby("feature_hash", observed=True)["binary_label"]
        .nunique()
        .rename("n_binary_labels")
    )
    group_summary = group_summary.merge(
        binary_counts, on="feature_hash", how="left", validate="one_to_one"
    )
    return group_label, group_summary


def label_group_statistics(
    group_label: pd.DataFrame,
    group_summary: pd.DataFrame,
) -> pd.DataFrame:
    enriched = group_label.merge(group_summary, on="feature_hash", how="left", validate="many_to_one")
    records = []
    for label, frame in enriched.groupby("Label", sort=True, observed=True):
        label_rows = int(frame["rows"].sum())
        largest = int(frame["rows"].max())
        records.append(
            {
                "Label": label,
                "rows": label_rows,
                "unique_feature_groups": int(frame["feature_hash"].nunique()),
                "duplicate_feature_groups": int(frame.loc[frame["group_size"] >= 2, "feature_hash"].nunique()),
                "conflict_feature_groups": int(frame.loc[frame["n_binary_labels"] > 1, "feature_hash"].nunique()),
                "largest_group_label_rows": largest,
                "largest_group_label_row_ratio": largest / label_rows,
                "group_split_possible_both_sides": bool(frame["feature_hash"].nunique() >= 2),
            }
        )
    return pd.DataFrame(records)


def split_per_label(
    labels: np.ndarray,
    test_mask: np.ndarray,
    split_name: str,
) -> pd.DataFrame:
    frame = pd.DataFrame({"Label": labels, "is_test": test_mask})
    counts = frame.groupby(["Label", "is_test"], observed=True).size().unstack(fill_value=0)
    records = []
    for label in counts.index:
        train_rows = int(counts.loc[label].get(False, 0))
        test_rows = int(counts.loc[label].get(True, 0))
        total = train_rows + test_rows
        records.append(
            {
                "split_method": split_name,
                "Label": label,
                "total_rows": total,
                "train_rows": train_rows,
                "test_rows": test_rows,
                "test_ratio": test_rows / total,
                "absolute_deviation_from_0_25": abs(test_rows / total - TEST_FRACTION),
            }
        )
    return pd.DataFrame(records)


def conflict_assignment(
    group_label: pd.DataFrame,
    group_summary: pd.DataFrame,
    test_hashes: np.ndarray,
) -> pd.DataFrame:
    conflict_hashes = group_summary.loc[group_summary["n_binary_labels"] > 1, "feature_hash"]
    frame = group_label.loc[group_label["feature_hash"].isin(conflict_hashes)].copy()
    frame["split"] = np.where(frame["feature_hash"].isin(test_hashes), "test", "train")
    frame["group_id"] = frame["feature_hash"].map(lambda value: f"g_{int(value):016x}_0")
    return frame[["group_id", "split", "Label", "rows"]].sort_values(
        ["split", "group_id", "Label"]
    )


def main() -> int:
    args = parse_args()
    include, exclude = load_whitelist(REPO_ROOT / "configs" / "features_whitelist.json")

    print("[1/6] 데이터 무결성 재검증")
    manifest, _ = validate_integrity(args.input_dir, args.source_zip, include, exclude)
    overlap_summary = json.loads(
        (REPO_ROOT / "reports" / "class_overlap" / "summary.json").read_text(encoding="utf-8")
    )
    if overlap_summary["verified_hash_collision_subgroups"] != 0:
        raise RuntimeError("Feature hash cannot be used as group id: verified collisions exist")

    print("[2/6] 관찰군 제외 대상의 59-feature 그룹 생성")
    hashes, labels = load_target_hashes_and_labels(args.input_dir, include, args.chunk_size)
    group_label, group_summary = build_group_tables(hashes, labels)
    if int(group_summary["group_size"].sum()) != EXPECTED_TARGET_ROWS:
        raise AssertionError("Group rows do not reconcile to target population")

    print("[3/6] 라벨별 그룹 구조 및 희소 클래스 가능성 측정")
    label_stats = label_group_statistics(group_label, group_summary)

    print("[4/6] 완전일치 그룹 기반 75:25 근사 계층 분할")
    group_result = build_group_stratified_split(group_label, TEST_FRACTION, SEED)
    group_test = np.isin(hashes, group_result.test_hashes)
    group_per_label = split_per_label(labels, group_test, "exact_feature_group")
    crossing = pd.DataFrame({"hash": hashes, "test": group_test}).groupby("hash")["test"].nunique()
    if int((crossing > 1).sum()) != 0:
        raise AssertionError("Exact feature groups crossed train/test")

    print("[5/6] 행 단위 랜덤 분할의 실제 동일-feature 누수 측정")
    row_test = deterministic_stratified_row_split(labels, TEST_FRACTION, SEED)
    row_per_label = split_per_label(labels, row_test, "row_random_optimistic")
    leakage = row_random_leakage(hashes, labels, row_test)

    print("[6/6] 산출물 작성")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    label_stats.to_csv(args.output_dir / "label_group_statistics.csv", index=False)
    per_label = pd.concat([group_per_label, row_per_label], ignore_index=True)
    per_label.to_csv(args.output_dir / "split_per_label.csv", index=False)
    conflict = conflict_assignment(group_label, group_summary, group_result.test_hashes)
    conflict.to_csv(args.output_dir / "conflict_group_assignment.csv", index=False)

    group_test_rows = int(group_test.sum())
    group_train_rows = int((~group_test).sum())
    group_summary_payload = {
        "seed": SEED,
        "test_fraction_target": TEST_FRACTION,
        "train_rows": group_train_rows,
        "test_rows": group_test_rows,
        "test_ratio": group_test_rows / len(group_test),
        "cross_split_feature_groups": 0,
        "max_label_test_ratio_deviation": float(group_per_label["absolute_deviation_from_0_25"].max()),
        "labels_missing_from_train": group_per_label.loc[group_per_label["train_rows"] == 0, "Label"].tolist(),
        "labels_missing_from_test": group_per_label.loc[group_per_label["test_rows"] == 0, "Label"].tolist(),
        "conflict_groups_train": int(conflict.loc[conflict["split"] == "train", "group_id"].nunique()),
        "conflict_groups_test": int(conflict.loc[conflict["split"] == "test", "group_id"].nunique()),
        "conflict_rows_train": int(conflict.loc[conflict["split"] == "train", "rows"].sum()),
        "conflict_rows_test": int(conflict.loc[conflict["split"] == "test", "rows"].sum()),
        "conflict_subset_selection": group_result.conflict_selection,
    }
    summary = {
        "dataset_file_sha256": manifest["file_sha256"],
        "population_rows": len(hashes),
        "feature_groups": int(len(group_summary)),
        "singleton_groups": int((group_summary["group_size"] == 1).sum()),
        "duplicate_groups": int((group_summary["group_size"] >= 2).sum()),
        "multi_original_label_groups": int((group_summary["n_labels"] > 1).sum()),
        "conflict_groups": int((group_summary["n_binary_labels"] > 1).sum()),
        "group_split": group_summary_payload,
        "row_random_optimistic": leakage,
    }
    write_json(summary, args.output_dir / "summary.json")

    rare = group_per_label.loc[group_per_label["total_rows"] < 100]
    rare_lines = "\n".join(
        f"| {row.Label} | {int(row.total_rows):,} | {int(row.train_rows):,} | {int(row.test_rows):,} | {row.test_ratio:.4%} |"
        for row in rare.itertuples()
    )
    max_deviation = group_summary_payload["max_label_test_ratio_deviation"]
    report = f"""# D-004 그룹 분할 가능성 측정

## 1. 측정 대상

- 관찰군 제외: {len(hashes):,}행
- 완전일치 피처 그룹: {len(group_summary):,}개
- singleton 그룹: {summary['singleton_groups']:,}개
- 중복 그룹: {summary['duplicate_groups']:,}개
- class-overlap 그룹: {summary['conflict_groups']:,}개
- 그룹 키는 직전 class-overlap 조사에서 59개 실제 값으로 재검증했고 해시 충돌은 0건이었다.

## 2. 완전일치 그룹 기반 분할

- train: {group_train_rows:,}행
- test: {group_test_rows:,}행 ({group_test_rows / len(hashes):.8%})
- train/test를 가로지른 완전일치 그룹: 0개
- test에서 빠진 라벨: {group_summary_payload['labels_missing_from_test'] or '없음'}
- train에서 빠진 라벨: {group_summary_payload['labels_missing_from_train'] or '없음'}
- 라벨별 test 비율의 25% 대비 최대 절대편차: {max_deviation:.8%}p
- class-overlap 그룹: train {group_summary_payload['conflict_groups_train']}개/{group_summary_payload['conflict_rows_train']:,}행, test {group_summary_payload['conflict_groups_test']}개/{group_summary_payload['conflict_rows_test']:,}행

### 100행 미만 라벨

| Label | 전체 | train | test | test 비율 |
|---|---:|---:|---:|---:|
{rare_lines}

## 3. 행 단위 랜덤 분할의 낙관적 누수

- test: {leakage['test_rows']:,}행
- train/test를 가로지른 완전일치 그룹: {leakage['cross_split_feature_groups']:,}개
- train에 동일한 59-feature 값이 존재하는 test 행: {leakage['test_rows_with_feature_seen_in_train']:,}행 ({leakage['test_rows_with_feature_seen_in_train_ratio']:.8%})
- train에 동일한 원래 Label까지 존재하는 test 행: {leakage['test_rows_with_same_original_label_in_train']:,}행 ({leakage['test_rows_with_same_original_label_in_train_ratio']:.8%})
- train에 동일 피처·반대 이진 라벨이 존재하는 test 행: {leakage['test_rows_with_opposite_binary_label_in_train']:,}행 ({leakage['test_rows_with_opposite_binary_label_in_train_ratio']:.8%})

## 4. 관찰

- 59-feature 완전일치 그룹을 유지하면서 전체 75:25와 원래 Label별 계층화를 동시에 근사할 수 있는지 수치로 확인했다.
- 행 단위 랜덤 분할의 동일-feature 누수량은 낙관적 민감도 분석의 해석 기준으로 사용한다.
- 이 문서는 분할 가능성 측정 결과이며 D-004 결정 문서 자체를 변경하지 않는다.
"""
    (args.output_dir / "report.md").write_text(report, encoding="utf-8")
    print(f"완료: {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
