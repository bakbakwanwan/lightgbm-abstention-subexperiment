from __future__ import annotations

import pandas as pd

from cicids_prep.dedup import process_duplicates


def test_exact_duplicate_removed_to_one(make_raw_df):
    df = make_raw_df(
        [
            {},
            {},  # id/day/row_uid만 다르고 나머지 전부 같음 -> 완전일치
        ]
    )
    result, report = process_duplicates(df)

    assert len(result) == 1
    assert report["exact_duplicate_removed"] == 1


def test_relaxed_duplicate_same_label_removed_to_one(make_raw_df):
    df = make_raw_df(
        [
            {"Feature A": 1.0},
            {"Feature A": 2.0},  # 5-tuple+timestamp 같음, feature 다름, Label 같음
        ]
    )
    result, report = process_duplicates(df)

    assert len(result) == 1
    assert report["exact_duplicate_removed"] == 0
    assert report["relaxed_same_label_removed"] == 1


def test_relaxed_duplicate_label_conflict_kept_and_flagged(make_raw_df):
    df = make_raw_df(
        [
            {"Feature A": 1.0, "Label": "BENIGN"},
            {"Feature A": 2.0, "Label": "DoS Hulk"},  # 5-tuple+timestamp 같음, Label 다름
        ]
    )
    result, report = process_duplicates(df)

    assert len(result) == 2
    assert report["relaxed_same_label_removed"] == 0
    assert report["label_conflict_rows_kept"] == 2
    assert result["label_conflict_flag"].all()


def test_row_uid_unique_across_days(make_raw_df):
    df = make_raw_df(
        [
            {"day": "monday", "Src IP": "1.1.1.1"},
            {"day": "tuesday", "Src IP": "2.2.2.2"},
        ]
    )
    # 두 요일 모두 id=1로 시작하므로 row_uid가 없으면 충돌한다.
    df.loc[0, "id"] = 1
    df.loc[1, "id"] = 1
    df["row_uid"] = df["day"].astype(str) + "_" + df["id"].astype(str)

    assert df["row_uid"].nunique() == 2
