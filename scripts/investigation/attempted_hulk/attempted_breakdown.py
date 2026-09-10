"""작업 2 — Attempted 사유 구분 가능성 판정 (지시서 3장, 최우선).

이 모듈은 수치만 계산한다. A/B/C 판정 문구는 report.md 작성 시 이 수치를
근거로 사람이(이 경우 작업을 수행하는 Claude Code가) 판단해 적는다 —
코드에 판정 임계값을 하드코딩하지 않는다.
"""

from __future__ import annotations

import re

import pandas as pd

from cicids_prep.columns import COL_LABEL

ATTEMPTED_RE = re.compile(r"attempted", re.IGNORECASE)


def attempted_mask(df: pd.DataFrame, label_col: str = COL_LABEL) -> pd.Series:
    return df[label_col].str.contains(ATTEMPTED_RE, na=False)


def category_value_counts(df: pd.DataFrame, category_col: str) -> pd.DataFrame:
    return (
        df[category_col]
        .value_counts(dropna=False)
        .rename_axis(category_col)
        .reset_index(name="n_rows")
    )


def consistency_check(df: pd.DataFrame, category_col: str, label_col: str = COL_LABEL) -> dict:
    """Label의 Attempted 여부와 category_col 값이 얼마나 정합적인지 확인.

    비-Attempted 행에서 나타나는 category_col 고유값을 '기본값(sentinel) 후보'로
    보고, Attempted 여부 boolean과 (category != sentinel) boolean이 얼마나
    일치하는지를 계산한다. sentinel이 둘 이상이면 그 사실 자체를 반환한다
    (임의로 하나를 고르지 않는다).
    """
    a_mask = attempted_mask(df, label_col)
    non_attempted_categories = sorted(df.loc[~a_mask, category_col].dropna().unique().tolist())

    result = {
        "n_rows": int(len(df)),
        "n_attempted_rows": int(a_mask.sum()),
        "non_attempted_category_values": non_attempted_categories,
        "sentinel_ambiguous": len(non_attempted_categories) != 1,
    }

    if len(non_attempted_categories) == 1:
        sentinel = non_attempted_categories[0]
        category_present = df[category_col] != sentinel
        mismatch_mask = a_mask != category_present
        result["sentinel_value"] = sentinel
        result["n_mismatch"] = int(mismatch_mask.sum())
        result["mismatch_examples"] = (
            df.loc[mismatch_mask, [label_col, category_col]]
            .head(20)
            .to_dict(orient="records")
        )
    else:
        # sentinel이 여러 개면 attempted 쪽 category 고유값과 비교만 제공
        attempted_categories = sorted(df.loc[a_mask, category_col].dropna().unique().tolist())
        result["attempted_category_values"] = attempted_categories
        overlap = sorted(set(attempted_categories) & set(non_attempted_categories))
        result["overlap_categories_between_attempted_and_non"] = overlap

    return result


def label_category_crosstab(df: pd.DataFrame, category_col: str, label_col: str = COL_LABEL) -> pd.DataFrame:
    return (
        df.groupby([label_col, category_col]).size().rename("n_rows").reset_index()
    )
