from __future__ import annotations

from typing import Any
import math

import numpy as np
import pandas as pd


def expected_aurc(predictions: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    ordered = predictions.sort_values("confidence", ascending=False, kind="stable")
    groups = ordered.groupby("confidence", sort=False, observed=True)["is_error"].agg(["size", "sum"]).reset_index()
    n = len(ordered)
    k0 = 0
    e0 = 0.0
    total = 0.0
    rows = []
    for row in groups.itertuples(index=False):
        m, q = int(row.size), int(row.sum)
        j = np.arange(1, m + 1, dtype=np.float64)
        risks = (e0 + j * q / m) / (k0 + j)
        total += float(risks.sum())
        k0 += m
        e0 += q
        rows.append({"confidence_threshold": float(row.confidence), "n_accepted": k0, "coverage": k0 / n, "expected_errors_accepted": e0, "selective_risk": e0 / k0})
    errors = int(predictions["is_error"].sum())
    full = errors / n
    correct = n - errors
    oracle_errors = np.maximum(np.arange(1, n + 1) - correct, 0)
    oracle = float(np.mean(oracle_errors / np.arange(1, n + 1)))
    aurc = total / n
    relative = None if full == 0 else (full - aurc) / full
    return {"n_test": n, "aurc": aurc, "full_coverage_risk": full, "random_aurc": full, "oracle_aurc": oracle, "relative_aurc_improvement": relative, "total_errors": errors}, pd.DataFrame(rows)


def _ratio(numerator: int, denominator: int) -> tuple[float | None, str | None]:
    return (None, "zero_denominator") if denominator == 0 else (numerator / denominator, None)


def full_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    from sklearn.metrics import average_precision_score, log_loss, roc_auc_score

    y = frame["binary_label"].astype(int).to_numpy()
    pred = frame["predicted_label"].to_numpy(dtype=int)
    p = frame["p_attack"].to_numpy(dtype=float)
    tn = int(((y == 0) & (pred == 0)).sum()); fp = int(((y == 0) & (pred == 1)).sum())
    fn = int(((y == 1) & (pred == 0)).sum()); tp = int(((y == 1) & (pred == 1)).sum())
    fpr, fpr_reason = _ratio(fp, tn + fp); fnr, fnr_reason = _ratio(fn, tp + fn)
    return {"n_test": len(frame), "tn": tn, "fp": fp, "fn": fn, "tp": tp, "full_coverage_risk": (fp + fn) / len(frame), "fpr": fpr, "fpr_reason": fpr_reason, "fnr": fnr, "fnr_reason": fnr_reason, "auroc": float(roc_auc_score(y, p)), "average_precision": float(average_precision_score(y, p)), "binary_logloss": float(log_loss(y, p, labels=[0, 1]))}


def budget_metrics(frame: pd.DataFrame, rates: list[float]) -> list[dict[str, Any]]:
    n = len(frame); total_errors = int(frame["is_error"].sum()); benign = int(frame["binary_label"].eq(0).sum()); attack = n - benign
    grouped = frame.groupby("confidence", sort=True, observed=True).size()
    result = []
    for target in rates:
        used = 0; threshold = None; next_rate = None
        for confidence, size in grouped.items():
            if used + int(size) <= target * n + 1e-12:
                used += int(size); threshold = float(confidence)
            else:
                next_rate = (used + int(size)) / n; break
        abstained = frame["confidence"].le(threshold) if threshold is not None else pd.Series(False, index=frame.index)
        accepted = ~abstained
        a = frame.loc[accepted]; z = frame.loc[abstained]
        accepted_errors = int(a["is_error"].sum()); abstained_errors = int(z["is_error"].sum())
        actual = used / n
        capture, capture_reason = _ratio(abstained_errors, total_errors)
        enrichment = None if actual == 0 or capture is None else capture / actual
        accepted_benign = int(a["binary_label"].eq(0).sum()); accepted_attack = int(a["binary_label"].eq(1).sum())
        accepted_fp = int(((a["binary_label"] == 0) & (a["predicted_label"] == 1)).sum()); accepted_fn = int(((a["binary_label"] == 1) & (a["predicted_label"] == 0)).sum())
        sfpr, sfpr_reason = _ratio(accepted_fp, accepted_benign); sfnr, sfnr_reason = _ratio(accepted_fn, accepted_attack)
        rfpr, rfpr_reason = _ratio(accepted_fp, benign); rfnr, rfnr_reason = _ratio(accepted_fn, attack)
        bcov, bcov_reason = _ratio(accepted_benign, benign); acov, acov_reason = _ratio(accepted_attack, attack)
        srisk, srisk_reason = _ratio(accepted_errors, len(a))
        result.append({"target_abstention_rate": target, "actual_abstention_rate": actual, "n_test": n, "n_accepted": len(a), "n_abstained": used, "coverage": len(a) / n, "confidence_threshold": threshold, "confidence_threshold_reason": "confidence_resolution_insufficient" if threshold is None else None, "abstention_band_lower": None if threshold is None else 1-threshold, "abstention_band_upper": threshold, "budget_shortfall": target-actual, "next_tie_inclusive_abstention_rate": next_rate, "accepted_errors": accepted_errors, "abstained_errors": abstained_errors, "selective_risk": srisk, "selective_risk_reason": srisk_reason, "error_capture_rate": capture, "error_capture_rate_reason": capture_reason, "error_enrichment": enrichment, "selective_fpr": sfpr, "selective_fpr_reason": sfpr_reason, "selective_fnr": sfnr, "selective_fnr_reason": sfnr_reason, "residual_fpr": rfpr, "residual_fpr_reason": rfpr_reason, "residual_fnr": rfnr, "residual_fnr_reason": rfnr_reason, "benign_coverage": bcov, "benign_coverage_reason": bcov_reason, "attack_coverage": acov, "attack_coverage_reason": acov_reason, "accepted_fp": accepted_fp, "accepted_fn": accepted_fn, "accepted_benign": accepted_benign, "accepted_attack": accepted_attack, "total_benign": benign, "total_attack": attack, "total_errors": total_errors})
    return result


def fixed_threshold_metrics(
    frame: pd.DataFrame,
    target_abstention_rate: float,
    confidence_threshold: float,
    allowed_multiplier_lower: float,
    allowed_multiplier_upper: float,
) -> dict[str, Any]:
    """Apply an external confidence threshold without using evaluation labels to select it."""
    n = len(frame)
    abstained = frame["confidence"].le(confidence_threshold)
    accepted = ~abstained
    a = frame.loc[accepted]
    z = frame.loc[abstained]
    n_abstained = int(abstained.sum())
    total_errors = int(frame["is_error"].sum())
    accepted_errors = int(a["is_error"].sum())
    abstained_errors = int(z["is_error"].sum())
    actual = n_abstained / n
    capture, capture_reason = _ratio(abstained_errors, total_errors)
    enrichment = None if actual == 0 or capture is None else capture / actual
    selective_risk, selective_risk_reason = _ratio(accepted_errors, len(a))
    total_attack = int(frame["binary_label"].eq(1).sum())
    accepted_attack = int(a["binary_label"].eq(1).sum())
    attack_coverage, attack_coverage_reason = _ratio(accepted_attack, total_attack)
    lower = target_abstention_rate * allowed_multiplier_lower
    upper = target_abstention_rate * allowed_multiplier_upper
    target_rows = math.floor(target_abstention_rate * n)
    return {
        "target_abstention_rate": target_abstention_rate,
        "confidence_threshold": confidence_threshold,
        "n_test": n,
        "n_accepted": int(accepted.sum()),
        "n_abstained": n_abstained,
        "actual_abstention_rate": actual,
        "target_abstention_rows": target_rows,
        "abstention_row_delta": n_abstained - target_rows,
        "abstention_rate_delta": actual - target_abstention_rate,
        "allowed_abstention_rate_lower": lower,
        "allowed_abstention_rate_upper": upper,
        "within_allowed_range": lower <= actual <= upper,
        "accepted_errors": accepted_errors,
        "abstained_errors": abstained_errors,
        "total_errors": total_errors,
        "error_capture_rate": capture,
        "error_capture_rate_reason": capture_reason,
        "error_enrichment": enrichment,
        "selective_risk": selective_risk,
        "selective_risk_reason": selective_risk_reason,
        "attack_coverage": attack_coverage,
        "attack_coverage_reason": attack_coverage_reason,
    }


def add_predictions(frame: pd.DataFrame, probabilities: np.ndarray, threshold: float) -> pd.DataFrame:
    if len(frame) != len(probabilities) or not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise RuntimeError("Invalid prediction probabilities")
    out = frame[["day", "id", "Label", "Attempted Category", "observation_group", "split", "binary_label"]].copy()
    out["p_attack"] = probabilities.astype("float64")
    out["predicted_label"] = (out["p_attack"] >= threshold).astype("int8")
    out["confidence"] = np.maximum(out["p_attack"], 1-out["p_attack"])
    out["is_error"] = pd.Series(pd.NA, index=out.index, dtype="Int8")
    target = out["observation_group"].eq("none")
    out.loc[target, "is_error"] = out.loc[target, "predicted_label"].ne(out.loc[target, "binary_label"]).astype("int8")
    return out


def final_status(aurc: dict[str, Any], budgets: list[dict[str, Any]]) -> str:
    if aurc["total_errors"] == 0:
        return "scientifically_inconclusive"
    by_rate = {round(x["target_abstention_rate"], 2): x for x in budgets}; five = by_rate[0.05]
    improved = sum(x["actual_abstention_rate"] > 0 and x["error_enrichment"] is not None and x["error_enrichment"] > 1 and x["selective_risk"] < aurc["full_coverage_risk"] for x in budgets)
    success = aurc["relative_aurc_improvement"] >= 0.10 and five["actual_abstention_rate"] >= 0.04 and five["error_enrichment"] >= 2.0 and five["selective_risk"] < aurc["full_coverage_risk"] and improved >= 3
    failure = aurc["relative_aurc_improvement"] <= 0 or five["actual_abstention_rate"] == 0 or five["error_enrichment"] is None or five["error_enrichment"] <= 1 or five["selective_risk"] is None or five["selective_risk"] >= aurc["full_coverage_risk"] or improved <= 1
    return "success" if success else "failure" if failure else "scientifically_inconclusive"
