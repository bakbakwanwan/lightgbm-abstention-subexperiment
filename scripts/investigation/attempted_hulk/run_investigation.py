#!/usr/bin/env python
"""tasks/instruction_attempted_hulk_investigation.md 실행 스크립트 (읽기 전용 조사).

사용:
    .venv\\Scripts\\python.exe scripts\\investigation\\attempted_hulk\\run_investigation.py
    .venv\\Scripts\\python.exe scripts\\investigation\\attempted_hulk\\run_investigation.py \
        --target-reason-codes 1 3   # 작업2 사유 코드->이름 매핑을 확인한 뒤 S2 계산에 사용

이 스크립트는 데이터 파일을 수정하지 않는다. reports/attempted_hulk_investigation/
아래에만 쓴다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "investigation"))

from attempted_hulk import (  # noqa: E402
    attempted_breakdown,
    columns_resolve,
    hulk_shortcut,
    label_inventory,
    manifest_util,
    raw_loader,
    scenario_compare,
)
from cicids_prep.columns import COL_ID, COL_LABEL  # noqa: E402

INPUT_DIR = REPO_ROOT / "data" / "CICIDS2017_improved_2022ver"
PROCESSED_DIR = REPO_ROOT / "data" / "processed" / "cicids_prep"
OUTPUT_DIR = REPO_ROOT / "reports" / "attempted_hulk_investigation"
CONFIG_PATH = REPO_ROOT / "configs" / "exp" / "cicids_prep.yaml"

OLD_DOC_CLAIMS = {
    "attempted_total_rows": 447362,
    "hulk_total_flows": 545438,
    "hulk_exceptions_to_shortcut": 8,
    "hulk_shortcut_values": [11595, 23190, 11606, 23201],
}


def _write_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--target-reason-codes",
        nargs="*",
        type=int,
        default=None,
        help="작업2에서 확인된 'Target Unresponsive'/'Port,System Closed'에 해당하는"
        " Attempted Category 코드값. 주어지면 시나리오 S2를 계산한다.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    findings: dict = {}
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    print("[1/9] 헤더 일치성 확인 (작업 2-3-3 겸 1-6)...")
    header_check = raw_loader.check_header_consistency(INPUT_DIR)
    findings["header_consistency"] = {
        "consistent": header_check["consistent"],
        "mismatches": header_check["mismatches"],
    }
    if not header_check["consistent"]:
        _write_json(findings, OUTPUT_DIR / "run_findings_partial.json")
        print("헤더 불일치 발견 -> 지시서 8-1에 따라 중단")
        return 1
    header = header_check["headers"][header_check["reference_day"]]
    print(f"  5개 파일 헤더 동일, {len(header)}개 컬럼")

    print("[2/9] 컬럼 해석 (라벨 / Attempted 사유 / DoS Hulk 대상 컬럼)...")
    resolved: dict[str, str] = {}
    col_errors: dict[str, str] = {}
    for key, tokens, purpose in [
        ("label", ["label"], "라벨 컬럼"),
        ("attempted_category", ["attempt", "categ"], "Attempted 사유 컬럼"),
        ("hulk_length_col", ["total", "length", "bwd"], "DoS Hulk shortcut 대상 컬럼"),
    ]:
        try:
            resolved[key] = columns_resolve.resolve_single(header, tokens, purpose)
            print(f"  {purpose}: '{resolved[key]}'")
        except columns_resolve.ColumnResolutionError as e:
            col_errors[key] = str(e)
            print(f"  [실패] {purpose}: {e}")
    findings["column_resolution"] = {"resolved": resolved, "errors": col_errors}

    if "label" not in resolved:
        _write_json(findings, OUTPUT_DIR / "run_findings_partial.json")
        print("라벨 컬럼 특정 불가 -> 지시서 8-1에 따라 전체 중단")
        return 1
    label_col = resolved["label"]

    print("[3/9] 원본 CSV 5개 병합 로드 (약 210만 행, 시간이 걸림)...")
    raw_df = raw_loader.load_raw_merged(INPUT_DIR)
    print(f"  raw_df shape={raw_df.shape}")

    print("[4/9] 파이프라인 산출물 로드...")
    final_df = None
    pipeline_cache_df = None
    missing_outputs = []
    try:
        final_df = pd.read_parquet(PROCESSED_DIR / "final_training_table.parquet")
        print(f"  final_training_table.parquet shape={final_df.shape}")
    except FileNotFoundError:
        missing_outputs.append("final_training_table.parquet")
    try:
        pipeline_cache_df = pd.read_parquet(PROCESSED_DIR / "_cache_flow_pre_pruning.parquet")
        print(f"  _cache_flow_pre_pruning.parquet shape={pipeline_cache_df.shape}")
    except FileNotFoundError:
        missing_outputs.append("_cache_flow_pre_pruning.parquet")
    if missing_outputs:
        findings["missing_pipeline_outputs"] = missing_outputs

    print("[5/9] 작업1 라벨 인벤토리...")
    inv = label_inventory.build_label_inventory(raw_df, final_df)
    _write_json(inv, OUTPUT_DIR / "label_inventory_summary.json")
    lbd = label_inventory.label_by_day(raw_df)
    _write_csv(lbd, OUTPUT_DIR / "label_inventory.csv")
    if final_df is not None:
        lbs = label_inventory.label_by_split(final_df)
        _write_csv(lbs, OUTPUT_DIR / "label_by_split.csv")
    print(f"  고유 라벨(원본) {inv['n_unique_labels_raw']}개, Attempted 총 {inv['attempted_total_rows_raw']}행")
    print(f"  구 문서 주장(447,362건)과의 차이: {inv['attempted_total_rows_raw'] - OLD_DOC_CLAIMS['attempted_total_rows']}")

    print("[6/9] 작업2 Attempted 사유 판정 (최우선)...")
    attempted_result: dict = {"resolved": "attempted_category" in resolved}
    if "attempted_category" in resolved:
        cat_col = resolved["attempted_category"]
        consistency = attempted_breakdown.consistency_check(raw_df, cat_col, label_col)
        attempted_result["consistency"] = consistency
        crosstab = attempted_breakdown.label_category_crosstab(raw_df, cat_col, label_col)
        _write_csv(crosstab, OUTPUT_DIR / "attempted_breakdown.csv")
        print(f"  '{cat_col}' 발견. sentinel_ambiguous={consistency['sentinel_ambiguous']}, "
              f"n_mismatch={consistency.get('n_mismatch')}")
    else:
        attempted_result["error"] = col_errors.get("attempted_category")
        print("  Attempted 사유 컬럼 미확정 -> 판정 B/C 검토 필요")
    _write_json(attempted_result, OUTPUT_DIR / "attempted_breakdown_summary.json")

    print("[7/9] 작업3 DoS Hulk shortcut 실측...")
    hulk_result: dict = {"resolved": "hulk_length_col" in resolved}
    benign_contam = False
    if "hulk_length_col" in resolved:
        val_col = resolved["hulk_length_col"]
        occ = hulk_shortcut.value_occurrences(raw_df, val_col, label_col)
        hulk_result["value_occurrences"] = occ
        hulk_result["not_in_shortcut"] = hulk_shortcut.hulk_not_in_shortcut(raw_df, val_col, label_col)
        hulk_result["distribution"] = hulk_shortcut.hulk_value_distribution(raw_df, val_col, label_col)
        benign_contam = any(v["benign_rows"] > 0 for v in occ.values())

        # 545,438 모수 탐색 (지시서 4-3-5): 원본/파이프라인, 라벨 정의별 후보 총계
        candidates = {
            "hulk_family_rows_raw": int(hulk_shortcut.hulk_mask(raw_df, label_col).sum()),
            "dos_hulk_exact_label_rows_raw": int((raw_df[label_col] == "DoS Hulk").sum()),
        }
        if pipeline_cache_df is not None:
            candidates["hulk_family_rows_pipeline_postdedup"] = int(
                hulk_shortcut.hulk_mask(pipeline_cache_df, label_col).sum()
            )
        if final_df is not None:
            candidates["hulk_family_rows_pipeline_final"] = int(
                hulk_shortcut.hulk_mask(final_df, label_col).sum()
            )
        hulk_result["n_545438_candidates"] = candidates
    else:
        hulk_result["error"] = col_errors.get("hulk_length_col")

    n_benign_contaminated = sum(v["benign_rows"] for v in hulk_result.get("value_occurrences", {}).values())
    n_benign_total = int((raw_df[label_col] == "BENIGN").sum())
    contamination_ratio = (n_benign_contaminated / n_benign_total) if n_benign_total else None
    hulk_result["benign_contamination"] = {
        "n_benign_rows_with_shortcut_values": n_benign_contaminated,
        "n_benign_total": n_benign_total,
        "ratio": contamination_ratio,
    }
    # 지시서 8-3은 "상당수" 발견 시 중단을 요구한다. 임의 임계값을 정책으로 쓰지
    # 않되, 명백히 사소한 수준(전체 BENIGN 대비 0.1% 미만)까지 실행을 막는 것은
    # 조사 자체를 무력화하므로, 이 경우엔 계속 진행하고 수치를 report에 그대로
    # 남겨 사람이 "상당수"인지 판단하게 한다.
    benign_contam = bool(contamination_ratio and contamination_ratio > 0.001)
    hulk_result["benign_contamination_detected"] = benign_contam
    _write_json(hulk_result, OUTPUT_DIR / "hulk_shortcut.json")

    if benign_contam:
        findings["stop_condition_triggered"] = "지시서 8-3: 4개 값을 가진 BENIGN 행 다수 발견"
        _write_json(findings, OUTPUT_DIR / "run_findings_partial.json")
        print("BENIGN 혼입 발견 -> 지시서 8-3에 따라 이후 무거운 연산(단일컬럼 스캔/시나리오비교) 생략하고 중단")
        return 2

    print("[8/9] 작업4-5 단일 컬럼 shortcut 예비 스캔 (라벨별 x 전체 수치형 컬럼)...")
    exclude_cols = {COL_ID}
    numeric_cols = [
        c for c in raw_df.columns
        if pd.api.types.is_numeric_dtype(raw_df[c]) and c not in exclude_cols
    ]
    scan_df = hulk_shortcut.scan_single_column_shortcuts(raw_df, numeric_cols, label_col)
    _write_csv(scan_df, OUTPUT_DIR / "single_column_shortcut_scan.csv")
    print(f"  스캔 완료: {len(scan_df)}건 (라벨,컬럼) 조합이 top10-coverage>=0.9")

    print("[9/9] 작업4/5 시나리오 비교 (S0~S4, 인메모리)...")
    hulk_family_labels = sorted(
        raw_df.loc[hulk_shortcut.hulk_mask(raw_df, label_col), label_col].unique().tolist()
    )
    attempted_labels_list = label_inventory.attempted_labels(raw_df)
    print(f"  Hulk 계열 라벨: {hulk_family_labels}")
    print(f"  Attempted 라벨 {len(attempted_labels_list)}개")

    scenario_report_rows = []
    exclusion_report: dict[str, list[dict]] = {}

    def run_scenario_set(df_in: pd.DataFrame, basis_name: str, has_group_id: bool) -> None:
        cat_col = resolved.get("attempted_category")
        df_work = df_in if has_group_id else scenario_compare.prepare_group_id(df_in, cfg["bucket_seconds"])
        target_codes = args.target_reason_codes
        scenarios = scenario_compare.build_scenario_masks(
            df_work,
            hulk_family_labels,
            attempted_labels_list,
            label_col,
            category_col=cat_col if (cat_col and target_codes) else None,
            target_reason_codes=target_codes,
        )
        baseline_labels = sorted(df_work[label_col].dropna().unique().tolist())
        for name, mask in scenarios.items():
            summary = scenario_compare.scenario_row_summary(df_work, mask, label_col)
            dropped = scenario_compare.labels_dropped_to_zero(baseline_labels, summary["per_label"], label_col)
            n_attack = scenario_compare.n_attack_labels_remaining(summary["per_label"], label_col)

            _, excluded = scenario_compare.compute_below_min_group_count(
                df_work[mask], cfg["split_ratios"], cfg["min_group_count_for_split"]
            )
            exclusion_report[f"{basis_name}:{name}"] = excluded

            scenario_report_rows.append(
                {
                    "basis": basis_name,
                    "scenario": name,
                    "total_rows": summary["total_rows"],
                    "benign_rows": summary["benign_rows"],
                    "attack_rows": summary["attack_rows"],
                    "n_attack_labels_remaining": n_attack,
                    "n_labels_dropped_to_zero": len(dropped),
                    "labels_dropped_to_zero": ";".join(dropped),
                    "n_below_min_group_count_labels": len(excluded),
                }
            )
            for row in summary["per_label"].to_dict(orient="records"):
                scenario_report_rows[-1].setdefault("_per_label", []).append(row)

    run_scenario_set(raw_df, "raw_predup", has_group_id=False)
    if pipeline_cache_df is not None:
        run_scenario_set(pipeline_cache_df, "pipeline_postdedup", has_group_id=True)
    else:
        findings.setdefault("skipped", []).append(
            "시나리오 비교 pipeline_postdedup 기준: _cache_flow_pre_pruning.parquet 없음"
        )

    scenario_df = pd.DataFrame(
        [{k: v for k, v in row.items() if k != "_per_label"} for row in scenario_report_rows]
    )
    _write_csv(scenario_df, OUTPUT_DIR / "scenario_comparison.csv")

    per_label_rows = []
    for row in scenario_report_rows:
        for pl in row.get("_per_label", []):
            per_label_rows.append({"basis": row["basis"], "scenario": row["scenario"], **pl})
    _write_csv(pd.DataFrame(per_label_rows), OUTPUT_DIR / "scenario_comparison_per_label.csv")
    _write_json(exclusion_report, OUTPUT_DIR / "scenario_below_min_group_count.json")

    if not (resolved.get("attempted_category") and args.target_reason_codes):
        findings.setdefault("skipped", []).append(
            "S2: attempted_category 컬럼 또는 --target-reason-codes 미확정으로 계산하지 않음"
        )

    print("[manifest] run_manifest.json 기록...")
    manifest = manifest_util.build_run_manifest(
        raw_loader.input_paths(INPUT_DIR),
        REPO_ROOT,
        resolved_columns=resolved,
        notes={"old_doc_claims": OLD_DOC_CLAIMS, "findings": findings},
    )
    _write_json(manifest, OUTPUT_DIR / "run_manifest.json")
    _write_json(findings, OUTPUT_DIR / "run_findings.json")

    print("완료.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
