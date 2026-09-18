from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from urllib import error
import json
import shutil

import pytest

from abstention_experiment.data import sha256_file
from abstention_experiment.layer2_common import read_json, read_jsonl, write_json, write_jsonl
from abstention_experiment.layer2_evaluation import evaluate_layer2_run
from abstention_experiment.layer2_package import package_transfer_bundle
from abstention_experiment.layer2_runtime import (
    EXPECTED_MODEL,
    RunIncompleteError,
    _parse_api_response,
    load_prompt_asset,
    run_ollama_bundle,
    validate_transfer_bundle,
)


RUN_ID = "e9-pilot-20260918T120000Z-a1b2c3d4"


@pytest.fixture
def work_path(request: pytest.FixtureRequest):
    root = Path(__file__).parent / ".runtime_tmp"
    root.mkdir(mode=0o777, exist_ok=True)
    path = root / request.node.name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(mode=0o777)
    yield path
    shutil.rmtree(path)


def _bundle(tmp_path: Path, row_count: int = 2) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    bundle = tmp_path / "bundle"
    transfer = bundle / "transfer"
    transfer.mkdir(parents=True)
    schema_source = repo_root / "configs/llm/e9_input_feature_schema.json"
    prompt_source = repo_root / "configs/llm/e9_prompt_v1.json"
    schema_path = transfer / schema_source.name
    prompt_path = transfer / prompt_source.name
    schema_path.write_bytes(schema_source.read_bytes())
    prompt_path.write_bytes(prompt_source.read_bytes())
    schema = read_json(schema_path)
    rows = []
    for index in range(row_count):
        features = {
            feature: ("TCP" if feature == "Protocol" else float(index))
            for feature in schema["features"]
        }
        rows.append({"input_index": index, "payload": {"flow_features": features}})
    inputs_path = transfer / "llm_inputs.jsonl"
    write_jsonl(inputs_path, rows)
    manifest = {
        "bundle_type": "layer2_abstained_flow_export",
        "schema_version": schema["schema_version"],
        "run_id": RUN_ID,
        "counts": {"exported_rows": row_count, "feature_count": 59},
        "artifacts": {
            "llm_inputs": {
                "path": "transfer/llm_inputs.jsonl",
                "sha256": sha256_file(inputs_path),
                "rows": row_count,
            },
            "feature_schema": {
                "path": f"transfer/{schema_path.name}",
                "version": schema["schema_version"],
                "sha256": sha256_file(schema_path),
            },
            "prompt": {
                "path": f"transfer/{prompt_path.name}",
                "version": "e9-v1",
                "sha256": sha256_file(prompt_path),
            },
        },
        "integrity": {},
        "transfer_contract": {
            "copy_to_llm_environment": [
                "transfer/llm_inputs.jsonl",
                "transfer/e9_input_feature_schema.json",
                "transfer/e9_prompt_v1.json",
                "manifest.json",
            ]
        },
    }
    write_json(bundle / "manifest.json", manifest)
    return bundle


def _api(content: str, *, done: bool = True, done_reason: str = "stop") -> dict:
    return {
        "model": "gemma:7b-instruct",
        "created_at": "2026-09-18T12:00:00Z",
        "message": {"role": "assistant", "content": content},
        "done": done,
        "done_reason": done_reason,
        "total_duration": 10,
        "load_duration": 1,
        "prompt_eval_count": 100,
        "prompt_eval_duration": 2,
        "eval_count": 4,
        "eval_duration": 7,
    }


def test_bundle_validator_accepts_contract_and_rejects_forbidden_field(work_path: Path) -> None:
    bundle = _bundle(work_path)
    valid = validate_transfer_bundle(bundle)
    assert valid["passed"] is True

    inputs_path = bundle / "transfer/llm_inputs.jsonl"
    rows = read_jsonl(inputs_path)
    rows[0]["payload"]["flow_features"]["confidence"] = 0.5
    inputs_path.unlink()
    write_jsonl(inputs_path, rows)
    manifest = read_json(bundle / "manifest.json")
    manifest["artifacts"]["llm_inputs"]["sha256"] = sha256_file(inputs_path)
    write_json(bundle / "manifest.json", manifest)

    invalid = validate_transfer_bundle(bundle)
    assert invalid["passed"] is False
    assert invalid["checks"]["forbidden_fields"]["passed"] is False
    assert invalid["checks"]["forbidden_fields"]["observed"] == ["confidence"]


def test_bundle_validator_detects_hash_count_index_and_feature_mutations(work_path: Path) -> None:
    hash_bundle = _bundle(work_path / "hash")
    hash_inputs = hash_bundle / "transfer/llm_inputs.jsonl"
    hash_inputs.write_bytes(hash_inputs.read_bytes() + b"\n")
    assert validate_transfer_bundle(hash_bundle)["checks"]["input_jsonl_sha256"]["passed"] is False

    count_bundle = _bundle(work_path / "count")
    count_inputs = count_bundle / "transfer/llm_inputs.jsonl"
    count_rows = read_jsonl(count_inputs)[:1]
    count_inputs.unlink()
    write_jsonl(count_inputs, count_rows)
    count_manifest = read_json(count_bundle / "manifest.json")
    count_manifest["artifacts"]["llm_inputs"]["sha256"] = sha256_file(count_inputs)
    write_json(count_bundle / "manifest.json", count_manifest)
    assert validate_transfer_bundle(count_bundle)["checks"]["row_count"]["passed"] is False

    index_bundle = _bundle(work_path / "index")
    index_inputs = index_bundle / "transfer/llm_inputs.jsonl"
    index_rows = read_jsonl(index_inputs)
    index_rows[1]["input_index"] = 0
    index_inputs.unlink()
    write_jsonl(index_inputs, index_rows)
    index_manifest = read_json(index_bundle / "manifest.json")
    index_manifest["artifacts"]["llm_inputs"]["sha256"] = sha256_file(index_inputs)
    write_json(index_bundle / "manifest.json", index_manifest)
    assert validate_transfer_bundle(index_bundle)["checks"]["input_index"]["passed"] is False

    feature_bundle = _bundle(work_path / "feature")
    feature_inputs = feature_bundle / "transfer/llm_inputs.jsonl"
    feature_rows = read_jsonl(feature_inputs)
    feature_rows[0]["payload"]["flow_features"].pop("Flow Duration")
    feature_inputs.unlink()
    write_jsonl(feature_inputs, feature_rows)
    feature_manifest = read_json(feature_bundle / "manifest.json")
    feature_manifest["artifacts"]["llm_inputs"]["sha256"] = sha256_file(feature_inputs)
    write_json(feature_bundle / "manifest.json", feature_manifest)
    assert validate_transfer_bundle(feature_bundle)["checks"]["feature_rows"]["passed"] is False


def test_transfer_archive_excludes_local_evaluation_artifacts(work_path: Path) -> None:
    import zipfile

    bundle = _bundle(work_path)
    local = bundle / "local"
    local.mkdir()
    (local / "evaluation_sidecar.jsonl").write_text("secret", encoding="utf-8")
    archive_path = work_path / "llm_transfer_bundle.zip"
    package = package_transfer_bundle(bundle, archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
    assert names == {
        "manifest.json",
        "transfer/llm_inputs.jsonl",
        "transfer/e9_input_feature_schema.json",
        "transfer/e9_prompt_v1.json",
    }
    assert package["archive"]["sha256"] == sha256_file(archive_path)
    assert "local/evaluation_sidecar.jsonl" not in names


def test_prompt_render_is_deterministic_and_contains_no_transport_metadata() -> None:
    root = Path(__file__).resolve().parents[2]
    prompt = load_prompt_asset(root / "configs/llm/e9_prompt_v1.json")
    features = {"Protocol": "TCP", "Flow Duration": 3.0}
    first = prompt.render(features)
    second = prompt.render(features)
    assert first == second
    assert "input_index" not in first
    assert "predicted_label" not in first
    assert '"Protocol":"TCP"' in first


def test_ollama_generated_modelfile_blob_path_is_recognized() -> None:
    from abstention_experiment.layer2_runtime import _base_blob_sha, _model_id

    digest = EXPECTED_MODEL["base_blob_sha256"]
    assert _base_blob_sha(f"FROM /models/blobs/sha256-{digest}\n") == digest
    assert _model_id(f"sha256:{EXPECTED_MODEL['model_id']}9876") == EXPECTED_MODEL["model_id"]


def test_strict_response_parser_distinguishes_valid_json_and_schema_failures() -> None:
    normal = _parse_api_response(RUN_ID, 0, 200, _api('{"decision":"ATTACK"}'), 0.1)
    invalid_json = _parse_api_response(RUN_ID, 1, 200, _api('```json\n{"decision":"ATTACK"}\n```'), 0.1)
    invalid_schema = _parse_api_response(RUN_ID, 2, 200, _api('{"decision":"ATTACK","reason":"x"}'), 0.1)
    assert normal["status"] == "completed"
    assert normal["parsed_decision"] == "ATTACK"
    assert invalid_json["generation_failure"]["code"] == "decision_json_invalid"
    assert invalid_schema["generation_failure"]["code"] == "decision_schema_invalid"


def test_runner_writes_one_response_per_input_and_keeps_timeout_as_row_failure(work_path: Path) -> None:
    bundle = _bundle(work_path)
    output = work_path / "returned"
    calls = 0
    observed_payloads = []

    def fake_chat(payload: dict):
        nonlocal calls
        observed_payloads.append(payload)
        calls += 1
        if calls == 1:
            raise TimeoutError
        return 200, _api('{"decision":"INDETERMINATE"}')

    status = run_ollama_bundle(
        bundle_root=bundle,
        output_dir=output,
        run_id=RUN_ID,
        repo_root=Path(__file__).resolve().parents[2],
        chat=fake_chat,
        model_metadata=deepcopy(EXPECTED_MODEL),
    )
    assert status["run_status"] == "completed"
    assert not (output / "llm_responses.partial.jsonl").exists()
    rows = read_jsonl(output / "llm_responses.jsonl")
    assert [row["input_index"] for row in rows] == [0, 1]
    assert rows[0]["generation_failure"]["code"] == "timeout"
    assert rows[1]["status"] == "indeterminate"
    assert all("input_index" not in item["messages"][1]["content"] for item in observed_payloads)


def test_runner_aborts_on_connection_error_and_preserves_partial(work_path: Path) -> None:
    bundle = _bundle(work_path)
    output = work_path / "returned"

    def fake_chat(_: dict):
        raise error.URLError(ConnectionRefusedError())

    with pytest.raises(RunIncompleteError):
        run_ollama_bundle(
            bundle_root=bundle,
            output_dir=output,
            run_id=RUN_ID,
            repo_root=Path(__file__).resolve().parents[2],
            chat=fake_chat,
            model_metadata=deepcopy(EXPECTED_MODEL),
        )
    assert (output / "llm_responses.partial.jsonl").exists()
    assert not (output / "llm_responses.jsonl").exists()
    status = read_json(output / "runner_status.json")
    assert status["run_status"] == "incomplete"
    assert status["reason"] == "connection_error"


def test_evaluator_applies_fallback_and_counts_transitions(work_path: Path) -> None:
    bundle = _bundle(work_path, row_count=4)
    sidecar_path = work_path / "evaluation_sidecar.jsonl"
    sidecar = [
        {"input_index": 0, "day": "monday", "id": 1, "binary_label": 0, "p_attack": 0.1, "confidence": 0.9, "predicted_label": 0, "is_error": 0},
        {"input_index": 1, "day": "monday", "id": 2, "binary_label": 1, "p_attack": 0.8, "confidence": 0.8, "predicted_label": 1, "is_error": 0},
        {"input_index": 2, "day": "tuesday", "id": 3, "binary_label": 1, "p_attack": 0.2, "confidence": 0.8, "predicted_label": 0, "is_error": 1},
        {"input_index": 3, "day": "friday", "id": 4, "binary_label": 0, "p_attack": 0.7, "confidence": 0.7, "predicted_label": 1, "is_error": 1},
    ]
    write_jsonl(sidecar_path, sidecar)
    export_manifest_path = bundle / "manifest.json"
    export_manifest = read_json(export_manifest_path)
    export_manifest["integrity"]["evaluation_sidecar_sha256"] = sha256_file(sidecar_path)
    write_json(export_manifest_path, export_manifest)

    returned = work_path / "returned"
    returned.mkdir()
    run_manifest_path = returned / "run_manifest.json"
    write_json(
        run_manifest_path,
        {
            "run_manifest_schema_version": "e9-run-manifest-v1",
            "run_id": RUN_ID,
            "input_bundle": {"manifest_sha256": sha256_file(export_manifest_path)},
        },
    )
    status_path = returned / "runner_status.json"
    write_json(
        status_path,
        {
            "status_schema_version": "e9-runner-status-v1",
            "run_id": RUN_ID,
            "run_status": "completed",
            "expected_rows": 4,
            "written_rows": 4,
            "last_input_index": 3,
        },
    )

    def response(index: int, decision: str | None, failure: str | None = None) -> dict:
        status = "generation_failure" if failure else "indeterminate" if decision == "INDETERMINATE" else "completed"
        return {
            "run_id": RUN_ID,
            "input_index": index,
            "status": status,
            "parsed_decision": decision,
            "raw_content": None if failure else json.dumps({"decision": decision}),
            "generation_failure": None if failure is None else {"code": failure, "detail": "test"},
            "wall_latency_seconds": float(index + 1),
            "http_status": None if failure else 200,
            "ollama": {
                "model": None,
                "created_at": None,
                "done": None,
                "done_reason": None,
                "total_duration": None,
                "load_duration": None,
                "prompt_eval_count": None,
                "prompt_eval_duration": None,
                "eval_count": None,
                "eval_duration": None,
            },
        }

    responses_path = returned / "llm_responses.jsonl"
    write_jsonl(
        responses_path,
        [
            response(0, "ATTACK"),
            response(1, "ATTACK"),
            response(2, "INDETERMINATE"),
            response(3, None, "timeout"),
        ],
    )
    metrics = evaluate_layer2_run(
        export_manifest_path=export_manifest_path,
        evaluation_sidecar_path=sidecar_path,
        run_manifest_path=run_manifest_path,
        runner_status_path=status_path,
        responses_path=responses_path,
        output_dir=work_path / "evaluation",
    )
    assert metrics["counts"] == {
        "n_rows": 4,
        "llm_binary_decision_count": 2,
        "indeterminate_count": 1,
        "generation_failure_count": 1,
        "fallback_count": 2,
        "override_count": 1,
        "timeout_count": 1,
        "parsing_failure_count": 0,
        "schema_valid_count": 3,
    }
    assert metrics["gate_forced"]["error_count"] == 2
    assert metrics["end_to_end"]["error_count"] == 3
    assert metrics["transitions"]["gate_correct_final_error"] == 1
    assert metrics["transitions"]["gate_error_final_error"] == 2
