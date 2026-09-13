from __future__ import annotations

import numpy as np
import pandas as pd

from cicids_prep.clipping import clip_infinities


def _df():
    rows = [
        # train: 정상 유한값 (percentile/lower bound 계산용)
        {"split": "train", "Flow Duration": 100.0, "RateFeature": 10.0},
        {"split": "train", "Flow Duration": 100.0, "RateFeature": 20.0},
        {"split": "train", "Flow Duration": 100.0, "RateFeature": 30.0},
        {"split": "train", "Flow Duration": 100.0, "RateFeature": -5.0},
        {"split": "train", "Flow Duration": 100.0, "RateFeature": -10.0},
        # test: +inf -> 상한 클리핑 대상 (다른 split이어도 동일 상한 적용)
        {"split": "test", "Flow Duration": 100.0, "RateFeature": np.inf},
        # test: Flow Duration<0 + -inf -> invalid_negative_duration_flag, 클리핑 안 함
        {"split": "test", "Flow Duration": -1.0, "RateFeature": -np.inf},
        # test: Flow Duration==0 + -inf -> 별도 계산된 하한으로 클리핑
        {"split": "test", "Flow Duration": 0.0, "RateFeature": -np.inf},
    ]
    df = pd.DataFrame(rows)
    df["day"] = "monday"
    df["id"] = range(1, len(df) + 1)
    df["row_uid"] = "monday_" + df["id"].astype(str)
    df["group_id"] = [f"g{i}" for i in range(len(df))]
    df["original_split"] = df["split"]
    df["attack_label"] = "BENIGN"
    df["Label"] = "BENIGN"
    df["label_conflict_flag"] = False
    df["Timestamp"] = pd.date_range("2017-07-03", periods=len(df), freq="min")
    df["Flow ID"] = "f"
    df["Src IP"] = "1.1.1.1"
    df["Dst IP"] = "2.2.2.2"
    return df


def _expected_bounds(percentile=99.9, multiplier=3.0):
    train_vals = pd.Series([10.0, 20.0, 30.0, -5.0, -10.0])
    upper = float(train_vals.quantile(percentile / 100) * multiplier)
    lower = float(train_vals.quantile(1 - percentile / 100) * multiplier)
    return upper, lower


def test_positive_infinity_clipped_to_train_based_upper_bound():
    df = _df()
    result, report = clip_infinities(df)

    upper, _ = _expected_bounds()
    pos_inf_row = result.loc[(result["split"] == "test") & (result["Flow Duration"] == 100.0)]
    assert pos_inf_row["RateFeature"].iloc[0] == upper


def test_negative_duration_row_flagged_not_deleted_not_clipped():
    df = _df()
    result, report = clip_infinities(df)

    neg_dur_row = result.loc[result["Flow Duration"] == -1.0]
    assert len(neg_dur_row) == 1  # 삭제되지 않음
    assert neg_dur_row["invalid_negative_duration_flag"].iloc[0] == True  # noqa: E712
    assert neg_dur_row["RateFeature"].iloc[0] == -np.inf  # 클리핑되지 않음
    assert report["invalid_negative_duration_rows"] == 1


def test_zero_duration_negative_infinity_clipped_to_separate_lower_bound():
    df = _df()
    result, report = clip_infinities(df)

    _, lower = _expected_bounds()
    zero_dur_row = result.loc[result["Flow Duration"] == 0.0]
    assert zero_dur_row["RateFeature"].iloc[0] == lower
    assert zero_dur_row["invalid_negative_duration_flag"].iloc[0] == False  # noqa: E712
    assert report["zero_duration_negative_infinity_rows"] == 1


def test_bounds_computed_from_train_only_not_calib_test():
    df = _df()
    upper, lower = _expected_bounds()

    # calib/test의 유한값을 극단적으로 바꿔도(inf 행은 그대로 유지) 상/하한은
    # train 값에서만 계산되므로 변하지 않아야 한다.
    df2 = _df()
    extreme_row = df2.iloc[0:1].copy()
    extreme_row["split"] = "test"
    extreme_row["id"] = 999
    extreme_row["row_uid"] = "monday_999"
    extreme_row["Flow Duration"] = 100.0
    extreme_row["RateFeature"] = 999999.0
    df2 = pd.concat([df2, extreme_row], ignore_index=True)

    result2, _ = clip_infinities(df2)

    pos_inf_row = result2.loc[(result2["split"] == "test") & (result2["Flow Duration"] == 100.0) & (result2["RateFeature"] != 999999.0)]
    assert pos_inf_row["RateFeature"].iloc[0] == upper
