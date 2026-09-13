"""train split 기준 상수/완전동일 컬럼 판단·제거 (stage1_briefing.md 1-6).

calib/test 값이 컬럼 선택에 전혀 섞이지 않도록, 반드시 split=="train"인 행만
슬라이싱한 뒤 판단한다 (2단계 그룹 기반 분할과 동일한 누수 방지 논리, 근거는
docs/stage1_briefing.md 3-6). 식별자·부기(bookkeeping) 컬럼과, 이 파이프라인이
아직 손대지 않기로 확정한 누수 후보 컬럼(Flow ID/Src IP/Dst IP/Timestamp)은
가지치기 후보에서 제외한다.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

import pandas as pd

from .columns import (
    COL_ATTACK_LABEL,
    COL_FLOW_ID,
    COL_GROUP_ID,
    COL_INVALID_NEG_DURATION_FLAG,
    COL_LABEL,
    COL_LABEL_CONFLICT_FLAG,
    COL_ORIGINAL_SPLIT,
    COL_SPLIT,
    COL_SRC_IP,
    COL_DST_IP,
    COL_TIMESTAMP,
    SYNTHETIC_COLS,
)

_NON_PRUNABLE = set(SYNTHETIC_COLS) | {
    COL_GROUP_ID,
    COL_SPLIT,
    COL_ORIGINAL_SPLIT,
    COL_ATTACK_LABEL,
    COL_LABEL,
    COL_LABEL_CONFLICT_FLAG,
    COL_INVALID_NEG_DURATION_FLAG,
    COL_TIMESTAMP,
    COL_FLOW_ID,
    COL_SRC_IP,
    COL_DST_IP,
}


def _prunable_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in _NON_PRUNABLE]


def _column_content_hash(series: pd.Series) -> str:
    row_hashes = pd.util.hash_pandas_object(series, index=False).to_numpy()
    return hashlib.md5(row_hashes.tobytes()).hexdigest()


def find_constant_and_duplicate_columns(
    df: pd.DataFrame, split_col: str = COL_SPLIT
) -> dict:
    train_df = df.loc[df[split_col] == "train"]
    candidates = _prunable_columns(df)

    constant_columns = [
        c for c in candidates if train_df[c].nunique(dropna=False) <= 1
    ]
    remaining = [c for c in candidates if c not in constant_columns]

    hash_to_cols: dict[str, list[str]] = defaultdict(list)
    for c in remaining:
        hash_to_cols[_column_content_hash(train_df[c])].append(c)

    duplicate_pairs = []
    dropped_duplicates = []
    for cols in hash_to_cols.values():
        if len(cols) <= 1:
            continue
        keep = cols[0]
        for other in cols[1:]:
            if train_df[keep].equals(train_df[other]):
                duplicate_pairs.append({"kept": keep, "dropped": other})
                dropped_duplicates.append(other)

    return {
        "constant_columns_dropped": constant_columns,
        "duplicate_column_pairs": duplicate_pairs,
        "columns_dropped": constant_columns + dropped_duplicates,
    }


def apply_column_pruning(df: pd.DataFrame, decisions: dict) -> pd.DataFrame:
    return df.drop(columns=decisions["columns_dropped"])
