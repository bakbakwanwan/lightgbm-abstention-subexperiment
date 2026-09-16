from __future__ import annotations

import platform
import os
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from .configuration import ExperimentConfig


def _dataset(frame: pd.DataFrame, features: list[str]) -> lgb.Dataset:
    return lgb.Dataset(frame[features], label=frame["binary_label"].astype("int8"), categorical_feature=["Protocol"], free_raw_data=False)


def select_candidate(config: ExperimentConfig, train: pd.DataFrame, validation_mask: np.ndarray, features: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    spec = config.raw["training"]
    histories: list[dict[str, Any]] = []
    for candidate in spec["candidates"]:
        evaluations: dict[str, dict[str, list[float]]] = {}
        params = dict(spec["fixed_parameters"])
        params.update({k: v for k, v in candidate.items() if k != "candidate_id"})
        params["num_threads"] = int(spec["num_threads"])
        try:
            training_data = _dataset(train.loc[~validation_mask], features)
            validation_data = _dataset(train.loc[validation_mask], features)
            model = lgb.train(params, training_data, num_boost_round=int(spec["num_boost_round"]), valid_sets=[validation_data, training_data], valid_names=["validation", "training"], callbacks=[lgb.record_evaluation(evaluations), lgb.early_stopping(int(spec["stopping_rounds"]), first_metric_only=True, min_delta=float(spec["min_delta"]), verbose=False)])
            losses = evaluations["validation"]["binary_logloss"]
            valid = bool(losses) and np.isfinite(losses).all() and len(losses) < int(spec["num_boost_round"])
            histories.append({**candidate, "status": "ok" if valid else "failed", "best_iteration": int(model.best_iteration), "validation_binary_logloss": float(model.best_score["validation"]["binary_logloss"]), "validation_binary_logloss_history": losses, "training_binary_logloss_history": evaluations["training"]["binary_logloss"], "trained_iterations": len(losses)})
        except Exception as exc:
            histories.append({**candidate, "status": "failed", "error": f"{type(exc).__name__}: {exc}"})
    valid = [item for item in histories if item["status"] == "ok"]
    if not valid:
        raise RuntimeError("All candidates failed or reached the iteration ceiling")
    best_loss = min(item["validation_binary_logloss"] for item in valid)
    tolerance = float(spec["candidate_tolerance"])
    tied = [item for item in valid if item["validation_binary_logloss"] - best_loss <= tolerance]
    selected = min(tied, key=lambda x: (int(x["num_leaves"]), -int(x["min_data_in_leaf"]), -float(x["lambda_l2"]), int(x["best_iteration"]), str(x["candidate_id"]))).copy()
    selected["tie_rule_applied"] = len(tied) > 1
    return selected, histories


def train_final(config: ExperimentConfig, train: pd.DataFrame, features: list[str], selected: dict[str, Any]) -> lgb.Booster:
    params = dict(config.raw["training"]["fixed_parameters"])
    for key in ("num_leaves", "min_data_in_leaf", "lambda_l2"):
        params[key] = selected[key]
    params["num_threads"] = int(config.raw["training"]["num_threads"])
    return lgb.train(params, _dataset(train, features), num_boost_round=int(selected["best_iteration"]))


def train_fixed(config: ExperimentConfig, train: pd.DataFrame, features: list[str]) -> lgb.Booster:
    """Train the fixed EXP-008 C06 model without selection or early stopping."""
    params = dict(config.raw["training"]["fixed_parameters"])
    params["num_threads"] = int(config.raw["training"]["num_threads"])
    return lgb.train(
        params,
        _dataset(train, features),
        num_boost_round=int(config.raw["training"]["num_boost_round"]),
    )


def runtime_versions() -> dict[str, Any]:
    import sklearn
    return {"python": platform.python_version(), "os": platform.platform(), "logical_cpu_count": os.cpu_count(), "configured_num_threads": None, "lightgbm": lgb.__version__, "pandas": pd.__version__, "numpy": np.__version__, "scikit_learn": sklearn.__version__}
