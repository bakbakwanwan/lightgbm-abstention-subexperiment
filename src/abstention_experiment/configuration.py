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
    exp_id = payload["experiment"]["id"]
    if exp_id == "EXP-007":
        _validate_exp007(payload)
    elif exp_id == "EXP-008":
        _validate_exp008(payload)
    else:
        raise ValueError(f"Unsupported experiment.id={exp_id}")
    return ExperimentConfig(repo_root.resolve(), payload)


def _validate_exp007(payload: dict[str, Any]) -> None:
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


def _validate_exp008(payload: dict[str, Any]) -> None:
    analysis = payload["analysis"]
    training = payload["training"]
    if [int(value) for value in analysis["split_seeds"]] != [43, 44, 45]:
        raise ValueError("EXP-008 split_seeds must be 43/44/45")
    if int(analysis["reference_split_seed"]) != 42 or float(analysis["test_fraction"]) != 0.25:
        raise ValueError("EXP-008 reference seed and test fraction differ from D-004")
    if float(analysis["decision_threshold"]) != 0.5:
        raise ValueError("EXP-008 decision threshold must be 0.5")
    if [float(value) for value in analysis["offline_target_abstention_rates"]] != [0.01, 0.02, 0.05, 0.10]:
        raise ValueError("EXP-008 offline budgets must be 0.01/0.02/0.05/0.10")
    if [float(value) for value in analysis["fixed_threshold_target_abstention_rates"]] != [0.01, 0.05]:
        raise ValueError("EXP-008 fixed-threshold budgets must be 0.01/0.05")
    rank = analysis["rank_verdict"]
    if (int(rank["minimum_errors_per_seed"]), float(rank["maximum_ratio_multiplier"])) != (10, 3.0):
        raise ValueError("EXP-008 rank verdict differs from D-004")
    throughput = analysis["throughput_verdict"]
    if (float(throughput["allowed_rate_multiplier_lower"]), float(throughput["allowed_rate_multiplier_upper"])) != (0.95, 1.05):
        raise ValueError("EXP-008 throughput band differs from D-004")
    if training["selection"] != "fixed_from_exp007" or training["selected_candidate_id"] != "C06":
        raise ValueError("EXP-008 must use fixed EXP-007 candidate C06")
    if int(training["num_boost_round"]) != 230 or bool(training["early_stopping"]):
        raise ValueError("EXP-008 must train exactly 230 iterations without early stopping")
    if training["calibration"] != "none":
        raise ValueError("EXP-008 does not permit calibration")
    params = training["fixed_parameters"]
    expected = {"num_leaves": 63, "min_data_in_leaf": 20, "lambda_l2": 1.0}
    if any(float(params[key]) != float(value) for key, value in expected.items()):
        raise ValueError("EXP-008 fixed C06 parameters differ from EXP-007")
