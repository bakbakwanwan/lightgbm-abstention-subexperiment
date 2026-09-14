from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "investigation"))

from split_feasibility.analysis import (  # noqa: E402
    build_group_stratified_split,
    choose_conflict_test_groups,
    closest_prefix_selection,
    deterministic_stratified_row_split,
    row_random_leakage,
)


class SplitFeasibilityTests(unittest.TestCase):
    def test_closest_prefix_selection_hits_available_target(self) -> None:
        hashes = np.array([1, 2, 3, 4], dtype=np.uint64)
        sizes = np.array([2, 2, 1, 1])
        chosen = closest_prefix_selection(hashes, sizes, target_rows=3, seed=42)
        lookup = dict(zip(hashes.tolist(), sizes.tolist()))
        self.assertEqual(sum(lookup[int(value)] for value in chosen), 3)

    def test_conflict_groups_are_selected_whole(self) -> None:
        matrix = pd.DataFrame(
            {"BENIGN": [10, 0], "Attack": [2, 8]},
            index=pd.Index(np.array([10, 20], dtype=np.uint64), name="feature_hash"),
        )
        selected, details = choose_conflict_test_groups(matrix, 0.25)
        self.assertTrue(set(selected).issubset({10, 20}))
        self.assertEqual(details["candidate_subsets"], 4)

    def test_group_split_never_splits_hash(self) -> None:
        rows = pd.DataFrame(
            {
                "feature_hash": np.array([1, 2, 3, 4, 5, 6, 7], dtype=np.uint64),
                "Label": ["BENIGN", "BENIGN", "BENIGN", "Attack", "Attack", "BENIGN", "Attack"],
                "rows": [10, 10, 10, 5, 5, 2, 2],
            }
        )
        result = build_group_stratified_split(rows, 0.25, 42)
        self.assertEqual(len(result.test_hashes), len(np.unique(result.test_hashes)))
        self.assertTrue(set(result.test_hashes).issubset(set(rows.feature_hash)))

    def test_row_random_leakage_detects_same_and_opposite_labels(self) -> None:
        hashes = np.array([1, 1, 2, 2, 3], dtype=np.uint64)
        labels = np.array(["BENIGN", "BENIGN", "BENIGN", "Attack", "Attack"])
        test = np.array([False, True, False, True, True])
        result = row_random_leakage(hashes, labels, test)
        self.assertEqual(result["cross_split_feature_groups"], 2)
        self.assertEqual(result["test_rows_with_feature_seen_in_train"], 2)
        self.assertEqual(result["test_rows_with_same_original_label_in_train"], 1)
        self.assertEqual(result["test_rows_with_opposite_binary_label_in_train"], 1)

    def test_row_random_split_is_deterministic_and_stratified(self) -> None:
        labels = np.array(["A"] * 8 + ["B"] * 4)
        first = deterministic_stratified_row_split(labels, 0.25, 42)
        second = deterministic_stratified_row_split(labels, 0.25, 42)
        self.assertTrue(np.array_equal(first, second))
        self.assertEqual(int(first[:8].sum()), 2)
        self.assertEqual(int(first[8:].sum()), 1)


if __name__ == "__main__":
    unittest.main()

