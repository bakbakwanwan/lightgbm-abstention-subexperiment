"""Generate RQ-focused figures from EXP-007 and EXP-008 result artifacts.

The figures compare budget-controlled abstention across group seeds 42--45 and
separately show why an absolute confidence threshold is not a stable workload
control.  The script reads existing result artifacts and does not retrain a
model or alter experiment metrics.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.ticker import PercentFormatter


ROOT = Path(__file__).resolve().parents[1]
EXP007_DIR = ROOT / "results" / "EXP-007"
EXP008_DIR = ROOT / "results" / "EXP-008"
FIGURE_DIR = EXP008_DIR / "figures"

SEED_COLORS = {
    42: "#2563EB",
    43: "#EA580C",
    44: "#15803D",
    45: "#7E22CE",
}
LIGHT_GRAY = "#CBD5E1"
TEXT = "#0F172A"
FAIL = "#DC2626"


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Malgun Gothic", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "figure.dpi": 120,
            "savefig.dpi": 300,
            "text.color": TEXT,
            "axes.labelcolor": TEXT,
            "axes.edgecolor": TEXT,
            "xtick.color": TEXT,
            "ytick.color": TEXT,
        }
    )


def clean_axis(ax: Axes, *, grid_axis: str = "y") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis=grid_axis, color=LIGHT_GRAY, linewidth=0.7, alpha=0.65)
    ax.set_axisbelow(True)


def seed42_budget_frame() -> pd.DataFrame:
    metrics = json.loads((EXP007_DIR / "metrics.json").read_text(encoding="utf-8"))
    analysis = metrics["analyses"]["group_seed42"]
    rows = []
    for budget in analysis["budgets"]:
        rows.append(
            {
                **budget,
                "seed": 42,
                "method": "group_seed42",
                "full_coverage_risk": analysis["full_coverage_risk"],
            }
        )
    return pd.DataFrame(rows)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    exp008 = pd.read_csv(EXP008_DIR / "offline_budget_summary.csv")
    exp008["full_coverage_risk"] = exp008["total_errors"] / exp008["n_test"]
    budgets = pd.concat([seed42_budget_frame(), exp008], ignore_index=True)
    budgets["risk_reduction"] = np.where(
        budgets["full_coverage_risk"] > 0,
        1.0 - budgets["selective_risk"] / budgets["full_coverage_risk"],
        np.nan,
    )
    fixed = pd.read_csv(EXP008_DIR / "fixed_threshold_summary.csv")
    overlap = pd.read_csv(EXP008_DIR / "class_overlap_summary.csv")
    distributions = pd.read_csv(EXP008_DIR / "prediction_distribution_summary.csv")
    return budgets, fixed, overlap, distributions


def validate_inputs(
    budgets: pd.DataFrame,
    fixed: pd.DataFrame,
    overlap: pd.DataFrame,
    distributions: pd.DataFrame,
) -> None:
    expected_seeds = {42, 43, 44, 45}
    expected_targets = [0.01, 0.02, 0.05, 0.10]
    assert set(budgets["seed"]) == expected_seeds
    for seed, frame in budgets.groupby("seed"):
        assert frame["target_abstention_rate"].tolist() == expected_targets, seed
        assert np.allclose(
            frame["accepted_errors"] + frame["abstained_errors"],
            frame["total_errors"],
        )
        recalculated_risk = frame["accepted_errors"] / frame["n_accepted"]
        assert np.allclose(recalculated_risk, frame["selective_risk"])
    assert set(fixed["seed"]) == {43, 44, 45}
    assert sorted(fixed["target_abstention_rate"].unique().tolist()) == [0.01, 0.05]
    assert set(overlap["scope"]) == {
        "with_class_overlap",
        "without_class_overlap",
        "class_overlap_only",
    }
    assert set(distributions["seed"]) == {43, 44, 45}


def with_zero_anchor(frame: pd.DataFrame, columns: dict[str, float]) -> pd.DataFrame:
    anchor = {name: value for name, value in columns.items()}
    anchor["actual_abstention_rate"] = 0.0
    return pd.concat([pd.DataFrame([anchor]), frame], ignore_index=True)


def draw_risk_reduction(ax: Axes, budgets: pd.DataFrame) -> None:
    for seed, frame in budgets.groupby("seed", sort=True):
        frame = with_zero_anchor(frame, {"risk_reduction": 0.0})
        ax.plot(
            frame["actual_abstention_rate"] * 100,
            frame["risk_reduction"] * 100,
            marker="o",
            linewidth=2.1,
            markersize=5,
            color=SEED_COLORS[int(seed)],
            label=f"seed {int(seed)}",
        )
    ax.set_title("유보율 증가에 따른 1차 판정 위험 감소")
    ax.set_xlabel("전체 test 대비 실제 유보율 (%)")
    ax.set_ylabel("전체 판정 대비 selective risk 감소율 (%)")
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0, 104)
    ax.set_xticks([0, 1, 2, 5, 10])
    ax.legend(frameon=False, loc="lower right", ncol=2)
    clean_axis(ax)


def draw_error_capture(ax: Axes, budgets: pd.DataFrame) -> None:
    for seed, frame in budgets.groupby("seed", sort=True):
        frame = with_zero_anchor(frame, {"error_capture_rate": 0.0})
        ax.plot(
            frame["actual_abstention_rate"] * 100,
            frame["error_capture_rate"] * 100,
            marker="o",
            linewidth=2.1,
            markersize=5,
            color=SEED_COLORS[int(seed)],
            label=f"seed {int(seed)}",
        )
        for row in frame.iloc[1:].itertuples(index=False):
            if row.target_abstention_rate == 0.01:
                ax.annotate(
                    f"{int(row.abstained_errors)}/{int(row.total_errors)}",
                    (row.actual_abstention_rate * 100, row.error_capture_rate * 100),
                    xytext=(0, 7 if int(seed) in (42, 45) else -12),
                    textcoords="offset points",
                    ha="center",
                    fontsize=7.5,
                    color=SEED_COLORS[int(seed)],
                )
    ax.plot([0, 10], [0, 10], color="#94A3B8", linestyle="--", linewidth=1.2, label="무작위 기대")
    ax.set_title("작은 유보 큐에 집중된 1차 판정 오류")
    ax.set_xlabel("전체 test 대비 실제 유보율 (%)")
    ax.set_ylabel("전체 오류 중 유보 구간 포착률 (%)")
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0, 105)
    ax.set_xticks([0, 1, 2, 5, 10])
    ax.legend(frameon=False, loc="lower right", ncol=2)
    clean_axis(ax)


def draw_attack_coverage(ax: Axes, budgets: pd.DataFrame) -> None:
    for seed, frame in budgets.groupby("seed", sort=True):
        frame = with_zero_anchor(frame, {"attack_coverage": 1.0})
        ax.plot(
            frame["actual_abstention_rate"] * 100,
            frame["attack_coverage"] * 100,
            marker="o",
            linewidth=2.1,
            markersize=5,
            color=SEED_COLORS[int(seed)],
            label=f"seed {int(seed)}",
        )
    ax.set_title("위험 감소와 함께 지불하는 공격 coverage 비용")
    ax.set_xlabel("전체 test 대비 실제 유보율 (%)")
    ax.set_ylabel("1차 모델이 직접 판정하는 공격 비율 (%)")
    ax.set_xlim(0, 10.5)
    ax.set_ylim(70, 101.5)
    ax.set_xticks([0, 1, 2, 5, 10])
    ax.legend(frameon=False, loc="lower left", ncol=2)
    clean_axis(ax)


def draw_fixed_threshold(ax: Axes, fixed: pd.DataFrame) -> None:
    seeds = sorted(fixed["seed"].unique())
    targets = [0.01, 0.05]
    x = np.arange(len(seeds), dtype=float)
    width = 0.34
    colors = ["#38BDF8", "#F97316"]
    for offset_index, (target, color) in enumerate(zip(targets, colors, strict=True)):
        frame = fixed.loc[fixed["target_abstention_rate"] == target].set_index("seed").loc[seeds]
        positions = x + (offset_index - 0.5) * width
        values = frame["actual_abstention_rate"].to_numpy() * 100
        bars = ax.bar(
            positions,
            values,
            width=width,
            color=color,
            label=f"EXP-007 {target:.0%} 고정 경계",
            alpha=0.9,
        )
        ax.bar_label(bars, labels=[f"{value:.2f}%" for value in values], padding=3, fontsize=8)
        lower = float(frame["allowed_abstention_rate_lower"].iloc[0]) * 100
        upper = float(frame["allowed_abstention_rate_upper"].iloc[0]) * 100
        ax.axhspan(lower, upper, color=color, alpha=0.09)
        ax.axhline(target * 100, color=color, linestyle="--", linewidth=1.1)
    ax.set_title("EXP-007 절대 confidence 경계의 처리량 이식")
    ax.set_xlabel("새 그룹 분할")
    ax.set_ylabel("실제 유보율 (%)")
    ax.set_xticks(x, [f"seed {seed}" for seed in seeds])
    ax.set_ylim(0, 6.7)
    ax.legend(frameon=False, loc="upper left")
    clean_axis(ax)


def draw_overlap_effect(ax: Axes, overlap: pd.DataFrame) -> None:
    scopes = ["with_class_overlap", "without_class_overlap"]
    scope_labels = ["전체 test", "class overlap 제외"]
    colors = ["#64748B", "#0EA5E9"]
    seeds = [43, 44, 45]
    x = np.arange(len(seeds), dtype=float)
    width = 0.34
    for index, (scope, label, color) in enumerate(zip(scopes, scope_labels, colors, strict=True)):
        frame = (
            overlap.loc[overlap["scope"] == scope]
            .drop_duplicates(subset=["seed", "scope"])
            .set_index("seed")
            .loc[seeds]
        )
        ratio = frame["aurc"] / frame["random_aurc"]
        positions = x + (index - 0.5) * width
        bars = ax.bar(positions, ratio, width=width, color=color, label=label)
        ax.bar_label(bars, labels=[f"{value:.3f}" for value in ratio], padding=3, fontsize=8)

    exp007_ratio = 0.0064163586320881
    stability_limit = exp007_ratio * 3
    ax.axhline(
        stability_limit,
        color=FAIL,
        linestyle="--",
        linewidth=1.4,
        label=f"사전 안정성 한계 ({stability_limit:.3f})",
    )
    ax.set_title("분해 불가능한 class overlap이 AURC 판정에 준 영향")
    ax.set_xlabel("새 그룹 분할")
    ax.set_ylabel("AURC / random AURC (낮을수록 좋음)")
    ax.set_xticks(x, [f"seed {seed}" for seed in seeds])
    ax.set_ylim(0, 0.038)
    ax.legend(frameon=False, loc="upper right")
    clean_axis(ax)


def draw_confidence_saturation(ax: Axes, distributions: pd.DataFrame) -> None:
    seeds = distributions["seed"].astype(int).tolist()
    x = np.arange(len(seeds), dtype=float)
    saturated = distributions["confidence_ge_0_99999_rate"].to_numpy() * 100
    middle = distributions["p_attack_0_01_to_0_99_rate"].to_numpy() * 100
    bars1 = ax.bar(x, saturated, 0.56, color="#7E22CE", label="confidence ≥ 0.99999")
    ax.bar_label(bars1, labels=[f"{value:.1f}%" for value in saturated], padding=3, fontsize=8)
    ax2 = ax.twinx()
    line = ax2.plot(
        x,
        middle,
        color="#F59E0B",
        marker="o",
        linewidth=2.2,
        label="p_attack ∈ [0.01, 0.99]",
    )[0]
    for position, value in zip(x, middle, strict=True):
        ax2.annotate(
            f"{value:.2f}%",
            (position, value),
            xytext=(0, 7),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color="#B45309",
        )
    ax.set_title("다른 분할에서도 지속된 confidence 포화")
    ax.set_xlabel("새 그룹 분할")
    ax.set_ylabel("confidence ≥ 0.99999인 test 행 (%)", color="#7E22CE")
    ax2.set_ylabel("p_attack 중간 구간의 test 행 (%)", color="#B45309")
    ax.set_xticks(x)
    ax.set_xticklabels([f"seed {seed}" for seed in seeds])
    ax.set_ylim(0, 72)
    ax2.set_ylim(0, 0.85)
    ax.legend(handles=[bars1, line], labels=["confidence ≥ 0.99999", "p_attack ∈ [0.01, 0.99]"], frameon=False, loc="upper center")
    clean_axis(ax)
    ax2.spines["top"].set_visible(False)
    ax2.grid(False)


def save_figure(fig: plt.Figure, stem: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "svg"):
        fig.savefig(FIGURE_DIR / f"{stem}.{suffix}", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def single_figure(draw, filename: str, *args) -> None:
    fig, ax = plt.subplots(figsize=(8.4, 5.3), constrained_layout=True)
    draw(ax, *args)
    save_figure(fig, filename)


def create_figures(
    budgets: pd.DataFrame,
    fixed: pd.DataFrame,
    overlap: pd.DataFrame,
    distributions: pd.DataFrame,
) -> None:
    single_figure(draw_risk_reduction, "budget_risk_reduction", budgets)
    single_figure(draw_error_capture, "budget_error_capture", budgets)
    single_figure(draw_attack_coverage, "budget_attack_coverage", budgets)
    single_figure(draw_fixed_threshold, "fixed_threshold_portability", fixed)
    single_figure(draw_overlap_effect, "class_overlap_effect", overlap)
    single_figure(draw_confidence_saturation, "confidence_saturation", distributions)

    fig, axes = plt.subplots(2, 2, figsize=(15, 10), constrained_layout=True)
    draw_risk_reduction(axes[0, 0], budgets)
    draw_error_capture(axes[0, 1], budgets)
    draw_attack_coverage(axes[1, 0], budgets)
    draw_fixed_threshold(axes[1, 1], fixed)
    fig.suptitle(
        "EXP-007·008: 유보 예산에 따른 위험–처리량 관계",
        fontsize=17,
        fontweight="bold",
    )
    save_figure(fig, "exp008_rq_summary")


def main() -> None:
    configure_style()
    budgets, fixed, overlap, distributions = load_inputs()
    validate_inputs(budgets, fixed, overlap, distributions)
    create_figures(budgets, fixed, overlap, distributions)
    for path in sorted(FIGURE_DIR.glob("*")):
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
