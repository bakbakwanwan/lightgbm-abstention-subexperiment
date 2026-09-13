"""Infinity 처리 (stage1_briefing.md 1-4, 1-8).

+Infinity: train split 유한값의 99.9 퍼센타일 × 3을 상한으로 클리핑
(stage1_briefing.md에 명시). calib/test에도 동일 값 적용 — 반드시 train만 참조해
계산한다(누수 방지, 근거는 stage1_briefing.md 3-4).

-Infinity: stage1_briefing.md가 명시하지 않은 부분이라 사용자 지시로 확정함.
Flow Duration 부호로 원인을 갈라 처리한다 — 양수 쪽 상한에 부호만 뒤집어
재사용하지 않는다.
  - Flow Duration < 0 인 행: 데이터 자체가 오염된 것으로 보고 삭제하지 않고
    invalid_negative_duration_flag=True로 표시·보존한다. 이 행은 클리핑 기준
    통계에서도 제외하고, 그 행의 -Infinity 값 자체도 클리핑하지 않는다(임의로
    지우면 버그 신호가 사라진다).
  - Flow Duration == 0(또는 -0.0)인 행: 정당한 제로-듀레이션 케이스이므로, train의
    실제 음수 방향 유한값 분포에서 별도로 하한을 계산해 적용한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .column_pruning import _prunable_columns
from .columns import COL_FLOW_DURATION, COL_INVALID_NEG_DURATION_FLAG, COL_SPLIT


def _numeric_prunable_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in _prunable_columns(df) if pd.api.types.is_numeric_dtype(df[c])]


def diagnose_negative_infinity(
    df: pd.DataFrame, numeric_cols: list[str]
) -> tuple[pd.Series, pd.Series]:
    has_neg_inf = (df[numeric_cols] == -np.inf).any(axis=1)
    duration_negative = df[COL_FLOW_DURATION] < 0
    duration_zero = df[COL_FLOW_DURATION] == 0
    invalid_negative_duration_flag = has_neg_inf & duration_negative
    zero_duration_neg_inf_mask = has_neg_inf & duration_zero
    return invalid_negative_duration_flag, zero_duration_neg_inf_mask


def compute_clip_bounds(
    df: pd.DataFrame,
    numeric_cols: list[str],
    zero_duration_neg_inf_mask: pd.Series,
    split_col: str = COL_SPLIT,
    percentile: float = 99.9,
    multiplier: float = 3.0,
) -> dict:
    train_df = df.loc[df[split_col] == "train"]
    bounds: dict[str, dict] = {}

    for col in numeric_cols:
        train_col = train_df[col]
        finite_train = train_col[np.isfinite(train_col)]
        if finite_train.empty:
            continue

        upper = None
        if np.isposinf(df[col]).any():
            upper = float(finite_train.quantile(percentile / 100) * multiplier)

        lower = None
        if zero_duration_neg_inf_mask.any() and (
            df.loc[zero_duration_neg_inf_mask, col] == -np.inf
        ).any():
            lower = float(finite_train.quantile(1 - percentile / 100) * multiplier)

        if upper is not None or lower is not None:
            bounds[col] = {"upper": upper, "lower": lower}

    return bounds


def apply_clipping(
    df: pd.DataFrame, bounds: dict, invalid_negative_duration_flag: pd.Series
) -> pd.DataFrame:
    df = df.copy()
    for col, b in bounds.items():
        if b["upper"] is not None:
            df[col] = df[col].where(df[col] != np.inf, b["upper"])
        if b["lower"] is not None:
            neg_inf_mask = df[col] == -np.inf
            clip_mask = neg_inf_mask & (~invalid_negative_duration_flag)
            df.loc[clip_mask, col] = b["lower"]
    return df


def clip_infinities(
    df: pd.DataFrame,
    split_col: str = COL_SPLIT,
    percentile: float = 99.9,
    multiplier: float = 3.0,
) -> tuple[pd.DataFrame, dict]:
    """1-4/1-8 전체 흐름: 진단 -> 상/하한 계산(train만) -> 적용. flag 컬럼을 부여한다."""
    numeric_cols = _numeric_prunable_columns(df)
    invalid_flag, zero_duration_mask = diagnose_negative_infinity(df, numeric_cols)

    df = df.copy()
    df[COL_INVALID_NEG_DURATION_FLAG] = invalid_flag

    bounds = compute_clip_bounds(df, numeric_cols, zero_duration_mask, split_col, percentile, multiplier)
    df = apply_clipping(df, bounds, invalid_flag)

    report = {
        "bounds": bounds,
        "invalid_negative_duration_rows": int(invalid_flag.sum()),
        "zero_duration_negative_infinity_rows": int(zero_duration_mask.sum()),
    }
    return df, report
