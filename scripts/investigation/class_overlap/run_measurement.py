#!/usr/bin/env python
"""Measure exact 59-feature duplicates and binary class overlap.

This implements tasks/task_duplicate_class_overlap_measurement.md. Raw CSV files
are read only. Duplicate rows are measured, never removed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "investigation"))

from class_overlap.analysis import (  # noqa: E402
    ScopeAccumulator,
    distribution_rows,
    duplicate_hashes,
    feature_hash,
    normalize_features,
    process_candidate_bucket,
)

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday")
EXPECTED_ROWS = {
    "monday.csv": 371_624,
    "tuesday.csv": 322_078,
    "wednesday.csv": 496_641,
    "thursday.csv": 362_076,
    "friday.csv": 547_557,
}
EXPECTED_TOTAL_ROWS = 2_099_976
EXPECTED_ATTEMPTED_ROWS = 11_979
EXPECTED_HULK_ROWS = 158_468
EXPECTED_TARGET_ROWS = 1_929_529
EXPECTED_BENIGN_ROWS = 1_582_566
EXPECTED_ATTACK_ROWS = 346_963


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
        default=REPO_ROOT / "reports" / "class_overlap",
    )
    parser.add_argument("--chunk-size", type=int, default=100_000)
    parser.add_argument("--hash-buckets", type=int, default=32)
    return parser.parse_args()


def sha256_and_data_rows(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    newlines = 0
    last_byte = b""
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            digest.update(block)
            newlines += block.count(b"\n")
            last_byte = block[-1:]
    data_rows = newlines - 1 + (1 if last_byte and last_byte != b"\n" else 0)
    return digest.hexdigest(), data_rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


def load_whitelist(path: Path) -> tuple[list[str], list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    include = payload["include"]
    exclude = list(payload["exclude"])
    if len(include) != 59 or len(exclude) != 32:
        raise ValueError(
            f"Whitelist cardinality mismatch: include={len(include)}, exclude={len(exclude)}"
        )
    if len(set(include)) != len(include) or len(set(exclude)) != len(exclude):
        raise ValueError("Whitelist contains duplicate column names")
    overlap = sorted(set(include) & set(exclude))
    if overlap:
        raise ValueError(f"Whitelist include/exclude overlap: {overlap}")
    if "Protocol" not in include:
        raise ValueError("Protocol must be included")
    return include, exclude


def validate_integrity(
    input_dir: Path,
    source_zip: Path,
    include: list[str],
    exclude: list[str],
) -> tuple[dict, list[str]]:
    headers: dict[str, list[str]] = {}
    file_sha256: dict[str, str] = {}
    row_counts: dict[str, int] = {}

    for day in DAYS:
        filename = f"{day}.csv"
        path = input_dir / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        headers[filename] = read_header(path)
        digest, rows = sha256_and_data_rows(path)
        file_sha256[filename] = digest
        row_counts[filename] = rows
        if rows != EXPECTED_ROWS[filename]:
            raise RuntimeError(
                f"Integrity stop: {filename} rows={rows}, expected={EXPECTED_ROWS[filename]}"
            )

    reference_header = headers["monday.csv"]
    if any(header != reference_header for header in headers.values()):
        raise RuntimeError("Integrity stop: CSV headers differ")
    if len(reference_header) != 91:
        raise RuntimeError(
            f"Integrity stop: column count={len(reference_header)}, expected=91"
        )
    classified = set(include) | set(exclude)
    if classified != set(reference_header):
        raise RuntimeError(
            "Integrity stop: whitelist classification and CSV header differ; "
            f"missing={sorted(set(reference_header) - classified)}, "
            f"unknown={sorted(classified - set(reference_header))}"
        )
    if sum(row_counts.values()) != EXPECTED_TOTAL_ROWS:
        raise RuntimeError(
            f"Integrity stop: total rows={sum(row_counts.values())}, "
            f"expected={EXPECTED_TOTAL_ROWS}"
        )
    if not source_zip.is_file():
        raise FileNotFoundError(source_zip)

    manifest = {
        "file_sha256": file_sha256,
        "row_counts": row_counts,
        "manifest_created_at": datetime.now(timezone.utc).isoformat(),
        "source_zip_sha256": sha256_file(source_zip),
    }
    return manifest, reference_header


def write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def iter_chunks(
    input_dir: Path,
    usecols: list[str],
    chunk_size: int,
):
    dtype = {column: "float64" for column in usecols if column not in {"Protocol", "Label", "id"}}
    dtype.update({"Protocol": "int16", "Label": "string", "id": "int64"})
    for day in DAYS:
        path = input_dir / f"{day}.csv"
        for chunk_index, chunk in enumerate(
            pd.read_csv(
                path,
                usecols=usecols,
                dtype=dtype,
                chunksize=chunk_size,
                low_memory=False,
            )
        ):
            yield day, chunk_index, chunk


def first_pass(
    input_dir: Path,
    feature_columns: list[str],
    chunk_size: int,
) -> tuple[np.ndarray, np.ndarray, dict]:
    all_hash_parts: list[np.ndarray] = []
    target_parts: list[np.ndarray] = []
    counts = {
        "total_rows": 0,
        "attempted_rows": 0,
        "invalid_class_rows": 0,
        "observation_group_overlap_rows": 0,
        "target_rows": 0,
        "target_benign_rows": 0,
        "target_attack_rows": 0,
    }
    usecols = list(dict.fromkeys(feature_columns + ["Label", "id"]))

    for day, chunk_index, chunk in iter_chunks(input_dir, usecols, chunk_size):
        features = normalize_features(chunk, feature_columns)
        hashes = feature_hash(features)
        labels = chunk["Label"]
        attempted = labels.str.endswith("- Attempted", na=False).to_numpy(dtype=bool)
        invalid_class = labels.eq("DoS Hulk").to_numpy(dtype=bool)
        target = ~(attempted | invalid_class)

        all_hash_parts.append(hashes)
        target_parts.append(target)
        counts["total_rows"] += len(chunk)
        counts["attempted_rows"] += int(attempted.sum())
        counts["invalid_class_rows"] += int(invalid_class.sum())
        counts["observation_group_overlap_rows"] += int((attempted & invalid_class).sum())
        counts["target_rows"] += int(target.sum())
        counts["target_benign_rows"] += int((target & labels.eq("BENIGN").to_numpy()).sum())
        counts["target_attack_rows"] += int((target & labels.ne("BENIGN").to_numpy()).sum())
        print(f"  hash pass: {day} chunk {chunk_index + 1}, total={counts['total_rows']:,}")

    expected = {
        "total_rows": EXPECTED_TOTAL_ROWS,
        "attempted_rows": EXPECTED_ATTEMPTED_ROWS,
        "invalid_class_rows": EXPECTED_HULK_ROWS,
        "observation_group_overlap_rows": 0,
        "target_rows": EXPECTED_TARGET_ROWS,
        "target_benign_rows": EXPECTED_BENIGN_ROWS,
        "target_attack_rows": EXPECTED_ATTACK_ROWS,
    }
    if counts != expected:
        raise RuntimeError(f"Target population stop: actual={counts}, expected={expected}")
    return np.concatenate(all_hash_parts), np.concatenate(target_parts), counts


def stage_candidates(
    input_dir: Path,
    feature_columns: list[str],
    candidate_hashes: np.ndarray,
    chunk_size: int,
    hash_buckets: int,
    temporary_dir: Path,
) -> int:
    usecols = list(dict.fromkeys(feature_columns + ["Label", "id"]))
    staged_rows = 0
    for day, chunk_index, chunk in iter_chunks(input_dir, usecols, chunk_size):
        features = normalize_features(chunk, feature_columns)
        hashes = feature_hash(features)
        selected = np.isin(hashes, candidate_hashes, assume_unique=False)
        if not selected.any():
            continue
        selected_frame = features.loc[selected].copy()
        selected_frame["_label"] = chunk.loc[selected, "Label"].astype(str).to_numpy()
        selected_frame["_day"] = day
        selected_frame["_id"] = chunk.loc[selected, "id"].to_numpy(dtype=np.int64)
        selected_frame["_feature_hash"] = hashes[selected]
        selected_frame["_target"] = ~(
            selected_frame["_label"].str.endswith("- Attempted", na=False)
            | selected_frame["_label"].eq("DoS Hulk")
        )
        selected_frame["_bucket"] = (
            selected_frame["_feature_hash"].to_numpy(dtype=np.uint64)
            % np.uint64(hash_buckets)
        ).astype(np.uint16)
        staged_rows += len(selected_frame)
        for bucket, bucket_frame in selected_frame.groupby("_bucket", sort=False):
            path = temporary_dir / f"b{int(bucket):03d}_{day}_{chunk_index:04d}.pkl"
            bucket_frame.drop(columns="_bucket").to_pickle(path)
        print(f"  verify stage: {day} chunk {chunk_index + 1}, candidates={staged_rows:,}")
    return staged_rows


def process_staged_candidates(
    temporary_dir: Path,
    feature_columns: list[str],
    hash_buckets: int,
) -> tuple[ScopeAccumulator, ScopeAccumulator, int]:
    target = ScopeAccumulator("target_excluding_observation_groups")
    full = ScopeAccumulator("full_including_observation_groups")
    collision_count = 0
    for bucket in range(hash_buckets):
        paths = sorted(temporary_dir.glob(f"b{bucket:03d}_*.pkl"))
        if not paths:
            continue
        frames = [pd.read_pickle(path) for path in paths]
        bucket_frame = pd.concat(frames, ignore_index=True)
        collision_count += process_candidate_bucket(
            bucket_frame, feature_columns, target, full
        )
        print(
            f"  exact verify: bucket {bucket + 1}/{hash_buckets}, "
            f"rows={len(bucket_frame):,}"
        )
        del frames, bucket_frame
    return target, full, collision_count


def write_outputs(
    output_dir: Path,
    manifest: dict,
    population_counts: dict,
    target: ScopeAccumulator,
    full: ScopeAccumulator,
    collision_count: int,
    staged_rows: int,
) -> None:
    target_summary = target.summary(EXPECTED_TARGET_ROWS)
    full_summary = full.summary(EXPECTED_TOTAL_ROWS)
    summary = {
        "comparison_key_feature_count": 59,
        "protocol_representation": "categorical: TCP/UDP/ICMP/UNKNOWN",
        "population_counts": population_counts,
        "candidate_hash_rows_staged": staged_rows,
        "verified_hash_collision_subgroups": collision_count,
        "target": target_summary,
        "full_reference": full_summary,
    }
    write_json(summary, output_dir / "summary.json")

    distribution = pd.DataFrame(
        list(distribution_rows(target)) + list(distribution_rows(full))
    )
    distribution.to_csv(output_dir / "group_size_distribution.csv", index=False)

    label_rows = [
        {"Label": label, "row_count": count}
        for label, count in target.conflict_labels.most_common()
    ]
    pd.DataFrame(label_rows, columns=["Label", "row_count"]).to_csv(
        output_dir / "conflict_label_distribution.csv", index=False
    )

    sample_columns = [
        "group_id",
        "group_size",
        "sampled_rows",
        "sample_truncated",
        "day",
        "id",
        "Label",
        "binary_label",
        "Protocol",
        "Flow Duration",
        "Total Fwd Packet",
        "Total Length of Fwd Packet",
        "Total Length of Bwd Packet",
        "Flow Bytes/s",
        "SYN Flag Count",
        "RST Flag Count",
        "ACK Flag Count",
    ]
    pd.DataFrame(target.top_conflict_rows(), columns=sample_columns).to_csv(
        output_dir / "conflict_groups_sample.csv", index=False
    )

    hashes = manifest["file_sha256"]
    conflict_pct = target_summary["label_conflict_row_ratio"] * 100
    duplicate_pct = target_summary["duplicate_row_ratio"] * 100
    conflict_day_rows = "\n".join(
        f"| {day} | {count:,} |"
        for day, count in sorted(target.conflict_days.items())
    )
    conflict_day_combination_rows = "\n".join(
        f"| {combination} | {count:,} |"
        for combination, count in sorted(target.conflict_day_combinations.items())
    )
    report = f"""# 59-feature 중복 행 및 class overlap 측정

## 1. 무결성 검증

- 데이터 행 수: {population_counts['total_rows']:,}행 (기대값 일치)
- 컬럼: 91개, 요일별 헤더 동일
- 비교 키: `configs/features_whitelist.json`의 include 59개
- `Protocol`: TCP/UDP/ICMP/UNKNOWN 범주로 변환
- 원본 ZIP SHA256: `{manifest['source_zip_sha256']}`

| 파일 | 데이터 행 수 | SHA256 |
|---|---:|---|
| monday.csv | {manifest['row_counts']['monday.csv']:,} | `{hashes['monday.csv']}` |
| tuesday.csv | {manifest['row_counts']['tuesday.csv']:,} | `{hashes['tuesday.csv']}` |
| wednesday.csv | {manifest['row_counts']['wednesday.csv']:,} | `{hashes['wednesday.csv']}` |
| thursday.csv | {manifest['row_counts']['thursday.csv']:,} | `{hashes['thursday.csv']}` |
| friday.csv | {manifest['row_counts']['friday.csv']:,} | `{hashes['friday.csv']}` |

## 2. 대상 행 집합

- Attempted 관찰군: {population_counts['attempted_rows']:,}행
- 무효 클래스 관찰군: {population_counts['invalid_class_rows']:,}행
- 두 관찰군의 교집합: {population_counts['observation_group_overlap_rows']:,}행
- 학습·평가 대상: {population_counts['target_rows']:,}행
- BENIGN: {population_counts['target_benign_rows']:,}행
- 공격: {population_counts['target_attack_rows']:,}행

## 3. 관찰군 제외 기준 결과

| 항목 | 그룹 수 | 행 수 |
|---|---:|---:|
| 전체 중복 | {target_summary['duplicate_groups']:,} | {target_summary['duplicate_rows']:,} |
| 라벨 일치 중복 | {target_summary['label_match_groups']:,} | {target_summary['label_match_rows']:,} |
| 이진 라벨 충돌 | {target_summary['label_conflict_groups']:,} | {target_summary['label_conflict_rows']:,} |

- 중복 행 비율: {duplicate_pct:.8f}%
- 이진 라벨 충돌 행 비율: {conflict_pct:.8f}%
- 파일 내부 충돌 그룹: {target.within_file_conflict_groups:,}개 / {target.within_file_conflict_rows:,}행
- 파일 간 충돌 그룹: {target.cross_file_conflict_groups:,}개 / {target.cross_file_conflict_rows:,}행
- `Flow Bytes/s` Infinity 포함 중복: {target.duplicate_groups_with_infinite_flow_bytes:,}그룹 / {target.duplicate_rows_with_infinite_flow_bytes:,}행
- `Flow Bytes/s` Infinity 포함 충돌: {target.conflict_groups_with_infinite_flow_bytes:,}그룹 / {target.conflict_rows_with_infinite_flow_bytes:,}행

### 충돌 행의 요일 분포

| 요일 | 행 수 |
|---|---:|
{conflict_day_rows}

| 충돌 그룹의 요일 조합 | 그룹 수 |
|---|---:|
{conflict_day_combination_rows}

## 4. 전체 데이터 참고 측정

| 항목 | 그룹 수 | 행 수 |
|---|---:|---:|
| 전체 중복 | {full_summary['duplicate_groups']:,} | {full_summary['duplicate_rows']:,} |
| 라벨 일치 중복 | {full_summary['label_match_groups']:,} | {full_summary['label_match_rows']:,} |
| 이진 라벨 충돌 | {full_summary['label_conflict_groups']:,} | {full_summary['label_conflict_rows']:,} |

## 5. 검증과 해석 범위

- 64비트 행 해시는 중복 후보 탐색에만 사용했다. 후보 그룹은 59개 원본 파싱 값을 다시 비교해 완전 일치를 검증했다.
- 실제 값 재검증 과정에서 분리된 해시 충돌 하위그룹 수는 {collision_count:,}개다.
- `conflict_groups_sample.csv`는 크기 상위 20개 충돌 그룹에서 라벨별 대표를 우선해 그룹당 최대 20행을 기록한다. `sample_truncated`가 참이면 일부 행만 수록됐다.
- 이진 라벨 충돌 행은 대상 집합의 {conflict_pct:.8f}%다. 이 수치는 유보 구간의 일부가 데이터 표현 충돌에서 비롯될 가능성을 정량화하지만, 유보 구간의 존재나 처리 정책에 대한 결론 자체는 내리지 않는다.
"""
    (output_dir / "report.md").write_text(report, encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.chunk_size <= 0:
        raise ValueError("--chunk-size must be positive")
    if args.hash_buckets <= 0:
        raise ValueError("--hash-buckets must be positive")

    whitelist_path = REPO_ROOT / "configs" / "features_whitelist.json"
    include, exclude = load_whitelist(whitelist_path)

    print("[1/5] CSV 행 수, SHA256, 헤더, whitelist 무결성 검증")
    manifest, _ = validate_integrity(args.input_dir, args.source_zip, include, exclude)
    write_json(manifest, REPO_ROOT / "data" / "dataset_manifest.json")

    print("[2/5] 59-feature 후보 해시 및 대상 행 집합 검증")
    all_hashes, target_mask, population_counts = first_pass(
        args.input_dir, include, args.chunk_size
    )
    full_candidates = duplicate_hashes(all_hashes)
    target_candidates = duplicate_hashes(all_hashes[target_mask])
    candidate_hashes = np.union1d(full_candidates, target_candidates)
    print(
        f"  duplicate candidate hashes: target={len(target_candidates):,}, "
        f"full={len(full_candidates):,}, union={len(candidate_hashes):,}"
    )

    print("[3/5] 중복 후보 행 임시 분할 저장")
    with tempfile.TemporaryDirectory(prefix="class_overlap_") as temp_name:
        temporary_dir = Path(temp_name)
        staged_rows = stage_candidates(
            args.input_dir,
            include,
            candidate_hashes,
            args.chunk_size,
            args.hash_buckets,
            temporary_dir,
        )
        print("[4/5] 59개 원본 값 재비교 및 집계")
        target, full, collision_count = process_staged_candidates(
            temporary_dir, include, args.hash_buckets
        )

    print("[5/5] 결과 파일 작성")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_outputs(
        args.output_dir,
        manifest,
        population_counts,
        target,
        full,
        collision_count,
        staged_rows,
    )
    print(f"완료: {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
