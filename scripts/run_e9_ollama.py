#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from abstention_experiment.layer2_runtime import run_ollama_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Run strict E9 JSON classification with local Ollama.")
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434/api/chat")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    status = run_ollama_bundle(
        bundle_root=args.bundle_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        run_id=args.run_id,
        repo_root=args.repo_root.resolve(),
        endpoint=args.endpoint,
    )
    print(json.dumps(status, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
