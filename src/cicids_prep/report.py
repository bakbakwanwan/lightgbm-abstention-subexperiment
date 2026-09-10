"""분할 요약 리포트 (split_protocol_proposal.md 3-3)."""

from __future__ import annotations

import pandas as pd

from .columns import COL_ATTACK_LABEL, COL_DAY, COL_GROUP_ID, COL_N_FLOWS_IN_GROUP, COL_SPLIT


def build_summary_report(group_index_df: pd.DataFrame, excluded_labels: list[dict]) -> pd.DataFrame:
    pivot = (
        group_index_df.groupby([COL_DAY, COL_ATTACK_LABEL, COL_SPLIT])
        .agg(n_groups=(COL_GROUP_ID, "size"), n_flows=(COL_N_FLOWS_IN_GROUP, "sum"))
        .reset_index()
    )
    excluded_set = {(e["day"], e["attack_label"]) for e in excluded_labels}
    pivot["below_min_group_count"] = pivot.apply(
        lambda r: (r[COL_DAY], r[COL_ATTACK_LABEL]) in excluded_set, axis=1
    )
    return pivot
