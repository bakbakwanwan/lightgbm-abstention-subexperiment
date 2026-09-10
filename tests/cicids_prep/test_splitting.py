from __future__ import annotations

import pandas as pd

from cicids_prep.splitting import assign_split


def _group_index(n: int, day: str = "monday", label: str = "BENIGN") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "group_id": [f"g{i}" for i in range(n)],
            "day": [day] * n,
            "attack_label": [label] * n,
            "rep_time": pd.date_range("2017-07-03 12:00:00", periods=n, freq="min"),
            "n_flows_in_group": [1] * n,
        }
    )


def test_ratio_boundary_60_20_20(make_raw_df):
    df = _group_index(10)
    result, excluded = assign_split(df, {"train": 0.6, "calib": 0.2, "test": 0.2}, min_group_count_for_split=1)

    counts = result["split"].value_counts()
    assert counts["train"] == 6
    assert counts["calib"] == 2
    assert counts["test"] == 2
    assert excluded == []
    assert (result["split"] == result["original_split"]).all()


def test_below_min_group_count_all_test_and_excluded(make_raw_df):
    df = _group_index(3, label="Heartbleed")
    result, excluded = assign_split(df, {"train": 0.6, "calib": 0.2, "test": 0.2}, min_group_count_for_split=10)

    assert (result["split"] == "test").all()
    assert excluded == [{"day": "monday", "attack_label": "Heartbleed", "n_groups": 3}]
