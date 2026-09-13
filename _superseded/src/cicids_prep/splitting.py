"""요일×레이블 단위 커트라인 계산 및 split 라벨 부여 (split_protocol_proposal.md 4-4, 4-5)."""

from __future__ import annotations

import pandas as pd

from .columns import (
    COL_ATTACK_LABEL,
    COL_DAY,
    COL_ORIGINAL_SPLIT,
    COL_REP_TIME,
    COL_SPLIT,
)


def assign_split(
    group_index_df: pd.DataFrame,
    split_ratios: dict[str, float],
    min_group_count_for_split: int,
) -> tuple[pd.DataFrame, list[dict]]:
    df = group_index_df.copy()
    df[COL_SPLIT] = pd.Series([None] * len(df), index=df.index, dtype=object)
    excluded = []

    for (day, label), sub in df.groupby([COL_DAY, COL_ATTACK_LABEL]):
        sub_sorted = sub.sort_values(COL_REP_TIME)
        n = len(sub_sorted)
        if n < min_group_count_for_split:
            df.loc[sub_sorted.index, COL_SPLIT] = "test"
            excluded.append({"day": day, "attack_label": label, "n_groups": n})
            continue

        n_train = int(n * split_ratios["train"])
        n_calib = int(n * split_ratios["calib"])
        idx = sub_sorted.index
        df.loc[idx[:n_train], COL_SPLIT] = "train"
        df.loc[idx[n_train : n_train + n_calib], COL_SPLIT] = "calib"
        df.loc[idx[n_train + n_calib :], COL_SPLIT] = "test"

    df[COL_ORIGINAL_SPLIT] = df[COL_SPLIT]
    return df, excluded
