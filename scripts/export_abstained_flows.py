#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from abstention_experiment.layer2_export import export_abstained_flow_bundle
from abstention_experiment.layer2_common import new_pilot_run_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export label-free abstained-flow JSONL for a separate Layer 2 environment."
    )
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument(
        "--feature-schema",
        type=Path,
        default=REPO_ROOT / "configs/llm/e9_input_feature_schema.json",
    )
    parser.add_argument(
        "--prompt",
        type=Path,
        default=REPO_ROOT / "configs/llm/e9_prompt_v1.json",
    )
    parser.add_argument("--run-id", help="Optional pre-generated E9 pilot run ID.")
    parser.add_argument("--method", required=True)
    parser.add_argument("--target-rate", type=float, required=True)
    parser.add_argument("--sample-size", type=int)
    parser.add_argument("--chunk-size", type=int, default=100_000)
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help="Environment-specific root under which <run_id>/export is created.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id = args.run_id or new_pilot_run_id()
    output_dir = args.output_root.resolve() / run_id / "export"
    manifest = export_abstained_flow_bundle(
        repo_root=REPO_ROOT,
        predictions_path=args.predictions.resolve(),
        metrics_path=args.metrics.resolve(),
        data_dir=args.data_dir.resolve(),
        feature_schema_path=args.feature_schema.resolve(),
        prompt_path=args.prompt.resolve(),
        run_id=run_id,
        method=args.method,
        target_rate=args.target_rate,
        output_dir=output_dir,
        sample_size=args.sample_size,
        chunk_size=args.chunk_size,
    )
    print(
        json.dumps(
            {"status": "exported", "run_id": run_id, "export_dir": str(output_dir), **manifest["counts"]},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
