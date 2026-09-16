from __future__ import annotations

import itertools
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .artifacts import distribution_values, write_json
from .configuration import ExperimentConfig
from .data import feature_hash, load_analysis_frame, load_whitelist, sha256_file
from .evaluation import (
    add_predictions,
    budget_metrics,
    expected_aurc,
    fixed_threshold_metrics,
    full_metrics,
)
from .modeling import runtime_versions, train_fixed
from .splitting import (
    SplitPlan,
    build_split_plan,
    read_test_index,
    validate_saved_split_assignments,
    write_split_assignments,
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _check(condition: bool, observed: Any, expected: Any, source: str) -> dict[str, Any]:
    return {"passed": bool(condition), "observed": observed, "expected": expected, "source": source}


def _validate_references(config: ExperimentConfig) -> dict[str, Any]:
    inputs = config.raw["inputs"]
    expected = inputs["expected_sha256"]
    paths = {
        "baseline_split_manifest": config.path("inputs", "baseline_split_manifest"),
        "overlap_groups": config.path("inputs", "overlap_groups"),
        "exp007_manifest": config.path("inputs", "exp007_manifest"),
        "exp007_metrics": config.path("inputs", "exp007_metrics"),
        "exp007_candidate_history": config.path("inputs", "exp007_candidate_history"),
        "exp007_predictions": config.path("inputs", "exp007_predictions"),
    }
    actual_hashes = {key: sha256_file(path) for key, path in paths.items()}
    hash_checks = {
        key: _check(actual_hashes[key] == expected[key], actual_hashes[key], expected[key], str(paths[key]))
        for key in paths
    }
    spec_path = config.path("experiment", "spec")
    spec_hash = sha256_file(spec_path)
    hash_checks["spec"] = _check(
        spec_hash == config.raw["experiment"]["spec_sha256"],
        spec_hash,
        config.raw["experiment"]["spec_sha256"],
        str(spec_path),
    )
    if not all(item["passed"] for item in hash_checks.values()):
        raise RuntimeError(f"EXP-008 reference integrity failed: {hash_checks}")

    manifest = _read_json(paths["exp007_manifest"])
    metrics = _read_json(paths["exp007_metrics"])
    history = _read_json(paths["exp007_candidate_history"])
    baseline_manifest = _read_json(paths["baseline_split_manifest"])
    baseline_root = config.path("inputs", "baseline_split_dir").parent
    baseline_files = {
        name: value
        for name, value in baseline_manifest["output_file_sha256"].items()
        if name.startswith("group_seed42/")
    }
    baseline_file_checks = {
        name: _check(
            sha256_file(baseline_root / name) == expected_hash,
            sha256_file(baseline_root / name),
            expected_hash,
            str(baseline_root / name),
        )
        for name, expected_hash in baseline_files.items()
    }
    if len(baseline_file_checks) != 5 or not all(
        item["passed"] for item in baseline_file_checks.values()
    ):
        raise RuntimeError(f"EXP-007 baseline split files failed integrity: {baseline_file_checks}")
    selected = history["selected"]
    training = config.raw["training"]
    fixed = training["fixed_parameters"]
    exp007_fixed = dict(manifest["config"]["training"]["fixed_parameters"])
    exp007_fixed.update(
        {key: selected[key] for key in ("num_leaves", "min_data_in_leaf", "lambda_l2")}
    )
    fixed_match = all(
        float(fixed[key]) == float(selected[key])
        for key in ("num_leaves", "min_data_in_leaf", "lambda_l2")
    )
    contract_checks = {
        "candidate_id": _check(
            manifest["selected_candidate_id"] == training["selected_candidate_id"] == selected["candidate_id"],
            [manifest["selected_candidate_id"], selected["candidate_id"]],
            training["selected_candidate_id"],
            str(paths["exp007_candidate_history"]),
        ),
        "best_iteration": _check(
            int(manifest["best_iteration"]) == int(training["num_boost_round"]) == int(selected["best_iteration"]),
            [manifest["best_iteration"], selected["best_iteration"]],
            training["num_boost_round"],
            str(paths["exp007_manifest"]),
        ),
        "candidate_parameters": _check(
            fixed_match,
            {key: selected[key] for key in ("num_leaves", "min_data_in_leaf", "lambda_l2")},
            {key: fixed[key] for key in ("num_leaves", "min_data_in_leaf", "lambda_l2")},
            str(paths["exp007_candidate_history"]),
        ),
        "full_fixed_parameters": _check(
            fixed == exp007_fixed,
            fixed,
            exp007_fixed,
            str(paths["exp007_manifest"]),
        ),
    }
    if not all(item["passed"] for item in contract_checks.values()):
        raise RuntimeError(f"EXP-008 fixed-model contract failed: {contract_checks}")

    method = config.raw["analysis"]["reference_rank"]["method"]
    reference = metrics["analyses"][method]
    random_aurc = float(reference["random_aurc"])
    if random_aurc <= 0:
        raise RuntimeError("EXP-007 reference random_aurc must be positive")
    reference_ratio = float(reference["aurc"]) / random_aurc
    requested = set(float(value) for value in config.raw["analysis"]["fixed_threshold_target_abstention_rates"])
    thresholds = {
        float(row["target_abstention_rate"]): float(row["confidence_threshold"])
        for row in reference["budgets"]
        if float(row["target_abstention_rate"]) in requested
    }
    if set(thresholds) != requested:
        raise RuntimeError(f"Missing EXP-007 fixed thresholds: {thresholds}")
    return {
        "hash_checks": hash_checks,
        "contract_checks": contract_checks,
        "baseline_split_file_checks": baseline_file_checks,
        "actual_sha256": actual_hashes,
        "reference_aurc_random_ratio": reference_ratio,
        "maximum_aurc_random_ratio": reference_ratio
        * float(config.raw["analysis"]["rank_verdict"]["maximum_ratio_multiplier"]),
        "fixed_thresholds": thresholds,
        "exp007_metrics": metrics,
    }


def _worktree_clean() -> bool:
    safe = f"safe.directory={Path(__file__).resolve().parents[2].as_posix()}"
    status = subprocess.check_output(
        ["git", "-c", safe, "status", "--porcelain"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
    )
    return not bool(status.strip())


def _fixed_threshold_source(config: ExperimentConfig, target: float) -> str:
    source = config.raw["analysis"]["fixed_threshold_source"]
    return f"EXP-007/{source['method']}/{target:.2f}/{source['source']}"


def _distribution_row(method: str, seed: int, frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "method": method,
        "seed": seed,
        "n_test": len(frame),
        **distribution_values(frame),
        "confidence_ge_0_99999_rate": float(frame["confidence"].ge(0.99999).mean()),
        "p_attack_0_01_to_0_99_rate": float(frame["p_attack"].between(0.01, 0.99).mean()),
        "unique_confidence_values": int(frame["confidence"].nunique()),
    }


def _subset_threshold_metrics(
    frame: pd.DataFrame, target: float, threshold: float
) -> dict[str, Any]:
    if frame.empty:
        return {
            "target_abstention_rate": target,
            "confidence_threshold": threshold,
            "n_test": 0,
            "n_accepted": 0,
            "n_abstained": 0,
            "actual_abstention_rate": None,
            "accepted_errors": 0,
            "abstained_errors": 0,
            "total_errors": 0,
            "error_capture_rate": None,
            "error_enrichment": None,
            "selective_risk": None,
            "attack_coverage": None,
        }
    result = fixed_threshold_metrics(frame, target, threshold, 0.0, 1_000_000.0)
    keep = (
        "target_abstention_rate",
        "confidence_threshold",
        "n_test",
        "n_accepted",
        "n_abstained",
        "actual_abstention_rate",
        "accepted_errors",
        "abstained_errors",
        "total_errors",
        "error_capture_rate",
        "error_enrichment",
        "selective_risk",
        "attack_coverage",
    )
    return {key: result[key] for key in keep}


def _class_overlap_assignment(config: ExperimentConfig, plan: SplitPlan) -> pd.DataFrame:
    conflict = plan.group_label.loc[plan.group_label["feature_hash"].isin(plan.conflict_hashes)]
    baseline = pd.read_csv(config.path("inputs", "overlap_groups"))
    baseline_hash_to_split = {
        int(row.group_id.split("_")[1], 16): row.split
        for row in baseline[["group_id", "split"]].drop_duplicates().itertuples(index=False)
    }
    records: list[dict[str, Any]] = []
    for feature_hash, rows in conflict.groupby("feature_hash", observed=True, sort=False):
        value = int(feature_hash)
        record: dict[str, Any] = {
            "feature_group_id": plan.conflict_feature_group_ids[value],
            "group_size": int(rows["rows"].sum()),
            "benign_rows": int(rows.loc[rows["Label"].eq("BENIGN"), "rows"].sum()),
            "attack_rows": int(rows.loc[rows["Label"].ne("BENIGN"), "rows"].sum()),
            "label_counts": json.dumps(
                {str(row.Label): int(row.rows) for row in rows.itertuples(index=False)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            "group_seed42": baseline_hash_to_split[value],
        }
        group_rows = np.flatnonzero(plan.hashes == np.uint64(value))
        for method, mask in plan.test_masks.items():
            selected = mask[group_rows]
            if selected.any() and not selected.all():
                raise RuntimeError(f"Conflict group split across train/test: {method}/{value}")
            record[method] = "test" if selected.all() else "train"
        records.append(record)
    return pd.DataFrame(records).sort_values("feature_group_id").reset_index(drop=True)


def _split_summaries(
    config: ExperimentConfig, plan: SplitPlan
) -> tuple[pd.DataFrame, pd.DataFrame]:
    label_rows: list[dict[str, Any]] = []
    observation_rows: list[dict[str, Any]] = []
    for method, mask in plan.test_masks.items():
        seed = int(method.removeprefix("group_seed"))
        for split, selected in (("train", ~mask), ("test", mask)):
            counts = pd.Series(plan.labels[selected]).value_counts(sort=False)
            for label, count in counts.items():
                label_rows.append(
                    {"method": method, "seed": seed, "split": split, "Label": label, "n_rows": int(count)}
                )
            observation_rows.append(
                {"method": method, "seed": seed, "split": split, "observation_group": "none", "n_rows": int(selected.sum())}
            )
        expected_groups = config.raw["inputs"]["expected_population"]["observation_group_rows"]
        observation_rows.extend(
            [
                {"method": method, "seed": seed, "split": "", "observation_group": key, "n_rows": int(value)}
                for key, value in expected_groups.items()
            ]
        )
    return pd.DataFrame(label_rows), pd.DataFrame(observation_rows)


def _aggregate_verdicts(
    config: ExperimentConfig,
    seed_metrics: dict[str, dict[str, Any]],
    fixed_rows: list[dict[str, Any]],
) -> tuple[str, str, dict[str, str], dict[str, str]]:
    minimum = int(config.raw["analysis"]["rank_verdict"]["minimum_errors_per_seed"])
    rank_states: dict[str, str] = {}
    for method, metrics in seed_metrics.items():
        if int(metrics["total_errors"]) < minimum:
            rank_states[method] = "unassessable"
        elif float(metrics["aurc_random_ratio"]) <= float(metrics["maximum_aurc_random_ratio"]):
            rank_states[method] = "maintained"
        else:
            rank_states[method] = "failed"
    if "unassessable" in rank_states.values():
        rank_verdict = "inconclusive"
    else:
        passes = sum(value == "maintained" for value in rank_states.values())
        rank_verdict = "maintained" if passes == 3 else "inconclusive" if passes == 2 else "failed"

    fixed = pd.DataFrame(fixed_rows)
    throughput_states: dict[str, str] = {}
    for method, rows in fixed.groupby("method", observed=True):
        in_range = int(rows["within_allowed_range"].sum())
        throughput_states[str(method)] = "maintained" if in_range == 2 else "inconclusive" if in_range == 1 else "failed"
    if all(value == "maintained" for value in throughput_states.values()):
        throughput_verdict = "maintained"
    elif sum(value == "failed" for value in throughput_states.values()) >= 2:
        throughput_verdict = "failed"
    else:
        throughput_verdict = "inconclusive"
    return rank_verdict, throughput_verdict, rank_states, throughput_states


def _seed_overlap_summary(
    config: ExperimentConfig,
    plan: SplitPlan,
    split_root: Path,
    predictions: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    indexes: dict[int, pd.DataFrame] = {}
    baseline_method = "group_seed42"
    baseline_root = config.path("inputs", "baseline_split_dir").parent
    indexes[42] = read_test_index(baseline_root, baseline_method, plan.hashes)
    for method in plan.test_masks:
        seed = int(method.removeprefix("group_seed"))
        indexes[seed] = read_test_index(split_root, method, plan.hashes)

    reference_prediction = pd.read_parquet(config.path("inputs", "exp007_predictions"))
    reference_prediction = reference_prediction.loc[
        reference_prediction["observation_group"].eq("none") & reference_prediction["split"].eq("test")
    ]
    errors: dict[int, pd.DataFrame] = {
        42: reference_prediction.loc[reference_prediction["is_error"].eq(1), ["day", "id"]]
    }
    for method, frame in predictions.items():
        seed = int(method.removeprefix("group_seed"))
        errors[seed] = frame.loc[frame["is_error"].eq(1), ["day", "id"]]

    records: list[dict[str, Any]] = []
    for left, right in itertools.combinations(sorted(indexes), 2):
        left_rows = indexes[left]
        right_rows = indexes[right]
        common_rows = len(left_rows.merge(right_rows, on=["day", "id"], how="inner"))
        row_union = len(left_rows) + len(right_rows) - common_rows
        left_groups = np.unique(left_rows["feature_hash"].to_numpy(dtype=np.uint64))
        right_groups = np.unique(right_rows["feature_hash"].to_numpy(dtype=np.uint64))
        common_groups = len(np.intersect1d(left_groups, right_groups, assume_unique=True))
        group_union = len(left_groups) + len(right_groups) - common_groups
        common_error_rows = len(errors[left].merge(errors[right], on=["day", "id"], how="inner"))
        records.append(
            {
                "left_seed": left,
                "right_seed": right,
                "common_test_rows": common_rows,
                "row_jaccard": common_rows / row_union,
                "common_test_feature_groups": common_groups,
                "feature_group_jaccard": common_groups / group_union,
                "common_error_rows": common_error_rows,
            }
        )
    return pd.DataFrame(records)


def run_exp008(
    config: ExperimentConfig,
    stage: str,
    commit: str,
    integrity: dict[str, Any],
) -> int:
    references = _validate_references(config)
    features, _ = load_whitelist(config.path("inputs", "whitelist"))
    plan = build_split_plan(config, features)
    if stage == "validate":
        report = {
            "status": "valid",
            "git_commit": commit,
            "worktree_clean": _worktree_clean(),
            "output_exists": config.output_dir.exists(),
            "input_checks": integrity["checks"],
            "reference_checks": {
                key: value["passed"] for key, value in references["hash_checks"].items()
            },
            "model_contract_checks": {
                key: value["passed"] for key, value in references["contract_checks"].items()
            },
            "split_checks": plan.validation,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    output = config.output_dir
    output.mkdir(parents=True)
    split_root = output / "splits"
    split_manifest = write_split_assignments(config, plan, split_root)
    saved_split_checks = validate_saved_split_assignments(config, plan, split_root)
    label_summary, observation_summary = _split_summaries(config, plan)
    label_summary.to_csv(output / "label_summary.csv", index=False)
    observation_summary.to_csv(output / "observation_summary.csv", index=False)
    _class_overlap_assignment(config, plan).to_csv(output / "class_overlap_assignment.csv", index=False)

    seed_metrics: dict[str, dict[str, Any]] = {}
    predictions: dict[str, pd.DataFrame] = {}
    offline_rows: list[dict[str, Any]] = []
    fixed_rows: list[dict[str, Any]] = []
    overlap_rows: list[dict[str, Any]] = []
    distribution_rows: list[dict[str, Any]] = []
    seed_checks: dict[str, Any] = {}
    analysis = config.raw["analysis"]
    allowed_lower = float(analysis["throughput_verdict"]["allowed_rate_multiplier_lower"])
    allowed_upper = float(analysis["throughput_verdict"]["allowed_rate_multiplier_upper"])

    for method, split_validation in plan.validation.items():
        seed = int(split_validation["seed"])
        frame, load_check = load_analysis_frame(
            config,
            method,
            split_dir=split_root,
            enforce_exp007_counts=False,
        )
        train = frame.loc[frame["split"].eq("train")].copy()
        test = frame.loc[frame["split"].eq("test")].copy()
        model = train_fixed(config, train, features)
        if int(model.num_trees()) != int(config.raw["training"]["num_boost_round"]):
            raise RuntimeError(f"Fixed iteration mismatch for {method}: {model.num_trees()}")
        prediction = add_predictions(
            test,
            model.predict(test[features], num_iteration=int(config.raw["training"]["num_boost_round"])),
            float(analysis["decision_threshold"]),
        )
        prediction.insert(0, "method", method)
        if prediction.duplicated(["day", "id"]).any() or len(prediction) != split_validation["test_rows"]:
            raise RuntimeError(f"Prediction key or row-count validation failed for {method}")
        probability = prediction["p_attack"].to_numpy(dtype=float)
        expected_label = (probability >= float(analysis["decision_threshold"])).astype(np.int8)
        expected_confidence = np.maximum(probability, 1.0 - probability)
        expected_error = expected_label != prediction["binary_label"].to_numpy(dtype=np.int8)
        if (
            not np.isfinite(prediction[["p_attack", "confidence"]].to_numpy()).all()
            or ((probability < 0) | (probability > 1)).any()
            or not np.array_equal(prediction["predicted_label"].to_numpy(dtype=np.int8), expected_label)
            or not np.array_equal(prediction["confidence"].to_numpy(dtype=float), expected_confidence)
            or not np.array_equal(prediction["is_error"].to_numpy(dtype=np.int8), expected_error.astype(np.int8))
        ):
            raise RuntimeError(f"Non-finite predictions for {method}")
        (output / "predictions").mkdir(parents=True, exist_ok=True)
        prediction_path = output / "predictions" / f"{method}.parquet"
        prediction.to_parquet(prediction_path, index=False)
        persisted = pd.read_parquet(prediction_path)
        if (
            len(persisted) != len(prediction)
            or not np.array_equal(persisted[["day", "id"]].to_numpy(), prediction[["day", "id"]].to_numpy())
            or not np.array_equal(persisted["p_attack"].to_numpy(), prediction["p_attack"].to_numpy())
        ):
            raise RuntimeError(f"Persisted prediction validation failed for {method}")
        predictions[method] = prediction

        aurc, curve = expected_aurc(prediction)
        shuffle_differences = []
        for shuffle_seed in [int(value) for value in analysis["aurc_shuffle_seeds"]]:
            shuffled, _ = expected_aurc(prediction.sample(frac=1.0, random_state=shuffle_seed))
            shuffle_differences.append(abs(float(aurc["aurc"]) - float(shuffled["aurc"])))
        if max(shuffle_differences) > 1e-18 or aurc["aurc"] < aurc["oracle_aurc"] - 1e-15:
            raise RuntimeError(f"AURC arithmetic validation failed for {method}")
        curve.insert(0, "method", method)
        (output / "aurc_curve").mkdir(parents=True, exist_ok=True)
        curve.to_csv(output / "aurc_curve" / f"{method}.csv.gz", index=False)
        ratio = None if aurc["random_aurc"] == 0 else aurc["aurc"] / aurc["random_aurc"]
        metrics = {
            **full_metrics(prediction),
            **aurc,
            "aurc_random_ratio": ratio,
            "reference_aurc_random_ratio": references["reference_aurc_random_ratio"],
            "maximum_aurc_random_ratio": references["maximum_aurc_random_ratio"],
        }

        budgets = budget_metrics(
            prediction,
            [float(value) for value in analysis["offline_target_abstention_rates"]],
        )
        for row in budgets:
            row.update({"method": method, "seed": seed})
            offline_rows.append(row)
        metrics["offline_budgets"] = budgets

        fixed_for_seed = []
        for target, threshold in references["fixed_thresholds"].items():
            row = fixed_threshold_metrics(
                prediction,
                target,
                threshold,
                allowed_lower,
                allowed_upper,
            )
            row.update(
                {
                    "method": method,
                    "seed": seed,
                    "confidence_threshold_source": _fixed_threshold_source(config, target),
                }
            )
            direct_count = int(prediction["confidence"].le(threshold).sum())
            if direct_count != row["n_abstained"]:
                raise RuntimeError(f"Fixed threshold independent count mismatch for {method}/{target}")
            fixed_rows.append(row)
            fixed_for_seed.append(row)
        metrics["fixed_thresholds"] = fixed_for_seed

        hashes = feature_hash(test, features)
        is_overlap = np.isin(hashes, plan.conflict_hashes)
        for scope, subset in (
            ("with_class_overlap", prediction),
            ("without_class_overlap", prediction.loc[~is_overlap]),
            ("class_overlap_only", prediction.loc[is_overlap]),
        ):
            if subset.empty:
                subset_aurc = {"aurc": None, "random_aurc": None, "oracle_aurc": None}
                subset_distribution: dict[str, Any] = {}
            else:
                subset_aurc, _ = expected_aurc(subset)
                subset_distribution = distribution_values(subset)
            for full_budget in budgets:
                row = _subset_threshold_metrics(
                    subset,
                    float(full_budget["target_abstention_rate"]),
                    float(full_budget["confidence_threshold"]),
                )
                overlap_rows.append(
                    {
                        "method": method,
                        "seed": seed,
                        "scope": scope,
                        "n_test": len(subset),
                        "total_errors": int(subset["is_error"].sum()),
                        "aurc": subset_aurc["aurc"],
                        "random_aurc": subset_aurc["random_aurc"],
                        "oracle_aurc": subset_aurc["oracle_aurc"],
                        **subset_distribution,
                        **row,
                    }
                )

        distribution_rows.append(_distribution_row(method, seed, prediction))
        seed_checks[method] = {
            "passed": True,
            "split": split_validation,
            "load": load_check,
            "trained_iterations": int(model.num_trees()),
            "prediction_rows": len(prediction),
            "unique_prediction_keys": int(prediction[["day", "id"]].drop_duplicates().shape[0]),
            "aurc_shuffle_max_abs_difference": max(shuffle_differences),
            "oracle_lower_bound_satisfied": bool(aurc["aurc"] >= aurc["oracle_aurc"] - 1e-15),
        }
        seed_metrics[method] = metrics
        del frame, train, test, model

    pd.DataFrame(offline_rows).to_csv(output / "offline_budget_summary.csv", index=False)
    pd.DataFrame(fixed_rows).to_csv(output / "fixed_threshold_summary.csv", index=False)
    pd.DataFrame(overlap_rows).to_csv(output / "class_overlap_summary.csv", index=False)
    pd.DataFrame(distribution_rows).to_csv(output / "prediction_distribution_summary.csv", index=False)
    _seed_overlap_summary(config, plan, split_root, predictions).to_csv(
        output / "seed_overlap_summary.csv", index=False
    )

    rank_verdict, throughput_verdict, rank_states, throughput_states = _aggregate_verdicts(
        config, seed_metrics, fixed_rows
    )
    metrics_payload = {
        "exp_id": config.exp_id,
        "git_commit": commit,
        "rank_verdict": rank_verdict,
        "throughput_verdict": throughput_verdict,
        "rank_seed_states": rank_states,
        "throughput_seed_states": throughput_states,
        "analyses": seed_metrics,
    }
    write_json(output / "metrics.json", metrics_payload)

    required = [
        "metrics.json",
        "offline_budget_summary.csv",
        "fixed_threshold_summary.csv",
        "class_overlap_assignment.csv",
        "class_overlap_summary.csv",
        "seed_overlap_summary.csv",
        "label_summary.csv",
        "observation_summary.csv",
        "prediction_distribution_summary.csv",
        "splits/split_manifest.json",
    ]
    required.extend(f"predictions/{method}.parquet" for method in plan.test_masks)
    required.extend(f"aurc_curve/{method}.csv.gz" for method in plan.test_masks)
    required.extend(
        f"splits/{method}/{day}.csv.gz"
        for method in plan.test_masks
        for day in ("monday", "tuesday", "wednesday", "thursday", "friday")
    )
    missing = [name for name in required if not (output / name).is_file()]
    if missing:
        raise RuntimeError(f"Required EXP-008 artifacts are missing: {missing}")
    validation_checks = {
        "input": {"passed": True, "integrity": integrity, "references": references["hash_checks"]},
        "split": {
            "passed": True,
            "planned_methods": plan.validation,
            "saved_methods": saved_split_checks,
        },
        "training_prediction_evaluation": {"passed": True, "methods": seed_checks},
        "artifacts": {"passed": True, "required_file_count": len(required), "missing": missing},
    }
    write_json(output / "validation_checks.json", validation_checks)

    output_hashes = {
        str(path.relative_to(output)).replace("\\", "/"): sha256_file(path)
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    runtime = runtime_versions()
    runtime["configured_num_threads"] = config.raw["training"]["num_threads"]
    write_json(
        output / "manifest.json",
        {
            "exp_id": config.exp_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": commit,
            "working_tree_dirty_at_creation": False,
            "config": config.raw,
            "integrity": integrity,
            "reference_artifact_sha256": references["actual_sha256"],
            "reference_aurc_random_ratio": references["reference_aurc_random_ratio"],
            "maximum_aurc_random_ratio": references["maximum_aurc_random_ratio"],
            "fixed_thresholds": references["fixed_thresholds"],
            "selected_candidate_id": config.raw["training"]["selected_candidate_id"],
            "best_iteration": config.raw["training"]["num_boost_round"],
            "runtime": runtime,
            "split_manifest_sha256": sha256_file(split_root / "split_manifest.json"),
            "output_file_sha256": output_hashes,
        },
    )
    print(f"완료: {output}")
    return 0
