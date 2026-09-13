from __future__ import annotations

from cicids_prep.reserved_columns import split_off_destination_port


def test_destination_port_removed_from_main_and_preserved_in_reserved(make_raw_df):
    df = make_raw_df([{"Dst Port": 443}, {"Dst Port": 22}])

    main, reserved = split_off_destination_port(df)

    assert "Dst Port" not in main.columns
    assert "Dst Port" in reserved.columns
    assert set(reserved.columns) == {"row_uid", "Dst Port"}
    assert reserved.set_index("row_uid")["Dst Port"].to_dict() == {
        "monday_1": 443,
        "monday_2": 22,
    }
