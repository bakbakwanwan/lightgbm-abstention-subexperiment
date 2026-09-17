from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from abstention_experiment.layer2_export import (
    PROMPT_FORBIDDEN_FIELDS,
    InputFeatureSchema,
    ThresholdSource,
    load_input_feature_schema,
    select_abstained_predictions,
    serialized_input_record,
    validate_schema_snapshot,
)


def _predictions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "method": ["group_seed42"] * 6,
            "day": ["monday", "monday", "tuesday", "tuesday", "wednesday", "friday"],
            "id": [1, 2, 3, 4, 5, 6],
            "observation_group": ["none", "none", "none", "attempted", "none", "none"],
            "split": ["test", "test", "train", "test", "test", "test"],
            "binary_label": [0, 1, 0, pd.NA, 1, 0],
            "p_attack": [0.40, 0.60, 0.10, 0.40, 0.01, 0.50],
            "confidence": [0.60, 0.60, 0.90, 0.60, 0.99, 0.50],
            "predicted_label": [0, 1, 0, 0, 0, 1],
            "is_error": [0, 0, 0, pd.NA, 1, 1],
        }
    )


def test_repository_layer2_schema_is_a_verified_whitelist_snapshot() -> None:
    root = Path(__file__).resolve().parents[2]
    schema = load_input_feature_schema(root / "configs/llm/e9_input_feature_schema.json")
    validate_schema_snapshot(schema, root)
    assert len(schema.features) == 59
    assert not (set(schema.features) & PROMPT_FORBIDDEN_FIELDS)


def test_selection_uses_only_test_target_rows_below_external_threshold() -> None:
    source = ThresholdSource("EXP-007", "group_seed42", 0.01, 0.60)
    selected, n_test = select_abstained_predictions(_predictions(), source)
    assert n_test == 4
    assert set(zip(selected["day"], selected["id"])) == {
        ("monday", 1),
        ("monday", 2),
        ("friday", 6),
    }


def test_sampling_is_stable_and_does_not_depend_on_labels_or_input_order() -> None:
    source = ThresholdSource("EXP-007", "group_seed42", 0.01, 0.99)
    first = _predictions()
    second = first.sample(frac=1.0, random_state=9).reset_index(drop=True)
    second["binary_label"] = [1, 0, 1, 0, 1, 0]
    second["is_error"] = [1, 1, 0, 0, 1, 0]
    selected_first, _ = select_abstained_predictions(first, source, sample_size=2)
    selected_second, _ = select_abstained_predictions(second, source, sample_size=2)
    assert list(zip(selected_first["day"], selected_first["id"])) == list(
        zip(selected_second["day"], selected_second["id"])
    )


def test_serialized_record_contains_only_index_and_feature_payload() -> None:
    schema = InputFeatureSchema(
        schema_version="test",
        source_whitelist_path="unused",
        source_whitelist_sha256="unused",
        features=("Protocol", "Flow Duration", "Flow Bytes/s"),
    )
    row = pd.Series(
        {
            "input_index": 7,
            "Protocol": "TCP",
            "Flow Duration": np.float64(4523.0),
            "Flow Bytes/s": np.nan,
            "binary_label": 1,
            "confidence": 0.51,
        }
    )
    record = serialized_input_record(row, schema)
    assert record == {
        "input_index": 7,
        "payload": {
            "flow_features": {
                "Protocol": "TCP",
                "Flow Duration": 4523.0,
                "Flow Bytes/s": None,
            }
        },
    }
    encoded = json.dumps(record, allow_nan=False)
    assert "binary_label" not in encoded
    assert "confidence" not in encoded
