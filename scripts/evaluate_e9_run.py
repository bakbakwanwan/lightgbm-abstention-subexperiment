#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from abstention_experiment.layer2_evaluation import evaluate_layer2_run


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a completed E9 Ollama response bundle.")
    parser.add_argument("--export-manifest", type=Path, required=True)
    parser.add_argument("--evaluation-sidecar", type=Path, required=True)
    parser.add_argument("--run-manifest", type=Path, required=True)
    parser.add_argument("--runner-status", type=Path, required=True)
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    metrics = evaluate_layer2_run(
        export_manifest_path=args.export_manifest.resolve(),
        evaluation_sidecar_path=args.evaluation_sidecar.resolve(),
        run_manifest_path=args.run_manifest.resolve(),
        runner_status_path=args.runner_status.resolve(),
        responses_path=args.responses.resolve(),
        output_dir=args.output_dir.resolve(),
    )
    print(json.dumps(metrics["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
