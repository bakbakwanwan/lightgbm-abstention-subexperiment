"""원본 CICIDS2017 요일별 CSV 로드 (조사 전용, cicids_prep.io 재사용).

원본 CSV 기준 통계는 반드시 이 로더가 만든 DataFrame에서 산출한다
(지시서 1-2: 파이프라인 산출물과 별도로 원본 기준을 독립 산출).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from cicids_prep.io import load_day_csvs

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]


def input_paths(input_dir: Path) -> dict[str, Path]:
    return {d: input_dir / f"{d}.csv" for d in DAYS}


def check_header_consistency(input_dir: Path) -> dict:
    """5개 파일 헤더가 동일한지 확인 (작업 2-3-3 겸 1-6 사전 점검)."""
    headers = {}
    for d, p in input_paths(input_dir).items():
        headers[d] = list(pd.read_csv(p, nrows=0).columns)
    reference_day = DAYS[0]
    reference = headers[reference_day]
    mismatches = {d: h for d, h in headers.items() if h != reference}
    return {
        "headers": headers,
        "reference_day": reference_day,
        "consistent": len(mismatches) == 0,
        "mismatches": mismatches,
    }


def load_raw_merged(input_dir: Path) -> pd.DataFrame:
    """원본 CSV 5개 병합. day/row_uid만 부여, dedup·정렬 없음."""
    return load_day_csvs(input_paths(input_dir))
