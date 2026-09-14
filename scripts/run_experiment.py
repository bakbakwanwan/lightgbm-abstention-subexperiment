#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from abstention_experiment.artifacts import distribution_values, write_json
from abstention_experiment.configuration import load_config
from abstention_experiment.data import feature_hash, internal_validation_mask, load_analysis_frame, load_whitelist, validate_sources
from abstention_experiment.evaluation import add_predictions, budget_metrics, expected_aurc, final_status, full_metrics
from abstention_experiment.modeling import runtime_versions, select_candidate, train_final


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--stage", choices=("validate", "all"), default="all")
    return parser.parse_args()


def git_state() -> tuple[str, bool]:
    safe = f"safe.directory={REPO_ROOT.as_posix()}"
    commit = subprocess.check_output(["git", "-c", safe, "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-c", safe, "status", "--porcelain"], cwd=REPO_ROOT, text=True).strip())
    return commit, dirty


def preflight(config, stage: str) -> tuple[str, dict]:
    commit, dirty = git_state()
    guard = config.raw["execution_guard"]
    if stage == "all" and guard["require_clean_worktree"] and dirty:
        raise RuntimeError("Execution guard: worktree is not clean")
    if stage == "all" and guard["refuse_existing_output"] and config.output_dir.exists():
        raise FileExistsError(f"Execution guard: output already exists: {config.output_dir}")
    integrity = validate_sources(config)
    if stage == "all" and guard["run_tests_first"]:
        command = [sys.executable if item == "python" else item for item in guard["test_command"]]
        subprocess.run(command, cwd=REPO_ROOT, check=True)
    return commit, integrity


def summarize_labels(method: str, target: pd.DataFrame, budgets: list[dict]) -> pd.DataFrame:
    rows = []
    for label, part in target.groupby("Label", observed=True):
        correct_for_label = int(part["predicted_label"].eq(0 if label == "BENIGN" else 1).sum())
        base = {"method": method, "Label": label, "target_abstention_rate": 0.0, "n_test": len(part), "n_accepted": len(part), "n_abstained": 0, "actual_abstention_rate": 0.0, "accepted_errors": int(part["is_error"].sum()), "accepted_error_rate": float(part["is_error"].mean()), "binary_recall_or_specificity": correct_for_label / len(part)}
        rows.append(base)
        for budget in budgets:
            t = budget["confidence_threshold"]; abstained = part["confidence"].le(t) if t is not None else pd.Series(False, index=part.index); accepted = part.loc[~abstained]
            rows.append({"method": method, "Label": label, "target_abstention_rate": budget["target_abstention_rate"], "n_test": len(part), "n_accepted": len(accepted), "n_abstained": int(abstained.sum()), "actual_abstention_rate": float(abstained.mean()), "accepted_errors": int(accepted["is_error"].sum()), "accepted_error_rate": None if accepted.empty else float(accepted["is_error"].mean()), "binary_recall_or_specificity": None})
    return pd.DataFrame(rows)


def summarize_overlap(method: str, overlap: pd.DataFrame, budgets: list[dict]) -> pd.DataFrame:
    rows = []
    for budget in [{"target_abstention_rate": 0.0, "confidence_threshold": None}] + budgets:
        threshold = budget["confidence_threshold"]
        abstained = overlap["confidence"].le(threshold) if threshold is not None else pd.Series(False, index=overlap.index)
        accepted = overlap.loc[~abstained]
        rows.append({"method": method, "target_abstention_rate": budget["target_abstention_rate"], "n_test": len(overlap), "n_labels": int(overlap["Label"].nunique()), "n_accepted": len(accepted), "n_abstained": int(abstained.sum()), "actual_abstention_rate": float(abstained.mean()), "accepted_errors": int(accepted["is_error"].sum()), "selective_risk": None if accepted.empty else float(accepted["is_error"].mean()), **distribution_values(overlap)})
    return pd.DataFrame(rows)


def summarize_observations(prediction: pd.DataFrame, primary_budgets: list[dict]) -> pd.DataFrame:
    observations = prediction.loc[prediction["observation_group"].ne("none")].copy()
    observations["Attempted Category"] = observations["Attempted Category"].astype(str)
    rows = []
    grouping_sets = [["observation_group"], ["observation_group", "Attempted Category"]]
    for columns in grouping_sets:
        for keys, part in observations.groupby(columns[0] if len(columns) == 1 else columns, observed=True):
            keys = (keys,) if not isinstance(keys, tuple) else keys
            if len(columns) == 2 and keys[0] != "attempted":
                continue
            base = dict(zip(columns, keys))
            for budget in primary_budgets:
                threshold = budget["confidence_threshold"]
                included = part["confidence"].le(threshold) if threshold is not None else pd.Series(False, index=part.index)
                row = {**base, "target_abstention_rate": budget["target_abstention_rate"], "confidence_threshold": threshold, "n_test": len(part), "n_in_band": int(included.sum()), "band_inclusion_rate": float(included.mean()), "predicted_benign": int(part["predicted_label"].eq(0).sum()), "predicted_attack": int(part["predicted_label"].eq(1).sum())}
                row.update(distribution_values(part))
                rows.append(row)
    return pd.DataFrame(rows)


def summarize_prediction_distributions(method: str, target: pd.DataFrame) -> pd.DataFrame:
    rows = [{"method": method, "scope": "all", "value": "all", "n_test": len(target), **distribution_values(target)}]
    for scope, column, mapping in (("error", "is_error", {0: "correct", 1: "error"}), ("binary_class", "binary_label", {0: "benign", 1: "attack"})):
        for value, part in target.groupby(column, observed=True):
            rows.append({"method": method, "scope": scope, "value": mapping[int(value)], "n_test": len(part), **distribution_values(part)})
    return pd.DataFrame(rows)


def main() -> int:
    cli = args(); config = load_config(cli.config.resolve(), REPO_ROOT)
    commit, integrity = preflight(config, cli.stage)
    if cli.stage == "validate":
        print(json.dumps({"status": "valid", "git_commit": commit, **integrity["checks"]}, indent=2)); return 0
    output = config.output_dir; output.mkdir(parents=True)
    include, _ = load_whitelist(config.path("inputs", "whitelist"))
    methods = [config.raw["analysis"]["primary_method"], config.raw["analysis"]["sensitivity_method"]]
    checks = {}
    primary = methods[0]
    primary_frame, checks[primary] = load_analysis_frame(config, primary)
    primary_train = primary_frame.loc[primary_frame["split"].eq("train")].copy()
    validation_mask = internal_validation_mask(primary_train, include, float(config.raw["analysis"]["internal_validation_fraction"]), int(config.raw["analysis"]["seed"]))
    checks["internal_validation"] = {"train_rows": int((~validation_mask).sum()), "validation_rows": int(validation_mask.sum()), "cross_split_feature_groups": 0}
    selected, histories = select_candidate(config, primary_train, validation_mask, include)
    all_metrics = {}; budget_rows = []; label_frames = []; overlap_frames = []; distribution_frames = []; primary_prediction = None; primary_budgets = None
    overlap_ids = pd.read_csv(config.path("inputs", "overlap_groups"))["group_id"].str.extract(r"g_([0-9a-f]{16})_")[0].dropna().map(lambda x: int(x, 16)).unique().astype(np.uint64)
    for method in methods:
        if method == primary:
            frame = primary_frame
        else:
            frame, checks[method] = load_analysis_frame(config, method)
        train = frame.loc[frame["split"].eq("train")].copy(); model = train_final(config, train, include, selected)
        evaluated = frame.loc[frame["split"].eq("test") | frame["observation_group"].ne("none")].copy()
        prediction = add_predictions(evaluated, model.predict(evaluated[include], num_iteration=int(selected["best_iteration"])), float(config.raw["analysis"]["decision_threshold"])); prediction.insert(0, "method", method)
        (output / "predictions").mkdir(parents=True, exist_ok=True)
        prediction.to_parquet(output / "predictions" / f"{method}.parquet", index=False)
        target = prediction.loc[prediction["observation_group"].eq("none")].copy()
        aurc, curve = expected_aurc(target); curve.insert(0, "method", method); (output / "aurc_curve").mkdir(parents=True, exist_ok=True); curve.to_csv(output / "aurc_curve" / f"{method}.csv.gz", index=False)
        shuffled_aurc, _ = expected_aurc(target.sample(frac=1.0, random_state=int(config.raw["analysis"]["seed"])))
        if aurc["aurc"] != shuffled_aurc["aurc"] or aurc["aurc"] < aurc["oracle_aurc"] - 1e-15:
            raise RuntimeError("AURC invariance or oracle lower-bound validation failed")
        budgets = budget_metrics(target, [float(x) for x in config.raw["analysis"]["target_abstention_rates"]])
        for row in budgets: row["method"] = method
        all_metrics[method] = {**full_metrics(target), **aurc, "budgets": budgets}
        budget_rows.extend(budgets); label_frames.append(summarize_labels(method, target, budgets)); distribution_frames.append(summarize_prediction_distributions(method, target))
        hashes = feature_hash(evaluated, include); target["is_class_overlap"] = np.isin(hashes[evaluated["observation_group"].eq("none").to_numpy()], overlap_ids)
        overlap = target.loc[target["is_class_overlap"]]
        if len(overlap): overlap_frames.append(summarize_overlap(method, overlap, budgets))
        if method == primary:
            all_metrics[method]["final_status"] = final_status(aurc, budgets)
            primary_prediction = prediction
            primary_budgets = budgets
        del train, model, evaluated, prediction, target, frame
        if method == primary:
            del primary_frame, primary_train
    pd.DataFrame(budget_rows).to_csv(output / "budget_summary.csv", index=False)
    pd.concat(label_frames, ignore_index=True).to_csv(output / "label_summary.csv", index=False)
    pd.concat(distribution_frames, ignore_index=True).to_csv(output / "prediction_distribution_summary.csv", index=False)
    (pd.concat(overlap_frames, ignore_index=True) if overlap_frames else pd.DataFrame()).to_csv(output / "overlap_summary.csv", index=False)
    if primary_prediction is None or primary_budgets is None: raise RuntimeError("Primary analysis outputs are missing")
    summarize_observations(primary_prediction, primary_budgets).to_csv(output / "observation_summary.csv", index=False)
    write_json(output / "candidate_history.json", {"selected": selected, "candidates": histories})
    write_json(output / "validation_checks.json", checks)
    write_json(output / "metrics.json", {"exp_id": config.exp_id, "git_commit": commit, "seed": config.raw["analysis"]["seed"], "dataset": integrity["dataset_file_sha256"], "primary_method": primary, "final_status": all_metrics[primary]["final_status"], "analyses": all_metrics})
    runtime = runtime_versions(); runtime["configured_num_threads"] = config.raw["training"]["num_threads"]
    write_json(output / "manifest.json", {"exp_id": config.exp_id, "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": commit, "working_tree_dirty_at_creation": False, "config": config.raw, "integrity": integrity, "runtime": runtime, "selected_candidate_id": selected["candidate_id"], "best_iteration": selected["best_iteration"], "sensitivity_reuses_primary_selection": True})
    print(f"완료: {output}"); return 0


if __name__ == "__main__":
    raise SystemExit(main())
