"""검증 — split_protocol_proposal.md 6장 + stage1_briefing.md 7장 통합.

각 함수는 {"name", "passed", "level", "detail"}를 반환한다. level="warning"은
전체 실패에 반영하지 않는다(6-3처럼 정상적으로 발생 가능한 상황을 알리는 용도).
run_all()이 전부 실행한 뒤(첫 실패에서 멈추지 않음) 하나라도 error 레벨에서
fail이면 전체를 fail로 판정한다.
"""

from __future__ import annotations

import pandas as pd

from .columns import (
    COL_ATTACK_LABEL,
    COL_DAY,
    COL_DST_PORT,
    COL_GROUP_ID,
    COL_INVALID_NEG_DURATION_FLAG,
    COL_LABEL_CONFLICT_FLAG,
    COL_ROW_UID,
    COL_SPLIT,
    SYNTHETIC_COLS,
)
from .dedup import remove_exact_duplicates


def _result(name: str, passed: bool, detail: dict, level: str = "error") -> dict:
    return {"name": name, "passed": passed, "level": level, "detail": detail}


# --- 2단계 (split_protocol_proposal.md 6장) ---------------------------------


def check_group_split_exclusivity(group_index_df: pd.DataFrame) -> dict:
    by_split = {
        s: set(group_index_df.loc[group_index_df[COL_SPLIT] == s, COL_GROUP_ID])
        for s in ("train", "calib", "test")
    }
    overlaps = {
        f"{a}-{b}": len(by_split[a] & by_split[b])
        for a, b in (("train", "test"), ("calib", "test"), ("train", "calib"))
    }
    passed = all(v == 0 for v in overlaps.values())
    return _result("6-1 group_id_split_exclusivity", passed, overlaps)


def check_row_level_train_calib_exclusivity(flow_df: pd.DataFrame) -> dict:
    train_uids = set(flow_df.loc[flow_df[COL_SPLIT] == "train", COL_ROW_UID])
    calib_uids = set(flow_df.loc[flow_df[COL_SPLIT] == "calib", COL_ROW_UID])
    overlap = len(train_uids & calib_uids)
    return _result("6-2 row_uid_train_calib_exclusivity", overlap == 0, {"overlap": overlap})


def check_split_skew(flow_df: pd.DataFrame) -> dict:
    pivot = (
        flow_df.groupby([COL_DAY, COL_ATTACK_LABEL])[COL_SPLIT]
        .value_counts(normalize=True)
        .unstack(fill_value=0.0)
    )
    fully_skewed = pivot[(pivot == 1.0).any(axis=1)]
    detail = {"n_fully_skewed_day_label_pairs": int(len(fully_skewed))}
    return _result("6-3 split_skew_warning", True, detail, level="warning")


def check_loao_target_absent_from_train(flow_df: pd.DataFrame, loao_target_labels: list[str]) -> dict:
    if not loao_target_labels:
        return _result("6-4 loao_target_absent_from_train", True, {"loao_target_labels": []})
    remaining_in_train = int(
        flow_df.loc[
            flow_df[COL_ATTACK_LABEL].isin(loao_target_labels) & (flow_df[COL_SPLIT] == "train")
        ].shape[0]
    )
    return _result(
        "6-4 loao_target_absent_from_train",
        remaining_in_train == 0,
        {"loao_target_labels": loao_target_labels, "remaining_in_train": remaining_in_train},
    )


# --- 1단계 (stage1_briefing.md 7장) -----------------------------------------


def check_no_exact_duplicates(final_df: pd.DataFrame) -> dict:
    _, n_removed_if_rerun = remove_exact_duplicates(final_df)
    return _result("7-1 no_exact_duplicates", n_removed_if_rerun == 0, {"would_remove": n_removed_if_rerun})


def check_label_conflict_preserved(final_df: pd.DataFrame, dedup_report: dict) -> dict:
    expected = dedup_report.get("label_conflict_rows_kept", 0)
    actual = int(final_df[COL_LABEL_CONFLICT_FLAG].sum())
    return _result(
        "7-2 label_conflict_flag_preserved",
        actual == expected,
        {"expected": expected, "actual": actual},
    )


def check_invalid_negative_duration_preserved(final_df: pd.DataFrame, clipping_report: dict) -> dict:
    expected = clipping_report.get("invalid_negative_duration_rows", 0)
    actual = int(final_df[COL_INVALID_NEG_DURATION_FLAG].sum())
    return _result(
        "7-2b invalid_negative_duration_flag_preserved",
        actual == expected,
        {"expected": expected, "actual": actual},
    )


def check_destination_port_separated(final_df: pd.DataFrame, reserved_df: pd.DataFrame) -> dict:
    not_in_final = COL_DST_PORT not in final_df.columns
    in_reserved = COL_DST_PORT in reserved_df.columns
    return _result(
        "7-5 destination_port_separated",
        not_in_final and in_reserved,
        {"in_final": not not_in_final, "in_reserved": in_reserved},
    )


def check_manifest_no_download_date(manifest: dict) -> dict:
    absent = "original_download_date" not in manifest
    return _result("7-6 manifest_no_download_date", absent, {"keys": list(manifest.keys())})


def run_all(
    *,
    group_index_df: pd.DataFrame,
    flow_df: pd.DataFrame,
    final_df: pd.DataFrame,
    reserved_df: pd.DataFrame,
    manifest: dict,
    dedup_report: dict,
    clipping_report: dict,
    loao_target_labels: list[str],
) -> tuple[list[dict], bool]:
    results = [
        check_group_split_exclusivity(group_index_df),
        check_row_level_train_calib_exclusivity(flow_df),
        check_split_skew(flow_df),
        check_loao_target_absent_from_train(flow_df, loao_target_labels),
        check_no_exact_duplicates(final_df),
        check_label_conflict_preserved(final_df, dedup_report),
        check_invalid_negative_duration_preserved(final_df, clipping_report),
        check_destination_port_separated(final_df, reserved_df),
        check_manifest_no_download_date(manifest),
    ]
    overall_passed = all(r["passed"] for r in results if r["level"] == "error")
    return results, overall_passed
