"""1단계+2단계 통합 오케스트레이터 (docs/stage1_briefing.md §5 실행 순서 그대로).

1. [1단계] 로드 + dataset_manifest.json
2. [1단계] 중복 플로우 검출·처리
3. [1단계] Destination Port 분리·보존
4. [2단계] 그룹키 -> 커트라인 -> split -> LOAO 후처리
5. [1단계] train 기준 상수/중복 컬럼 제거
6. [1단계] train 기준 클리핑
7. [1단계] 최종 학습 테이블 저장

--loao-only 모드는 4단계의 그룹 계산(2~4)을 다시 하지 않는다. 단, LOAO 대상이
바뀌면 train 구성원이 바뀌어 5·6단계(컬럼 가지치기·클리핑)의 train 기준 통계도
달라지므로 이 둘은 함께 재실행한다. 이를 위해 4단계 직후(가지치기·클리핑 전)
상태를 내부 캐시(`_cache_flow_pre_pruning.parquet`)로 남겨둔다 — 공식 산출물
목록에는 없는, 재실행 최적화용 내부 파일이다.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from . import clipping, column_pruning, dedup, grouping, loao, report as report_mod
from . import reserved_columns, splitting, validate
from . import manifest as manifest_mod
from .columns import COL_GROUP_ID, COL_ORIGINAL_SPLIT, COL_SPLIT
from .io import load_day_csvs, load_parquet, save_parquet

_CACHE_FLOW = "_cache_flow_pre_pruning.parquet"
_CACHE_EXCLUDED = "_cache_excluded_labels.json"


def load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _input_paths(cfg: dict) -> dict[str, Path]:
    input_dir = Path(cfg["input_dir"])
    days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    return {d: input_dir / f"{d}.csv" for d in days}


def _write_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)


def _finish_from_grouped(
    df,
    group_index_df,
    excluded_labels: list[dict],
    reserved_df,
    ds_manifest: dict,
    dedup_report: dict,
    cfg: dict,
    output_dir: Path,
) -> int:
    """4단계 결과(df, group_index_df)를 받아 5~7단계 + 리포트 + 검증까지 마무리한다."""
    save_parquet(df, output_dir / _CACHE_FLOW)
    _write_json(excluded_labels, output_dir / _CACHE_EXCLUDED)
    save_parquet(group_index_df, output_dir / "group_index.parquet")

    pruning_decisions = column_pruning.find_constant_and_duplicate_columns(df)
    _write_json(pruning_decisions, output_dir / "dropped_constant_duplicate_columns.json")
    df = column_pruning.apply_column_pruning(df, pruning_decisions)

    df, clipping_report = clipping.clip_infinities(
        df,
        percentile=cfg.get("clip_percentile", 99.9),
        multiplier=cfg.get("clip_multiplier", 3.0),
    )
    _write_json(clipping_report, output_dir / "clipping_values.json")

    save_parquet(df, output_dir / "final_training_table.parquet")

    summary = report_mod.build_summary_report(group_index_df, excluded_labels)
    summary.to_csv(output_dir / "split_summary_report.csv", index=False)

    results, overall_passed = validate.run_all(
        group_index_df=group_index_df,
        flow_df=df,
        final_df=df,
        reserved_df=reserved_df,
        manifest=ds_manifest,
        dedup_report=dedup_report,
        clipping_report=clipping_report,
        loao_target_labels=cfg.get("loao_target_labels", []),
    )
    _write_json({"passed": overall_passed, "checks": results}, output_dir / "validation_log.json")

    snapshot = dict(cfg)
    snapshot["git_commit"] = ds_manifest.get("repo_commit_hash")
    with open(output_dir / "config.snapshot.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(snapshot, f, allow_unicode=True)

    return 0 if overall_passed else 1


def run_full(cfg: dict, repo_root: Path) -> int:
    output_dir = Path(cfg["output_dir"])
    input_paths = _input_paths(cfg)

    # 1. 로드 + manifest
    df = load_day_csvs(input_paths)
    ds_manifest = manifest_mod.build_dataset_manifest(input_paths, repo_root)
    _write_json(ds_manifest, output_dir / "dataset_manifest.json")

    # 2. 중복 처리
    df, dedup_report = dedup.process_duplicates(df)
    _write_json(dedup_report, output_dir / "duplicate_flow_report.json")

    # 3. Destination Port 분리
    df, reserved_df = reserved_columns.split_off_destination_port(df)
    save_parquet(reserved_df, output_dir / "reserved_for_early_features.parquet")

    # 4. 그룹 -> 분할 -> LOAO
    df = grouping.add_attack_label(df)
    df[COL_GROUP_ID] = grouping.compute_group_id(df, cfg["bucket_seconds"])
    group_index_df = grouping.build_group_index(df)
    group_index_df, excluded_labels = splitting.assign_split(
        group_index_df, cfg["split_ratios"], cfg["min_group_count_for_split"]
    )

    split_map = group_index_df.set_index(COL_GROUP_ID)[[COL_SPLIT, COL_ORIGINAL_SPLIT]]
    df = df.join(split_map, on=COL_GROUP_ID)

    loao_targets = cfg.get("loao_target_labels", [])
    group_index_df = loao.apply_loao_mask(group_index_df, loao_targets)
    df = loao.apply_loao_mask(df, loao_targets)

    return _finish_from_grouped(
        df, group_index_df, excluded_labels, reserved_df, ds_manifest, dedup_report, cfg, output_dir
    )


def run_loao_only(cfg: dict, repo_root: Path) -> int:
    output_dir = Path(cfg["output_dir"])

    df = load_parquet(output_dir / _CACHE_FLOW)
    group_index_df = load_parquet(output_dir / "group_index.parquet")
    with open(output_dir / _CACHE_EXCLUDED, "r", encoding="utf-8") as f:
        excluded_labels = json.load(f)
    with open(output_dir / "dataset_manifest.json", "r", encoding="utf-8") as f:
        ds_manifest = json.load(f)
    with open(output_dir / "duplicate_flow_report.json", "r", encoding="utf-8") as f:
        dedup_report = json.load(f)
    reserved_df = load_parquet(output_dir / "reserved_for_early_features.parquet")

    loao_targets = cfg.get("loao_target_labels", [])
    group_index_df = loao.apply_loao_mask(group_index_df, loao_targets)
    df = loao.apply_loao_mask(df, loao_targets)

    return _finish_from_grouped(
        df, group_index_df, excluded_labels, reserved_df, ds_manifest, dedup_report, cfg, output_dir
    )
