from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def make_raw_df():
    """합성 CICIDS 스타일 DataFrame 생성기. 필요한 컬럼만 최소로 갖춘다."""

    def _make(rows: list[dict]) -> pd.DataFrame:
        base_cols = {
            "id": None,
            "day": "monday",
            "Flow ID": "fid",
            "Src IP": "10.0.0.1",
            "Src Port": 1234,
            "Dst IP": "10.0.0.2",
            "Dst Port": 80,
            "Protocol": 6,
            "Timestamp": pd.Timestamp("2017-07-03 12:00:00"),
            "Flow Duration": 100.0,
            "Feature A": 1.0,
            "Feature B": 1.0,
            "Label": "BENIGN",
            "Attempted Category": -1,
        }
        records = []
        for i, override in enumerate(rows, start=1):
            rec = dict(base_cols)
            rec["id"] = i
            rec.update(override)
            records.append(rec)
        df = pd.DataFrame.from_records(records)
        df["row_uid"] = df["day"].astype(str) + "_" + df["id"].astype(str)
        return df

    return _make
