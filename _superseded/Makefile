.PHONY: prep-dataset prep-dataset-loao test

CONFIG := configs/exp/cicids_prep.yaml

# make 자체가 이 Windows 환경에 설치되지 않아(choco 권한 문제) 검증하지 못했다.
# 설치되면 그대로 쓸 수 있도록 작성해두되, 지금은 아래 명령을 uv로 직접 호출해
# 안내한다: uv run python scripts/build_dataset.py --config configs/exp/cicids_prep.yaml

prep-dataset:
	uv run python scripts/build_dataset.py --config $(CONFIG)

prep-dataset-loao:
	uv run python scripts/build_dataset.py --config $(CONFIG) --loao-only

test:
	uv run python -m pytest -q tests/cicids_prep
