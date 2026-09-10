"""요일별 CICIDS2017 CSV 로드와 parquet 입출력."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .columns import COL_DAY, COL_ID, COL_ROW_UID, COL_TIMESTAMP, TIMESTAMP_FORMAT


def load_day_csvs(paths: dict[str, Path]) -> pd.DataFrame:
    """요일별 CSV를 로드하고 day·row_uid 컬럼을 부여해 병합한다.

    id 컬럼은 요일 파일마다 1부터 다시 시작해 전역 유일하지 않다
    (monday 1~371624, tuesday 1~322078, ... 확인됨). row_uid = f"{day}_{id}"로
    전역 유일 식별자를 만든다. 이 단계에서는 정렬·분할을 하지 않는다 (1단계 1번).
    """
    frames = []
    for day, path in paths.items():
        df = pd.read_csv(path)
        df.insert(0, COL_DAY, day)
        frames.append(df)
    merged = pd.concat(frames, ignore_index=True)
    merged[COL_TIMESTAMP] = pd.to_datetime(
        merged[COL_TIMESTAMP], format=TIMESTAMP_FORMAT
    )
    merged[COL_ROW_UID] = (
        merged[COL_DAY].astype(str) + "_" + merged[COL_ID].astype(str)
    )
    return merged


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def load_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)
