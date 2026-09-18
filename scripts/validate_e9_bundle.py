#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from abstention_experiment.layer2_runtime import validate_transfer_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an E9 transfer bundle before LLM use.")
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate_transfer_bundle(args.bundle_dir.resolve(), args.output.resolve())
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
