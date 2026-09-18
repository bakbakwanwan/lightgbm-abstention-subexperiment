#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from abstention_experiment.layer2_package import package_transfer_bundle


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package only label-free E9 transfer members into a ZIP archive."
    )
    parser.add_argument("--export-dir", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    result = package_transfer_bundle(args.export_dir.resolve(), args.archive.resolve())
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
