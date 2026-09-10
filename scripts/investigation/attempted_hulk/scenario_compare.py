"""작업 4/5 — 제외 시나리오별 잔존 공격 다양성 집계 (지시서 5장).

실제 필터링은 메모리 상에서만 수행하고 파일로 쓰지 않는다 (지시서 5-1).
그룹키 생성·커트라인 판정은 cicids_prep.grouping / cicids_prep.splitting을
함수 호출로 재사용한다 (지시서 5-3) — 이 파이프라인은 이미 두 함수가
순수 함수로 분리되어 있어 재사용 불가 상황이 아니다.
"""

from __future__ import annotations

import pandas as pd

from cicids_prep import grouping, splitting
from cicids_prep.columns import COL_ATTACK_LABEL, COL_GROUP_ID, COL_LABEL


def prepare_group_id(df: pd.DataFrame, bucket_seconds: int) -> pd.DataFrame:
    """attack_label·group_id를 한 번만 계산해 재사용할 수 있게 부여한다.

    group_id는 (src_ip, dst_ip, attack_label, bucket)에만 의존하므로, 이후
    시나리오별로 행을 필터링해도 남은 행의 group_id는 그대로 유효하다 —
    시나리오마다 다시 계산할 필요가 없다.
    """
    df = grouping.add_attack_label(df)
    df[COL_GROUP_ID] = grouping.compute_group_id(df, bucket_seconds)
    return df


def build_scenario_masks(
    df: pd.DataFrame,
    hulk_family_labels: list[str],
    attempted_labels: list[str],
    label_col: str = COL_LABEL,
    category_col: str | None = None,
    target_reason_codes: list | None = None,
) -> dict[str, pd.Series]:
    hulk_mask = df[label_col].isin(hulk_family_labels)
    attempted_mask = df[label_col].isin(attempted_labels)

    s0 = pd.Series(True, index=df.index)
    s1 = ~hulk_mask
    s3 = s1 & ~attempted_mask
    # S4는 S1과 동일 집합이다: S1이 이미 Attempted 행을 제거하지 않고
    # "비-BENIGN=공격"으로 집계하는 관례를 쓰므로, "Attempted 전량을 공격으로
    # 채택"은 행 집합을 바꾸지 않는다. 별도 표기는 report.md에서 명시한다.
    s4 = s1

    scenarios = {"S0": s0, "S1": s1, "S3": s3, "S4": s4}

    if category_col is not None and target_reason_codes is not None:
        keep_attempted = attempted_mask & df[category_col].isin(target_reason_codes)
        s2 = s1 & (~attempted_mask | keep_attempted)
        scenarios["S2"] = s2

    return scenarios


def scenario_row_summary(df: pd.DataFrame, mask: pd.Series, label_col: str = COL_LABEL) -> dict:
    sub = df[mask]
    total = int(len(sub))
    benign = int((sub[label_col] == "BENIGN").sum())
    per_label = (
        sub[label_col].value_counts().rename("n_rows").reset_index()
        .rename(columns={"index": label_col})
    )
    return {
        "total_rows": total,
        "benign_rows": benign,
        "attack_rows": total - benign,
        "per_label": per_label,
    }


def labels_dropped_to_zero(baseline_labels: list[str], per_label_df: pd.DataFrame, label_col: str = COL_LABEL) -> list[str]:
    present = set(per_label_df[label_col])
    return sorted(set(baseline_labels) - present)


def compute_below_min_group_count(
    df_with_group_id: pd.DataFrame,
    split_ratios: dict,
    min_group_count_for_split: int,
) -> tuple[pd.DataFrame, list[dict]]:
    """splitting.assign_split을 그대로 재사용해 below_min_group_count 목록을 얻는다."""
    group_index_df = grouping.build_group_index(df_with_group_id)
    group_index_df, excluded = splitting.assign_split(
        group_index_df, split_ratios, min_group_count_for_split
    )
    return group_index_df, excluded


def n_attack_labels_remaining(per_label_df: pd.DataFrame, label_col: str = COL_LABEL) -> int:
    return int((per_label_df[label_col] != "BENIGN").sum())
