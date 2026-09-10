"""작업 1 — 라벨 인벤토리 (지시서 2장)."""

from __future__ import annotations

import re

import pandas as pd

from cicids_prep.columns import COL_DAY, COL_LABEL, COL_SPLIT

ATTEMPTED_RE = re.compile(r"attempted", re.IGNORECASE)


def label_counts(raw_df: pd.DataFrame) -> pd.DataFrame:
    return (
        raw_df[COL_LABEL]
        .value_counts(dropna=False)
        .rename_axis(COL_LABEL)
        .reset_index(name="n_rows")
    )


def label_by_day(raw_df: pd.DataFrame) -> pd.DataFrame:
    return (
        raw_df.groupby([COL_LABEL, COL_DAY]).size().rename("n_rows").reset_index()
    )


def label_by_split(final_df: pd.DataFrame) -> pd.DataFrame:
    return (
        final_df.groupby([COL_LABEL, COL_SPLIT]).size().rename("n_rows").reset_index()
    )


def attempted_labels(raw_df: pd.DataFrame) -> list[str]:
    labels = raw_df[COL_LABEL].dropna().unique().tolist()
    return sorted(l for l in labels if ATTEMPTED_RE.search(l))


def attempted_naming_patterns(attempted: list[str]) -> dict:
    patterns = {}
    for l in attempted:
        patterns[l] = {
            "ends_with_dash_attempted": bool(re.search(r"-\s*Attempted\s*$", l)),
            "has_double_space": "  " in l,
            "n_dash_segments": l.count(" - ") + 1,
        }
    return patterns


def attempted_total_rows(raw_df: pd.DataFrame) -> int:
    mask = raw_df[COL_LABEL].str.contains(ATTEMPTED_RE, na=False)
    return int(mask.sum())


def build_label_inventory(raw_df: pd.DataFrame, final_df: pd.DataFrame | None) -> dict:
    attempted = attempted_labels(raw_df)
    result = {
        "n_unique_labels_raw": int(raw_df[COL_LABEL].nunique(dropna=False)),
        "unique_labels_raw": sorted(raw_df[COL_LABEL].dropna().unique().tolist()),
        "attempted_labels": attempted,
        "attempted_naming_patterns": attempted_naming_patterns(attempted),
        "attempted_total_rows_raw": attempted_total_rows(raw_df),
    }
    if final_df is not None:
        result["n_unique_labels_pipeline"] = int(final_df[COL_LABEL].nunique(dropna=False))
        result["attempted_total_rows_pipeline"] = attempted_total_rows(final_df)
    return result
