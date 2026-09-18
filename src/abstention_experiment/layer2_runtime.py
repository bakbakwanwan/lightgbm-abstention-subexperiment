from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import platform
import re
import socket
import subprocess
import time
from typing import Any, Callable
from urllib import error, request
from urllib.parse import urlsplit

from .data import sha256_file
from .layer2_common import (
    read_json,
    read_jsonl,
    require_valid_run_id,
    resolve_bundle_path,
    utc_now,
    write_json,
)
from .layer2_export import PROMPT_FORBIDDEN_FIELDS


DECISIONS = {"BENIGN", "ATTACK", "INDETERMINATE"}
CONTINUABLE_FAILURES = {
    "timeout",
    "generation_incomplete",
    "empty_response",
    "decision_json_invalid",
    "decision_schema_invalid",
}
SYSTEMIC_FAILURES = {
    "connection_error",
    "http_error",
    "ollama_error",
    "api_response_invalid",
}
ALL_FAILURES = CONTINUABLE_FAILURES | SYSTEMIC_FAILURES
DECISION_FORMAT = {
    "type": "object",
    "properties": {"decision": {"type": "string", "enum": sorted(DECISIONS)}},
    "required": ["decision"],
    "additionalProperties": False,
}
GENERATION = {
    "num_ctx": 4096,
    "temperature": 0,
    "top_p": 1.0,
    "num_predict": 64,
    "seed": 42,
    "concurrency": 1,
    "timeout_seconds": 60,
    "stream": False,
    "keep_alive": "5m",
    "repeat_penalty": 1,
    "penalize_newline": False,
    "stop": ["<start_of_turn>", "<end_of_turn>"],
}
EXPECTED_MODEL = {
    "version": "0.34.1",
    "model_tag": "gemma:7b-instruct",
    "model_id": "a72c7f4d0a15",
    "base_blob_sha256": "ef311de6af9db043d51ca4b1e766c28e0a1ac41d60420fed5e001dc470c64b77",
    "architecture": "gemma",
    "parameters": "9B",
    "quantization": "Q4_0",
    "model_context_length": 8192,
}


class BundleValidationError(RuntimeError):
    pass


class RunIncompleteError(RuntimeError):
    pass


@dataclass(frozen=True)
class PromptAsset:
    prompt_version: str
    system_prompt: str
    user_prompt_template: str
    placeholder: str

    def render(self, flow_features: dict[str, Any]) -> str:
        rendered = json.dumps(
            flow_features,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        return self.user_prompt_template.replace(self.placeholder, rendered)


def load_prompt_asset(path: Path) -> PromptAsset:
    payload = read_json(path)
    expected = {
        "prompt_version",
        "system_prompt",
        "user_prompt_template",
        "flow_features_placeholder",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("Prompt asset keys do not match e9-v1")
    placeholder = payload["flow_features_placeholder"]
    if placeholder != "{{FLOW_FEATURES_JSON}}":
        raise ValueError("Unexpected flow feature placeholder")
    if payload["user_prompt_template"].count(placeholder) != 1:
        raise ValueError("Prompt placeholder must occur exactly once")
    if payload["prompt_version"] != "e9-v1":
        raise ValueError("Unexpected prompt version")
    return PromptAsset(
        prompt_version=payload["prompt_version"],
        system_prompt=payload["system_prompt"],
        user_prompt_template=payload["user_prompt_template"],
        placeholder=placeholder,
    )


def _check(passed: bool, observed: Any, expected: Any, reason: str | None = None) -> dict[str, Any]:
    return {
        "passed": bool(passed),
        "observed": observed,
        "expected": expected,
        "reason": None if passed else reason,
    }


def validate_transfer_bundle(bundle_root: Path, output_path: Path | None = None) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}
    manifest_path = bundle_root / "manifest.json"
    try:
        manifest = read_json(manifest_path)
        if not isinstance(manifest, dict):
            raise ValueError("manifest is not an object")
        checks["manifest_parse"] = _check(True, "valid_json_object", "valid_json_object")
    except Exception as exc:
        manifest = None
        checks["manifest_parse"] = _check(False, "invalid", "valid_json_object", type(exc).__name__)

    manifest_sha256 = sha256_file(manifest_path) if manifest_path.is_file() else None
    input_rows: list[dict[str, Any]] = []
    if manifest is not None:
        try:
            artifacts = manifest["artifacts"]
            input_meta = artifacts["llm_inputs"]
            schema_meta = artifacts["feature_schema"]
            prompt_meta = artifacts["prompt"]
            input_path = resolve_bundle_path(bundle_root, input_meta["path"])
            schema_path = resolve_bundle_path(bundle_root, schema_meta["path"])
            prompt_path = resolve_bundle_path(bundle_root, prompt_meta["path"])
        except Exception as exc:
            checks["artifact_references"] = _check(False, "invalid", "valid_relative_paths", type(exc).__name__)
        else:
            checks["artifact_references"] = _check(True, "valid_relative_paths", "valid_relative_paths")
            for name, path, metadata in (
                ("input_jsonl_sha256", input_path, input_meta),
                ("feature_schema_sha256", schema_path, schema_meta),
                ("prompt_sha256", prompt_path, prompt_meta),
            ):
                observed = sha256_file(path) if path.is_file() else None
                expected_hash = metadata.get("sha256")
                checks[name] = _check(
                    observed == expected_hash,
                    observed,
                    expected_hash,
                    "missing_or_hash_mismatch",
                )
            try:
                schema = read_json(schema_path)
                features = schema["features"]
                schema_valid = (
                    isinstance(features, list)
                    and len(features) == 59
                    and len(set(features)) == 59
                    and not (set(features) & PROMPT_FORBIDDEN_FIELDS)
                    and schema.get("schema_version") == schema_meta.get("version")
                )
                checks["feature_schema"] = _check(
                    schema_valid,
                    {"version": schema.get("schema_version"), "feature_count": len(features)},
                    {"version": schema_meta.get("version"), "feature_count": 59},
                    "feature_schema_contract_mismatch",
                )
            except Exception as exc:
                features = []
                checks["feature_schema"] = _check(False, "invalid", "e9_input_schema", type(exc).__name__)
            try:
                prompt = load_prompt_asset(prompt_path)
                prompt_valid = prompt.prompt_version == prompt_meta.get("version")
                checks["prompt_asset"] = _check(
                    prompt_valid,
                    prompt.prompt_version,
                    prompt_meta.get("version"),
                    "prompt_version_mismatch",
                )
            except Exception as exc:
                checks["prompt_asset"] = _check(False, "invalid", "e9-v1", type(exc).__name__)
            try:
                input_rows = read_jsonl(input_path)
                checks["input_jsonl_parse"] = _check(True, len(input_rows), input_meta.get("rows"))
            except Exception as exc:
                checks["input_jsonl_parse"] = _check(False, "invalid", input_meta.get("rows"), type(exc).__name__)
                input_rows = []
            expected_count = manifest.get("counts", {}).get("exported_rows")
            checks["row_count"] = _check(
                len(input_rows) == expected_count == input_meta.get("rows"),
                len(input_rows),
                expected_count,
                "row_count_mismatch",
            )
            indices = [row.get("input_index") for row in input_rows]
            checks["input_index"] = _check(
                indices == list(range(len(input_rows))),
                {"rows": len(indices), "unique": len(set(indices)) if all(isinstance(x, int) for x in indices) else None},
                {"start": 0, "end": len(indices) - 1, "unique": len(indices)},
                "indices_not_unique_and_contiguous",
            )
            row_contract_ok = True
            forbidden_found: set[str] = set()
            for row in input_rows:
                if set(row) != {"input_index", "payload"} or not isinstance(row.get("payload"), dict):
                    row_contract_ok = False
                    continue
                payload = row["payload"]
                if set(payload) != {"flow_features"} or not isinstance(payload.get("flow_features"), dict):
                    row_contract_ok = False
                    continue
                keys = list(payload["flow_features"])
                forbidden_found.update(set(keys) & PROMPT_FORBIDDEN_FIELDS)
                if keys != features:
                    row_contract_ok = False
            checks["feature_rows"] = _check(
                row_contract_ok,
                {"rows": len(input_rows), "feature_count": len(features)},
                {"rows": len(input_rows), "feature_count": 59, "ordered": True},
                "input_row_or_feature_order_mismatch",
            )
            checks["forbidden_fields"] = _check(
                not forbidden_found,
                sorted(forbidden_found),
                [],
                "prompt_forbidden_fields_present",
            )

    passed_count = sum(item["passed"] for item in checks.values())
    result = {
        "validation_schema_version": "e9-bundle-validation-v1",
        "passed": bool(checks) and passed_count == len(checks),
        "validated_at": utc_now(),
        "manifest_sha256": manifest_sha256,
        "checks": checks,
        "summary": {
            "check_count": len(checks),
            "passed_count": passed_count,
            "failed_count": len(checks) - passed_count,
        },
    }
    if output_path is not None:
        write_json(output_path, result)
    return result


class OllamaHttpClient:
    def __init__(self, endpoint: str, timeout_seconds: float) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def _json_request(self, url: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8")
            value = json.loads(body)
            if not isinstance(value, dict):
                raise ValueError("Ollama response is not an object")
            return int(response.status), value

    def chat(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        return self._json_request(self.endpoint, payload)

    def metadata(self, model_tag: str) -> dict[str, Any]:
        base = self.endpoint.rsplit("/api/chat", 1)[0]
        _, version = self._json_request(f"{base}/api/version")
        _, tags = self._json_request(f"{base}/api/tags")
        _, shown = self._json_request(f"{base}/api/show", {"model": model_tag})
        tag_rows = tags.get("models", [])
        selected = next((row for row in tag_rows if row.get("name") == model_tag), {})
        details = shown.get("details", {})
        model_info = shown.get("model_info", {})
        return {
            "version": version.get("version"),
            "model_tag": model_tag,
            "model_id": _model_id(selected.get("digest")),
            "base_blob_sha256": _base_blob_sha(shown.get("modelfile")),
            "architecture": details.get("family"),
            "parameters": details.get("parameter_size"),
            "quantization": details.get("quantization_level"),
            "model_context_length": model_info.get("gemma.context_length"),
        }


def _base_blob_sha(modelfile: Any) -> str | None:
    if not isinstance(modelfile, str):
        return None
    for line in modelfile.splitlines():
        stripped = line.strip()
        if stripped.startswith("FROM "):
            match = re.search(r"sha256[:-]([0-9a-fA-F]{64})", stripped)
            if match:
                return match.group(1).lower()
    return None


def _model_id(digest: Any) -> str | None:
    if not isinstance(digest, str) or not digest:
        return None
    value = digest.rsplit(":", 1)[-1]
    return value[:12] or None


def _validate_endpoint(endpoint: str) -> None:
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.path != "/api/chat"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Ollama endpoint must be an unauthenticated local HTTP /api/chat URL")


def _verify_model_metadata(actual: dict[str, Any]) -> None:
    mismatches = {
        key: (actual.get(key), expected)
        for key, expected in EXPECTED_MODEL.items()
        if actual.get(key) != expected
    }
    if mismatches:
        raise RuntimeError(f"Ollama model metadata differs from the E9 contract: {mismatches}")


def _git_state(repo_root: Path) -> tuple[str | None, bool | None]:
    try:
        safe = f"safe.directory={repo_root.resolve().as_posix()}"
        commit = subprocess.check_output(
            ["git", "-c", safe, "rev-parse", "HEAD"], cwd=repo_root, text=True
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "-c", safe, "status", "--porcelain"], cwd=repo_root, text=True
            ).strip()
        )
        return commit, dirty
    except (OSError, subprocess.SubprocessError):
        return None, None


def _environment() -> dict[str, Any]:
    return {
        "os": platform.system() or None,
        "os_version": platform.version() or None,
        "architecture": platform.machine() or None,
        "cpu": platform.processor() or None,
        "memory_bytes": None,
        "gpu": None,
        "gpu_memory_bytes": None,
    }


def _manifest(
    *,
    run_id: str,
    bundle_root: Path,
    export_manifest: dict[str, Any],
    repo_root: Path,
    endpoint: str,
    model_metadata: dict[str, Any],
) -> dict[str, Any]:
    artifacts = export_manifest["artifacts"]
    commit, dirty = _git_state(repo_root)
    lock_path = repo_root / "uv.lock"
    return {
        "run_manifest_schema_version": "e9-run-manifest-v1",
        "run_id": run_id,
        "created_at": utc_now(),
        "input_bundle": {
            "manifest_sha256": sha256_file(bundle_root / "manifest.json"),
            "input_path": artifacts["llm_inputs"]["path"],
            "input_sha256": artifacts["llm_inputs"]["sha256"],
            "input_rows": artifacts["llm_inputs"]["rows"],
            "feature_schema_path": artifacts["feature_schema"]["path"],
            "feature_schema_version": artifacts["feature_schema"]["version"],
            "feature_schema_sha256": artifacts["feature_schema"]["sha256"],
            "prompt_path": artifacts["prompt"]["path"],
            "prompt_version": artifacts["prompt"]["version"],
            "prompt_sha256": artifacts["prompt"]["sha256"],
        },
        "runner": {
            "runner_version": "e9-ollama-runner-v1",
            "git_commit": commit,
            "working_tree_dirty": dirty,
            "python_version": platform.python_version(),
            "dependency_lock_sha256": sha256_file(lock_path) if lock_path.is_file() else None,
        },
        "ollama": {**model_metadata, "endpoint": endpoint},
        "generation": GENERATION,
        "environment": _environment(),
    }


def _response_ollama(api: dict[str, Any] | None) -> dict[str, Any]:
    value = api or {}
    return {
        "model": value.get("model"),
        "created_at": value.get("created_at"),
        "done": value.get("done"),
        "done_reason": value.get("done_reason"),
        "total_duration": value.get("total_duration"),
        "load_duration": value.get("load_duration"),
        "prompt_eval_count": value.get("prompt_eval_count"),
        "prompt_eval_duration": value.get("prompt_eval_duration"),
        "eval_count": value.get("eval_count"),
        "eval_duration": value.get("eval_duration"),
    }


def _failure_row(
    run_id: str,
    input_index: int,
    code: str,
    latency: float,
    *,
    detail: str,
    http_status: int | None = None,
    api: dict[str, Any] | None = None,
    raw_content: str | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "input_index": input_index,
        "status": "generation_failure",
        "parsed_decision": None,
        "raw_content": raw_content,
        "generation_failure": {"code": code, "detail": detail[:300]},
        "wall_latency_seconds": latency,
        "http_status": http_status,
        "ollama": _response_ollama(api),
    }


def _parse_api_response(
    run_id: str,
    input_index: int,
    http_status: int,
    api: dict[str, Any],
    latency: float,
) -> dict[str, Any]:
    if http_status < 200 or http_status >= 300:
        return _failure_row(
            run_id, input_index, "http_error", latency,
            detail=f"http_status_{http_status}", http_status=http_status,
            api=api if isinstance(api, dict) else None,
        )
    if not isinstance(api, dict):
        return _failure_row(
            run_id, input_index, "api_response_invalid", latency,
            detail="api_response_is_not_object", http_status=http_status,
        )
    if isinstance(api.get("error"), str):
        message = api.get("message")
        raw_content = message.get("content") if isinstance(message, dict) and isinstance(message.get("content"), str) else None
        return _failure_row(
            run_id, input_index, "ollama_error", latency,
            detail=api["error"], http_status=http_status, api=api, raw_content=raw_content,
        )
    message = api.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        return _failure_row(
            run_id, input_index, "api_response_invalid", latency,
            detail="missing_message_content", http_status=http_status, api=api,
        )
    content = message["content"]
    if api.get("done") is not True or api.get("done_reason") not in (None, "stop"):
        return _failure_row(
            run_id, input_index, "generation_incomplete", latency,
            detail="done_or_done_reason_invalid", http_status=http_status, api=api,
            raw_content=content,
        )
    if not content:
        return _failure_row(
            run_id, input_index, "empty_response", latency,
            detail="empty_message_content", http_status=http_status, api=api,
            raw_content=content,
        )
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return _failure_row(
            run_id, input_index, "decision_json_invalid", latency,
            detail="message_content_is_not_json", http_status=http_status, api=api,
            raw_content=content,
        )
    if not isinstance(parsed, dict) or set(parsed) != {"decision"} or parsed.get("decision") not in DECISIONS:
        return _failure_row(
            run_id, input_index, "decision_schema_invalid", latency,
            detail="decision_object_contract_mismatch", http_status=http_status, api=api,
            raw_content=content,
        )
    decision = parsed["decision"]
    return {
        "run_id": run_id,
        "input_index": input_index,
        "status": "indeterminate" if decision == "INDETERMINATE" else "completed",
        "parsed_decision": decision,
        "raw_content": content,
        "generation_failure": None,
        "wall_latency_seconds": latency,
        "http_status": http_status,
        "ollama": _response_ollama(api),
    }


def _request_payload(prompt: PromptAsset, flow_features: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": EXPECTED_MODEL["model_tag"],
        "messages": [
            {"role": "system", "content": prompt.system_prompt},
            {"role": "user", "content": prompt.render(flow_features)},
        ],
        "format": DECISION_FORMAT,
        "stream": GENERATION["stream"],
        "keep_alive": GENERATION["keep_alive"],
        "options": {
            "num_ctx": GENERATION["num_ctx"],
            "temperature": GENERATION["temperature"],
            "top_p": GENERATION["top_p"],
            "num_predict": GENERATION["num_predict"],
            "seed": GENERATION["seed"],
            "repeat_penalty": GENERATION["repeat_penalty"],
            "penalize_newline": GENERATION["penalize_newline"],
            "stop": GENERATION["stop"],
        },
    }


def run_ollama_bundle(
    *,
    bundle_root: Path,
    output_dir: Path,
    run_id: str,
    repo_root: Path,
    endpoint: str = "http://127.0.0.1:11434/api/chat",
    chat: Callable[[dict[str, Any]], tuple[int, dict[str, Any]]] | None = None,
    model_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    require_valid_run_id(run_id)
    _validate_endpoint(endpoint)
    if output_dir.exists():
        raise FileExistsError(f"Runner output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    validation = validate_transfer_bundle(bundle_root, output_dir / "bundle_validation.json")
    if not validation["passed"]:
        raise BundleValidationError("Transfer bundle validation failed")

    export_manifest = read_json(bundle_root / "manifest.json")
    if export_manifest.get("run_id") != run_id:
        raise BundleValidationError("run_id differs from the export manifest")
    client = OllamaHttpClient(endpoint, GENERATION["timeout_seconds"])
    actual_metadata = model_metadata if model_metadata is not None else client.metadata(EXPECTED_MODEL["model_tag"])
    _verify_model_metadata(actual_metadata)
    run_manifest = _manifest(
        run_id=run_id,
        bundle_root=bundle_root,
        export_manifest=export_manifest,
        repo_root=repo_root,
        endpoint=endpoint,
        model_metadata=actual_metadata,
    )
    write_json(output_dir / "run_manifest.json", run_manifest)

    artifacts = export_manifest["artifacts"]
    inputs = read_jsonl(resolve_bundle_path(bundle_root, artifacts["llm_inputs"]["path"]))
    prompt = load_prompt_asset(resolve_bundle_path(bundle_root, artifacts["prompt"]["path"]))
    partial_path = output_dir / "llm_responses.partial.jsonl"
    status_path = output_dir / "runner_status.json"
    started = utc_now()
    status = {
        "status_schema_version": "e9-runner-status-v1",
        "run_id": run_id,
        "run_status": "running",
        "expected_rows": len(inputs),
        "written_rows": 0,
        "last_input_index": None,
        "started_at": started,
        "finished_at": None,
        "reason": None,
    }
    write_json(status_path, status)
    chat_call = chat or client.chat
    abort_code: str | None = None
    try:
        with partial_path.open("x", encoding="utf-8", newline="\n") as handle:
            for row in inputs:
                input_index = int(row["input_index"])
                payload = _request_payload(prompt, row["payload"]["flow_features"])
                began = time.perf_counter()
                try:
                    http_status, api = chat_call(payload)
                    latency = time.perf_counter() - began
                    response_row = _parse_api_response(run_id, input_index, http_status, api, latency)
                except (TimeoutError, socket.timeout):
                    latency = time.perf_counter() - began
                    response_row = _failure_row(
                        run_id, input_index, "timeout", latency, detail="request_timeout"
                    )
                except error.HTTPError as exc:
                    latency = time.perf_counter() - began
                    error_api: dict[str, Any] | None = None
                    error_content: str | None = None
                    try:
                        decoded = json.loads(exc.read().decode("utf-8"))
                        if isinstance(decoded, dict):
                            error_api = decoded
                            message = decoded.get("message")
                            if isinstance(message, dict) and isinstance(message.get("content"), str):
                                error_content = message["content"]
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                        pass
                    response_row = _failure_row(
                        run_id, input_index, "http_error", latency,
                        detail=f"http_status_{exc.code}", http_status=int(exc.code),
                        api=error_api, raw_content=error_content,
                    )
                except error.URLError as exc:
                    latency = time.perf_counter() - began
                    if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                        response_row = _failure_row(
                            run_id, input_index, "timeout", latency, detail="request_timeout"
                        )
                    else:
                        response_row = _failure_row(
                            run_id, input_index, "connection_error", latency,
                            detail=type(exc.reason).__name__,
                        )
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                    latency = time.perf_counter() - began
                    response_row = _failure_row(
                        run_id, input_index, "api_response_invalid", latency,
                        detail="api_response_could_not_be_decoded",
                    )
                handle.write(json.dumps(response_row, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
                handle.write("\n")
                handle.flush()
                status["written_rows"] += 1
                status["last_input_index"] = input_index
                write_json(status_path, status)
                failure = response_row["generation_failure"]
                if failure is not None and failure["code"] in SYSTEMIC_FAILURES:
                    abort_code = failure["code"]
                    break
    except Exception as exc:
        status["run_status"] = "incomplete"
        status["finished_at"] = utc_now()
        status["reason"] = f"unexpected_runner_exception:{type(exc).__name__}"
        write_json(status_path, status)
        raise

    if abort_code is not None or status["written_rows"] != len(inputs):
        status["run_status"] = "incomplete"
        status["finished_at"] = utc_now()
        status["reason"] = abort_code or "response_count_mismatch"
        write_json(status_path, status)
        raise RunIncompleteError(f"Ollama run incomplete: {status['reason']}")

    final_path = output_dir / "llm_responses.jsonl"
    partial_path.replace(final_path)
    status["run_status"] = "completed"
    status["finished_at"] = utc_now()
    write_json(status_path, status)
    return status
