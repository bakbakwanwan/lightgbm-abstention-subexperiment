from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .data import sha256_file
from .layer2_common import read_json, read_jsonl, require_valid_run_id, utc_now, write_json, write_jsonl
from .layer2_runtime import ALL_FAILURES, DECISIONS


SIDECAR_KEYS = {
    "input_index",
    "day",
    "id",
    "binary_label",
    "p_attack",
    "confidence",
    "predicted_label",
    "is_error",
}
RESPONSE_KEYS = {
    "run_id",
    "input_index",
    "status",
    "parsed_decision",
    "raw_content",
    "generation_failure",
    "wall_latency_seconds",
    "http_status",
    "ollama",
}
OLLAMA_RESPONSE_KEYS = {
    "model",
    "created_at",
    "done",
    "done_reason",
    "total_duration",
    "load_duration",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
}


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _binary_metrics(labels: list[int], predictions: list[int]) -> dict[str, int | float | None]:
    if len(labels) != len(predictions):
        raise ValueError("Label and prediction lengths differ")
    tn = sum(y == 0 and p == 0 for y, p in zip(labels, predictions, strict=True))
    fp = sum(y == 0 and p == 1 for y, p in zip(labels, predictions, strict=True))
    fn = sum(y == 1 and p == 0 for y, p in zip(labels, predictions, strict=True))
    tp = sum(y == 1 and p == 1 for y, p in zip(labels, predictions, strict=True))
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = None if precision is None or recall is None or precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "n_rows": len(labels),
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "error_count": fp + fn,
        "error_rate": _ratio(fp + fn, len(labels)),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": _ratio(fp, fp + tn),
        "fnr": _ratio(fn, fn + tp),
    }


def _validate_response(row: dict[str, Any], run_id: str) -> None:
    if set(row) != RESPONSE_KEYS or row["run_id"] != run_id:
        raise ValueError("Response row keys or run_id are invalid")
    if not isinstance(row["ollama"], dict) or set(row["ollama"]) != OLLAMA_RESPONSE_KEYS:
        raise ValueError("Response Ollama metadata schema mismatch")
    status = row["status"]
    decision = row["parsed_decision"]
    failure = row["generation_failure"]
    if status == "completed":
        if decision not in {"BENIGN", "ATTACK"} or failure is not None:
            raise ValueError("Completed response contract mismatch")
    elif status == "indeterminate":
        if decision != "INDETERMINATE" or failure is not None:
            raise ValueError("Indeterminate response contract mismatch")
    elif status == "generation_failure":
        if decision is not None or not isinstance(failure, dict) or failure.get("code") not in ALL_FAILURES:
            raise ValueError("Generation failure response contract mismatch")
    else:
        raise ValueError("Unknown response status")
    latency = row["wall_latency_seconds"]
    if not isinstance(latency, (int, float)) or isinstance(latency, bool) or latency < 0:
        raise ValueError("Invalid wall latency")


def evaluate_layer2_run(
    *,
    export_manifest_path: Path,
    evaluation_sidecar_path: Path,
    run_manifest_path: Path,
    runner_status_path: Path,
    responses_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"Evaluation output already exists: {output_dir}")
    if responses_path.name != "llm_responses.jsonl":
        raise ValueError("Only completed llm_responses.jsonl can be evaluated")

    export_manifest = read_json(export_manifest_path)
    run_manifest = read_json(run_manifest_path)
    runner_status = read_json(runner_status_path)
    run_id = export_manifest.get("run_id")
    if not isinstance(run_id, str):
        raise ValueError("Export manifest has no run_id")
    require_valid_run_id(run_id)
    if run_manifest.get("run_id") != run_id or runner_status.get("run_id") != run_id:
        raise ValueError("run_id mismatch across evaluator inputs")
    if run_manifest.get("run_manifest_schema_version") != "e9-run-manifest-v1":
        raise ValueError("Run manifest schema version mismatch")
    if runner_status.get("status_schema_version") != "e9-runner-status-v1":
        raise ValueError("Runner status schema version mismatch")
    if runner_status.get("run_status") != "completed":
        raise ValueError("Runner status is not completed")
    if run_manifest.get("input_bundle", {}).get("manifest_sha256") != sha256_file(export_manifest_path):
        raise ValueError("Run manifest does not reference this export manifest")
    expected_sidecar_hash = export_manifest.get("integrity", {}).get("evaluation_sidecar_sha256")
    if sha256_file(evaluation_sidecar_path) != expected_sidecar_hash:
        raise ValueError("Evaluation sidecar SHA-256 mismatch")

    sidecar_rows = read_jsonl(evaluation_sidecar_path)
    response_rows = read_jsonl(responses_path)
    expected_rows = export_manifest.get("counts", {}).get("exported_rows")
    if not (len(sidecar_rows) == len(response_rows) == expected_rows == runner_status.get("expected_rows")):
        raise ValueError("Evaluator input row counts differ")
    if runner_status.get("written_rows") != expected_rows or runner_status.get("last_input_index") != expected_rows - 1:
        raise ValueError("Runner completion counters are inconsistent")
    indices = list(range(len(sidecar_rows)))
    if [row.get("input_index") for row in sidecar_rows] != indices:
        raise ValueError("Sidecar indices are not unique and contiguous")
    if [row.get("input_index") for row in response_rows] != indices:
        raise ValueError("Response indices are not unique and contiguous")
    if any(set(row) != SIDECAR_KEYS for row in sidecar_rows):
        raise ValueError("Sidecar row schema mismatch")
    for row in response_rows:
        _validate_response(row, run_id)

    records: list[dict[str, Any]] = []
    for sidecar, response in zip(sidecar_rows, response_rows, strict=True):
        label = int(sidecar["binary_label"])
        gate = int(sidecar["predicted_label"])
        if label not in (0, 1) or gate not in (0, 1):
            raise ValueError("Sidecar labels must be binary")
        if int(sidecar["is_error"]) != int(gate != label):
            raise ValueError("Sidecar is_error is inconsistent")
        decision = response["parsed_decision"]
        llm_label = 0 if decision == "BENIGN" else 1 if decision == "ATTACK" else None
        fallback = llm_label is None
        fallback_reason = (
            "indeterminate" if response["status"] == "indeterminate"
            else "generation_failure" if response["status"] == "generation_failure"
            else None
        )
        final = gate if fallback else llm_label
        gate_error = int(gate != label)
        final_error = int(final != label)
        transition = (
            f"gate_{'error' if gate_error else 'correct'}_"
            f"final_{'error' if final_error else 'correct'}"
        )
        failure = response["generation_failure"]
        records.append(
            {
                "input_index": sidecar["input_index"],
                "day": sidecar["day"],
                "id": sidecar["id"],
                "binary_label": label,
                "gate_predicted_label": gate,
                "llm_decision": decision,
                "llm_predicted_label": llm_label,
                "generation_failure_code": None if failure is None else failure["code"],
                "fallback_applied": fallback,
                "fallback_reason": fallback_reason,
                "final_predicted_label": final,
                "gate_is_error": gate_error,
                "final_is_error": final_error,
                "transition": transition,
                "llm_override": llm_label is not None and llm_label != gate,
                "wall_latency_seconds": response["wall_latency_seconds"],
            }
        )

    n_rows = len(records)
    valid = [row for row in records if row["llm_predicted_label"] is not None]
    indeterminate_count = sum(row["llm_decision"] == "INDETERMINATE" for row in records)
    failure_count = sum(row["generation_failure_code"] is not None for row in records)
    fallback_count = sum(row["fallback_applied"] for row in records)
    override_count = sum(row["llm_override"] for row in records)
    timeout_count = sum(row["generation_failure_code"] == "timeout" for row in records)
    parsing_failure_count = sum(
        row["generation_failure_code"] in {"decision_json_invalid", "decision_schema_invalid"}
        for row in records
    )
    schema_valid_count = n_rows - failure_count
    transition_names = (
        "gate_correct_final_correct",
        "gate_correct_final_error",
        "gate_error_final_correct",
        "gate_error_final_error",
    )
    latency = np.asarray([row["wall_latency_seconds"] for row in records], dtype=np.float64)
    metrics = {
        "counts": {
            "n_rows": n_rows,
            "llm_binary_decision_count": len(valid),
            "indeterminate_count": indeterminate_count,
            "generation_failure_count": failure_count,
            "fallback_count": fallback_count,
            "override_count": override_count,
            "timeout_count": timeout_count,
            "parsing_failure_count": parsing_failure_count,
            "schema_valid_count": schema_valid_count,
        },
        "rates": {
            "schema_valid_rate": _ratio(schema_valid_count, n_rows),
            "indeterminate_rate": _ratio(indeterminate_count, n_rows),
            "generation_failure_rate": _ratio(failure_count, n_rows),
            "fallback_rate": _ratio(fallback_count, n_rows),
            "override_rate": _ratio(override_count, n_rows),
            "timeout_rate": _ratio(timeout_count, n_rows),
            "parsing_failure_rate": _ratio(parsing_failure_count, n_rows),
        },
        "gate_forced": _binary_metrics(
            [row["binary_label"] for row in records],
            [row["gate_predicted_label"] for row in records],
        ),
        "llm_valid_only": _binary_metrics(
            [row["binary_label"] for row in valid],
            [row["llm_predicted_label"] for row in valid],
        ),
        "end_to_end": _binary_metrics(
            [row["binary_label"] for row in records],
            [row["final_predicted_label"] for row in records],
        ),
        "transitions": {
            name: sum(row["transition"] == name for row in records) for name in transition_names
        },
        "latency_seconds": {
            "n": int(latency.size),
            "p50": None if latency.size == 0 else float(np.percentile(latency, 50)),
            "p95": None if latency.size == 0 else float(np.percentile(latency, 95)),
        },
    }

    output_dir.mkdir(parents=True)
    records_path = output_dir / "evaluation_records.jsonl"
    write_jsonl(records_path, records)
    write_json(output_dir / "metrics.json", metrics)
    evaluation_manifest = {
        "evaluation_schema_version": "e9-evaluation-v1",
        "evaluated_at": utc_now(),
        "run_id": run_id,
        "export_manifest_sha256": sha256_file(export_manifest_path),
        "evaluation_sidecar_sha256": sha256_file(evaluation_sidecar_path),
        "run_manifest_sha256": sha256_file(run_manifest_path),
        "runner_status_sha256": sha256_file(runner_status_path),
        "llm_responses_sha256": sha256_file(responses_path),
        "evaluation_records_sha256": sha256_file(records_path),
    }
    write_json(output_dir / "evaluation_manifest.json", evaluation_manifest)
    return metrics
