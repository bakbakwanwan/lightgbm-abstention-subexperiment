from pathlib import Path

from abstention_experiment.configuration import load_config


def test_exp007_config_is_valid() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_config(root / "configs/exp/EXP-007.yaml", root)
    assert config.exp_id == "EXP-007"
    assert len(config.raw["training"]["candidates"]) == 8
    assert config.raw["training"]["num_boost_round"] == 3000
    assert config.raw["analysis"]["target_abstention_rates"] == [0.01, 0.02, 0.05, 0.10]
