"""중복 플로우 검출·처리 (stage1_briefing.md 1-2, 1-7).

두 단계로 나눈다:
1. 완전일치: row_uid/id/day를 뺀 전체 컬럼이 동일한 행 -> 1건만 남기고 제거.
2. 완화기준(5-tuple+timestamp만 동일, 값은 다를 수 있음):
   - 남은 행의 Label이 전부 같으면 -> 1건만 남기고 제거.
   - Label이 갈리면 -> 삭제하지 않고 label_conflict_flag=True로 표시해 보존.
   (완전일치와 혼동하지 말 것 — 완전일치는 캡처/전처리 버그, 완화기준+라벨충돌은
   라벨링 로직 결함일 수 있어 사람이 검토해야 한다.)
"""

from __future__ import annotations

import pandas as pd

from .columns import COL_LABEL, COL_LABEL_CONFLICT_FLAG, RELAXED_DUP_KEY, SYNTHETIC_COLS


def remove_exact_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    compare_cols = [c for c in df.columns if c not in SYNTHETIC_COLS]
    dup_mask = df.duplicated(subset=compare_cols, keep="first")
    n_removed = int(dup_mask.sum())
    return df.loc[~dup_mask].reset_index(drop=True), n_removed


def handle_relaxed_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = df.copy()
    df[COL_LABEL_CONFLICT_FLAG] = False

    group_sizes = df.groupby(RELAXED_DUP_KEY)[COL_LABEL].transform("size")
    group_label_nunique = df.groupby(RELAXED_DUP_KEY)[COL_LABEL].transform("nunique")
    multi = group_sizes > 1
    same_label = multi & (group_label_nunique == 1)
    conflict = multi & (group_label_nunique > 1)

    df.loc[conflict, COL_LABEL_CONFLICT_FLAG] = True

    same_label_idx = df.index[same_label]
    same_label_df = df.loc[same_label_idx]
    dup_within_same_label = same_label_df.duplicated(subset=RELAXED_DUP_KEY, keep="first")
    drop_idx = same_label_idx[dup_within_same_label.to_numpy()]

    n_relaxed_same_label_removed = int(len(drop_idx))
    n_label_conflict_rows_kept = int(conflict.sum())

    result = df.drop(index=drop_idx).reset_index(drop=True)
    return result, {
        "relaxed_same_label_removed": n_relaxed_same_label_removed,
        "label_conflict_rows_kept": n_label_conflict_rows_kept,
    }


def process_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """1단계 2번: 완전일치 -> 완화기준 순으로 처리하고 리포트를 반환한다."""
    n_input = len(df)
    df, n_exact_removed = remove_exact_duplicates(df)
    df, relaxed_stats = handle_relaxed_duplicates(df)
    report = {
        "n_input_rows": n_input,
        "exact_duplicate_removed": n_exact_removed,
        **relaxed_stats,
        "n_output_rows": len(df),
    }
    return df, report
