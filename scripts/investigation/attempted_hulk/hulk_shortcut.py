"""작업 3 — DoS Hulk shortcut 실측 (지시서 4장)."""

from __future__ import annotations

import re

import pandas as pd

from cicids_prep.columns import COL_LABEL

HULK_RE = re.compile(r"hulk", re.IGNORECASE)
SHORTCUT_VALUES = [11595, 23190, 11606, 23201]


def hulk_mask(df: pd.DataFrame, label_col: str = COL_LABEL) -> pd.Series:
    return df[label_col].str.contains(HULK_RE, na=False)


def value_occurrences(df: pd.DataFrame, value_col: str, label_col: str = COL_LABEL) -> dict:
    """4-3-1,2,4: 4개 값 각각의 전체 출현 행수, Hulk 여부, BENIGN 여부."""
    out = {}
    for v in SHORTCUT_VALUES:
        sub = df[df[value_col] == v]
        h_mask = hulk_mask(sub, label_col)
        out[str(v)] = {
            "total_rows": int(len(sub)),
            "hulk_rows": int(h_mask.sum()),
            "non_hulk_rows": int((~h_mask).sum()),
            "benign_rows": int((sub[label_col] == "BENIGN").sum()),
            "non_hulk_non_benign_labels": sorted(
                sub.loc[(~h_mask) & (sub[label_col] != "BENIGN"), label_col].unique().tolist()
            ),
        }
    return out


def hulk_not_in_shortcut(df: pd.DataFrame, value_col: str, label_col: str = COL_LABEL) -> dict:
    """4-3-3: Hulk 계열 전체 행 중 4개 값에 해당하지 않는 행 수."""
    h_mask = hulk_mask(df, label_col)
    hulk_df = df[h_mask]
    in_values = hulk_df[value_col].isin(SHORTCUT_VALUES)
    return {
        "n_hulk_total": int(len(hulk_df)),
        "n_hulk_in_shortcut_values": int(in_values.sum()),
        "n_hulk_not_in_shortcut_values": int((~in_values).sum()),
    }


def hulk_value_distribution(df: pd.DataFrame, value_col: str, label_col: str = COL_LABEL, top_n: int = 20) -> dict:
    """4-4: Hulk 계열 행에서 value_col 고유값 분포 (상위 top_n, 누적비율)."""
    hulk_df = df[hulk_mask(df, label_col)]
    n_total = len(hulk_df)
    vc = hulk_df[value_col].value_counts()
    top = vc.head(top_n)
    return {
        "n_hulk_total": int(n_total),
        "n_unique_values": int(vc.shape[0]),
        "top_values": [
            {"value": (v if not pd.isna(v) else None), "n_rows": int(c), "cum_ratio": None}
            for v, c in top.items()
        ],
        "top_n_cumulative_ratio": float(top.sum() / n_total) if n_total else None,
    }


def scan_single_column_shortcuts(
    df: pd.DataFrame,
    numeric_cols: list[str],
    label_col: str = COL_LABEL,
    coverage_threshold: float = 0.9,
    max_uniques_hint: int = 10,
) -> pd.DataFrame:
    """4-5: 라벨별로, 상위 10개 고유값이 행의 90% 이상을 덮는 컬럼을 스캔.

    우선순위 판단용 사전 스캔이며 정식 feature ablation의 대체물이 아니다.
    """
    rows = []
    for label, sub in df.groupby(label_col):
        n = len(sub)
        if n == 0:
            continue
        for col in numeric_cols:
            vc = sub[col].value_counts(dropna=False)
            top10 = vc.head(max_uniques_hint)
            coverage = float(top10.sum()) / n
            if coverage >= coverage_threshold:
                rows.append(
                    {
                        "label": label,
                        "column": col,
                        "n_rows_label": int(n),
                        "n_unique_values": int(vc.shape[0]),
                        "top10_coverage": coverage,
                    }
                )
    return pd.DataFrame(rows)
