import numpy as np
import pandas as pd

from abstention_experiment.evaluation import budget_metrics, expected_aurc, final_status


def sample(confidence, errors):
    return pd.DataFrame({"confidence": confidence, "is_error": errors, "binary_label": [0, 0, 1, 1][:len(errors)], "predicted_label": [0, 1, 1, 0][:len(errors)]})


def test_expected_aurc_is_invariant_to_tie_order() -> None:
    first = sample([0.9, 0.8, 0.8, 0.6], [0, 0, 1, 1])
    second = first.iloc[[0, 2, 1, 3]].reset_index(drop=True)
    assert expected_aurc(first)[0]["aurc"] == expected_aurc(second)[0]["aurc"]


def test_budget_never_splits_a_tie_or_exceeds_target() -> None:
    frame = sample([0.51, 0.51, 0.9, 0.95], [1, 0, 0, 0])
    result = budget_metrics(frame, [0.25, 0.50])
    assert result[0]["n_abstained"] == 0
    assert result[1]["n_abstained"] == 2
    assert all(x["actual_abstention_rate"] <= x["target_abstention_rate"] for x in result)


def test_oracle_is_not_above_observed_aurc() -> None:
    metrics, _ = expected_aurc(sample([0.9, 0.8, 0.7, 0.6], [0, 1, 0, 1]))
    assert metrics["oracle_aurc"] <= metrics["aurc"]


def test_random_aurc_equals_full_coverage_risk() -> None:
    metrics, _ = expected_aurc(sample([0.9, 0.8, 0.7, 0.6], [0, 1, 0, 1]))
    assert metrics["random_aurc"] == metrics["full_coverage_risk"]
