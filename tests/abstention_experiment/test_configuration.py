from pathlib import Path

from abstention_experiment.configuration import load_config


def test_exp007_config_is_valid() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_config(root / "configs/exp/EXP-007.yaml", root)
    assert config.exp_id == "EXP-007"
    assert len(config.raw["training"]["candidates"]) == 8
    assert config.raw["training"]["num_boost_round"] == 3000
    assert config.raw["analysis"]["target_abstention_rates"] == [0.01, 0.02, 0.05, 0.10]


def test_exp008_config_fixes_seeds_candidate_and_verdict_bands() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_config(root / "configs/exp/EXP-008.yaml", root)
    assert config.exp_id == "EXP-008"
    assert config.raw["analysis"]["split_seeds"] == [43, 44, 45]
    assert config.raw["training"]["selected_candidate_id"] == "C06"
    assert config.raw["training"]["num_boost_round"] == 230
    assert config.raw["analysis"]["throughput_verdict"]["allowed_rate_multiplier_lower"] == 0.95
    assert config.raw["analysis"]["throughput_verdict"]["allowed_rate_multiplier_upper"] == 1.05
