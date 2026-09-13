"""LOAO(leave-one-attack-out) 마스크 후처리 (split_protocol_proposal.md 4-7).

순수 함수다. 항상 original_split에서부터 다시 계산한다 — 직전 LOAO 결과 위에
누적하지 않는다. 그래야 loao_target_labels를 바꿔가며 여러 번 재실행해도
결과가 어긋나지 않는다. 그룹 인덱스 테이블·플로우 테이블 양쪽에 attack_label/
split/original_split 컬럼만 있으면 동일하게 쓸 수 있다.
"""

from __future__ import annotations

import pandas as pd

from .columns import COL_ATTACK_LABEL, COL_ORIGINAL_SPLIT, COL_SPLIT


def apply_loao_mask(df: pd.DataFrame, loao_target_labels: list[str]) -> pd.DataFrame:
    df = df.copy()
    df[COL_SPLIT] = df[COL_ORIGINAL_SPLIT]
    if not loao_target_labels:
        return df
    mask = df[COL_ATTACK_LABEL].isin(loao_target_labels) & df[COL_SPLIT].isin(
        ["train", "calib"]
    )
    df.loc[mask, COL_SPLIT] = "test"
    return df
