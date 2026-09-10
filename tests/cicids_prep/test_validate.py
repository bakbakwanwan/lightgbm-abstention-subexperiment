from __future__ import annotations

import pandas as pd

from cicids_prep import validate


def _group_index_df(overlap: bool = False):
    if overlap:
        # g1이 train과 test 양쪽에 존재 -> 6-1 fail 이어야 함
        return pd.DataFrame(
            {
                "group_id": ["g1", "g1", "g2"],
                "day": ["monday"] * 3,
                "attack_label": ["BENIGN"] * 3,
                "split": ["train", "test", "calib"],
            }
        )
    return pd.DataFrame(
        {
            "group_id": ["g1", "g2", "g3"],
            "day": ["monday"] * 3,
            "attack_label": ["BENIGN"] * 3,
            "split": ["train", "calib", "test"],
        }
    )


def test_group_split_exclusivity_fails_on_overlap():
    result = validate.check_group_split_exclusivity(_group_index_df(overlap=True))
    assert result["passed"] is False


def test_group_split_exclusivity_passes_without_overlap():
    result = validate.check_group_split_exclusivity(_group_index_df(overlap=False))
    assert result["passed"] is True


def test_label_conflict_preserved_detects_mismatch():
    final_df = pd.DataFrame({"label_conflict_flag": [True, False, False]})
    result = validate.check_label_conflict_preserved(final_df, {"label_conflict_rows_kept": 2})
    assert result["passed"] is False  # report는 2건인데 실제로는 1건만 남음


def test_label_conflict_preserved_passes_when_matching():
    final_df = pd.DataFrame({"label_conflict_flag": [True, True, False]})
    result = validate.check_label_conflict_preserved(final_df, {"label_conflict_rows_kept": 2})
    assert result["passed"] is True


def test_manifest_no_download_date_fails_if_present():
    result = validate.check_manifest_no_download_date({"original_download_date": "2017-07-03"})
    assert result["passed"] is False


def test_destination_port_separated_checks_both_sides():
    final_df = pd.DataFrame({"Feature A": [1]})
    reserved_df = pd.DataFrame({"row_uid": ["a"], "Dst Port": [80]})
    result = validate.check_destination_port_separated(final_df, reserved_df)
    assert result["passed"] is True
