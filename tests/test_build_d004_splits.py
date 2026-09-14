from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from build_d004_splits import observation_group  # noqa: E402


class BuildD004SplitsTests(unittest.TestCase):
    def test_observation_groups_are_mutually_exclusive(self) -> None:
        labels = pd.Series(
            ["BENIGN", "Portscan", "DoS Hulk", "DoS Hulk - Attempted"],
            dtype="string",
        )
        self.assertEqual(
            observation_group(labels).tolist(),
            ["none", "none", "invalid_class", "attempted"],
        )


if __name__ == "__main__":
    unittest.main()

