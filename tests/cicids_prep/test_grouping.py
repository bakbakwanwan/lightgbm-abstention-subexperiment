from __future__ import annotations

import pandas as pd

from cicids_prep.grouping import add_attack_label, build_group_index, compute_group_id


def test_group_id_is_deterministic_across_calls(make_raw_df):
    df = make_raw_df([{}, {}])
    df = add_attack_label(df)

    g1 = compute_group_id(df, bucket_seconds=300)
    g2 = compute_group_id(df, bucket_seconds=300)

    assert list(g1) == list(g2)
    assert g1.nunique() == 1  # 두 행 모두 같은 src/dst/label/bucket


def test_group_id_differs_when_bucket_differs(make_raw_df):
    df = make_raw_df(
        [
            {"Timestamp": pd.Timestamp("2017-07-03 12:00:00")},
            {"Timestamp": pd.Timestamp("2017-07-03 13:00:00")},  # 다른 5분 버킷
        ]
    )
    df = add_attack_label(df)
    g = compute_group_id(df, bucket_seconds=300)

    assert g.iloc[0] != g.iloc[1]


def test_build_group_index_rep_time_and_count(make_raw_df):
    df = make_raw_df(
        [
            {"Timestamp": pd.Timestamp("2017-07-03 12:00:00")},
            {"Timestamp": pd.Timestamp("2017-07-03 12:01:00")},
        ]
    )
    df = add_attack_label(df)
    df["group_id"] = compute_group_id(df, bucket_seconds=300)

    idx = build_group_index(df)

    assert len(idx) == 1
    assert idx.loc[0, "n_flows_in_group"] == 2
    assert idx.loc[0, "rep_time"] == pd.Timestamp("2017-07-03 12:00:00")
