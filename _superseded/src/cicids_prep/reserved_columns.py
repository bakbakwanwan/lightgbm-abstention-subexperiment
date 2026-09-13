"""Destination Port 분리·보존 (stage1_briefing.md 1-5).

기본 학습 테이블에서는 Destination Port를 제거하되, row_uid로 다시 조인할 수
있도록 원본값을 별도 테이블에 보존한다. IP/Flow ID/Timestamp는 여기서 다루지
않는다 — stage1_briefing이 명시적으로 확정한 누수 컬럼은 Destination Port뿐이다.
"""

from __future__ import annotations

import pandas as pd

from .columns import COL_DST_PORT, COL_ROW_UID


def split_off_destination_port(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    reserved = df[[COL_ROW_UID, COL_DST_PORT]].copy()
    main = df.drop(columns=[COL_DST_PORT])
    return main, reserved
