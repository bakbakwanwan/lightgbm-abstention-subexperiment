from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "investigation"))

from class_overlap.analysis import (  # noqa: E402
    ScopeAccumulator,
    duplicate_hashes,
    feature_hash,
    map_protocol,
    process_candidate_bucket,
    rows_equal_to_first,
)


class AnalysisTests(unittest.TestCase):
    def test_protocol_mapping_is_categorical(self) -> None:
        mapped = map_protocol(pd.Series([6, 17, 1, 0], name="Protocol"))
        self.assertEqual(mapped.astype(str).tolist(), ["TCP", "UDP", "ICMP", "UNKNOWN"])
        self.assertEqual(str(mapped.dtype), "category")

    def test_unexpected_protocol_stops(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unexpected Protocol"):
            map_protocol(pd.Series([6, 99], name="Protocol"))

    def test_hash_detects_identical_rows_with_nan_and_infinity(self) -> None:
        frame = pd.DataFrame(
            {
                "Protocol": pd.Categorical(["TCP", "TCP", "UDP"]),
                "A": [np.nan, np.nan, np.inf],
                "B": [1.0, 1.0, 2.0],
            }
        )
        hashes = feature_hash(frame)
        self.assertEqual(duplicate_hashes(hashes).tolist(), [hashes[0]])
        self.assertTrue(rows_equal_to_first(frame.iloc[:2]).all())

    def test_exact_class_overlap_is_counted(self) -> None:
        frame = pd.DataFrame(
            {
                "Protocol": pd.Categorical(["TCP", "TCP", "UDP", "UDP"]),
                "Flow Bytes/s": [np.inf, np.inf, 3.0, 3.0],
                "_label": ["BENIGN", "Attack", "Attack", "Attack"],
                "_day": ["monday", "tuesday", "monday", "monday"],
                "_id": [1, 2, 3, 4],
                "_feature_hash": np.array([10, 10, 20, 20], dtype=np.uint64),
                "_target": [True, True, True, True],
            }
        )
        target = ScopeAccumulator("target")
        full = ScopeAccumulator("full")
        collisions = process_candidate_bucket(
            frame, ["Protocol", "Flow Bytes/s"], target, full
        )
        self.assertEqual(collisions, 0)
        self.assertEqual(target.duplicate_groups, 2)
        self.assertEqual(target.duplicate_rows, 4)
        self.assertEqual(target.label_conflict_groups, 1)
        self.assertEqual(target.label_conflict_rows, 2)
        self.assertEqual(target.cross_file_conflict_groups, 1)
        self.assertEqual(target.conflict_groups_with_infinite_flow_bytes, 1)

    def test_candidate_hash_collision_is_split_by_original_values(self) -> None:
        frame = pd.DataFrame(
            {
                "Protocol": pd.Categorical(["TCP", "TCP", "UDP", "UDP"]),
                "Flow Bytes/s": [1.0, 1.0, 2.0, 2.0],
                "_label": ["BENIGN", "BENIGN", "Attack", "Attack"],
                "_day": ["monday"] * 4,
                "_id": [1, 2, 3, 4],
                "_feature_hash": np.array([99, 99, 99, 99], dtype=np.uint64),
                "_target": [True] * 4,
            }
        )
        target = ScopeAccumulator("target")
        full = ScopeAccumulator("full")
        collisions = process_candidate_bucket(
            frame, ["Protocol", "Flow Bytes/s"], target, full
        )
        self.assertEqual(collisions, 1)
        self.assertEqual(target.duplicate_groups, 2)
        self.assertEqual(target.label_conflict_groups, 0)


if __name__ == "__main__":
    unittest.main()

