from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ExperimentConfig:
    repo_root: Path
    raw: dict[str, Any]

    def path(self, section: str, key: str) -> Path:
        return (self.repo_root / self.raw[section][key]).resolve()

    @property
    def exp_id(self) -> str:
        return str(self.raw["experiment"]["id"])

    @property
    def output_dir(self) -> Path:
        return self.path("experiment", "output_dir")


def load_config(path: Path, repo_root: Path) -> ExperimentConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    required = {"experiment", "inputs", "analysis", "training", "execution_guard"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError(f"Config top-level keys must be exactly {sorted(required)}")
    if payload["experiment"]["id"] != "EXP-007":
        raise ValueError("This spec requires experiment.id=EXP-007")
    candidates = payload["training"]["candidates"]
    ids = [item["candidate_id"] for item in candidates]
    if ids != [f"C{i:02d}" for i in range(1, 9)]:
        raise ValueError("Candidates must be C01..C08 in order")
    expected_grid = [
        (31, 20, 0.0), (31, 20, 1.0), (31, 200, 0.0), (31, 200, 1.0),
        (63, 20, 0.0), (63, 20, 1.0), (63, 200, 0.0), (63, 200, 1.0),
    ]
    actual_grid = [(int(x["num_leaves"]), int(x["min_data_in_leaf"]), float(x["lambda_l2"])) for x in candidates]
    if actual_grid != expected_grid:
        raise ValueError("Candidate grid differs from D-006")
    rates = [float(x) for x in payload["analysis"]["target_abstention_rates"]]
    if rates != [0.01, 0.02, 0.05, 0.10]:
        raise ValueError("target_abstention_rates must be 0.01/0.02/0.05/0.10")
    training = payload["training"]
    if (int(training["num_boost_round"]), int(training["stopping_rounds"]), float(training["min_delta"])) != (3000, 100, 1e-6):
        raise ValueError("Early-stopping settings differ from D-006")
    if float(payload["analysis"]["decision_threshold"]) != 0.5 or int(payload["analysis"]["seed"]) != 42:
        raise ValueError("Decision threshold and seed must match D-006")
    return ExperimentConfig(repo_root.resolve(), payload)
