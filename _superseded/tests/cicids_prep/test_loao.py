from __future__ import annotations

import pandas as pd

from cicids_prep.loao import apply_loao_mask


def _df():
    return pd.DataFrame(
        {
            "attack_label": ["BENIGN", "DoS Hulk", "PortScan"],
            "split": ["train", "train", "calib"],
            "original_split": ["train", "train", "calib"],
        }
    )


def test_loao_masks_target_labels_in_train_and_calib():
    df = _df()
    result = apply_loao_mask(df, ["DoS Hulk"])

    assert result.loc[result["attack_label"] == "DoS Hulk", "split"].iloc[0] == "test"
    assert result.loc[result["attack_label"] == "BENIGN", "split"].iloc[0] == "train"


def test_repeated_calls_always_reset_from_original_split():
    df = _df()
    once = apply_loao_mask(df, ["DoS Hulk"])
    twice = apply_loao_mask(once, ["PortScan"])  # 다른 대상으로 재호출

    # DoS Hulk는 두 번째 호출에서 대상이 아니므로 original_split(train)으로 되돌아가야 한다
    assert twice.loc[twice["attack_label"] == "DoS Hulk", "split"].iloc[0] == "train"
    assert twice.loc[twice["attack_label"] == "PortScan", "split"].iloc[0] == "test"


def test_empty_target_list_is_noop():
    df = _df()
    result = apply_loao_mask(df, [])

    assert (result["split"] == df["original_split"]).all()
