from __future__ import annotations

import pandas as pd

from cicids_prep.column_pruning import apply_column_pruning, find_constant_and_duplicate_columns


def _df():
    # train: ConstFeature 전부 1 (상수), DupA==DupB (완전 동일)
    # calib/test: 일부러 값을 다르게 둬서 "train만 참조"를 증명한다.
    return pd.DataFrame(
        {
            "day": ["monday"] * 6,
            "id": range(1, 7),
            "row_uid": [f"monday_{i}" for i in range(1, 7)],
            "group_id": [f"g{i}" for i in range(6)],
            "split": ["train", "train", "train", "calib", "calib", "test"],
            "original_split": ["train", "train", "train", "calib", "calib", "test"],
            "attack_label": ["BENIGN"] * 6,
            "Label": ["BENIGN"] * 6,
            "label_conflict_flag": [False] * 6,
            "invalid_negative_duration_flag": [False] * 6,
            "Timestamp": pd.date_range("2017-07-03", periods=6, freq="min"),
            "Flow ID": ["f"] * 6,
            "Src IP": ["1.1.1.1"] * 6,
            "Dst IP": ["2.2.2.2"] * 6,
            "ConstFeature": [1, 1, 1, 999, 999, 999],
            "DupA": [1, 2, 3, 10, 20, 30],
            "DupB": [1, 2, 3, 99, 98, 97],
        }
    )


def test_constant_column_detected_from_train_only():
    df = _df()
    decisions = find_constant_and_duplicate_columns(df)

    assert "ConstFeature" in decisions["constant_columns_dropped"]


def test_duplicate_pair_detected_from_train_only():
    df = _df()
    decisions = find_constant_and_duplicate_columns(df)

    pairs = decisions["duplicate_column_pairs"]
    assert any(p["kept"] == "DupA" and p["dropped"] == "DupB" for p in pairs)


def test_changing_calib_test_values_does_not_change_decision():
    df = _df()
    baseline = find_constant_and_duplicate_columns(df)

    df.loc[df["split"] != "train", "ConstFeature"] = -12345
    df.loc[df["split"] != "train", "DupB"] = -12345

    changed = find_constant_and_duplicate_columns(df)

    assert changed["columns_dropped"] == baseline["columns_dropped"]


def test_apply_column_pruning_drops_columns():
    df = _df()
    decisions = find_constant_and_duplicate_columns(df)

    pruned = apply_column_pruning(df, decisions)

    assert "ConstFeature" not in pruned.columns
    assert "DupB" not in pruned.columns
    assert "DupA" in pruned.columns
