#!/usr/bin/env python
"""CICIDS2017 데이터 준비 파이프라인 CLI (tasks/split_protocol_proposal.md +
docs/stage1_briefing.md 통합 구현).

사용:
    uv run python scripts/build_dataset.py --config configs/exp/cicids_prep.yaml
    uv run python scripts/build_dataset.py --config configs/exp/cicids_prep.yaml --loao-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from cicids_prep import pipeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path, help="YAML config 경로")
    parser.add_argument(
        "--loao-only",
        action="store_true",
        help="그룹/분할 계산을 재사용하고 LOAO 후처리(+가지치기/클리핑 재계산)만 다시 실행",
    )
    parser.add_argument(
        "--loao-target-labels",
        nargs="*",
        default=None,
        help="config의 loao_target_labels를 CLI에서 override",
    )
    parser.add_argument("--bucket-seconds", type=int, default=None)
    parser.add_argument("--random-seed", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = pipeline.load_config(args.config)

    if args.loao_target_labels is not None:
        cfg["loao_target_labels"] = args.loao_target_labels
    if args.bucket_seconds is not None:
        cfg["bucket_seconds"] = args.bucket_seconds
    if args.random_seed is not None:
        cfg["random_seed"] = args.random_seed

    if args.loao_only:
        return pipeline.run_loao_only(cfg, REPO_ROOT)
    return pipeline.run_full(cfg, REPO_ROOT)


if __name__ == "__main__":
    sys.exit(main())
