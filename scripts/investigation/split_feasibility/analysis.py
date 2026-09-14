"""Deterministic split-feasibility helpers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd


def stable_label_seed(base_seed: int, label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    offset = int.from_bytes(digest[:4], "little")
    return (base_seed + offset) % (2**32)


def closest_prefix_selection(
    group_hashes: np.ndarray,
    group_sizes: np.ndarray,
    target_rows: int,
    seed: int,
) -> np.ndarray:
    """Select whole groups close to the row target with deterministic shuffling."""
    if len(group_hashes) == 0 or target_rows <= 0:
        return np.array([], dtype=np.uint64)
    if target_rows >= int(group_sizes.sum()):
        return group_hashes.astype(np.uint64, copy=True)

    rng = np.random.default_rng(seed)
    singleton = np.flatnonzero(group_sizes == 1)
    non_singleton = np.flatnonzero(group_sizes > 1)
    singleton = rng.permutation(singleton)
    non_singleton = rng.permutation(non_singleton)

    selected: list[int] = []
    skipped: list[int] = []
    selected_rows = 0
    for position in non_singleton:
        size = int(group_sizes[position])
        if selected_rows + size <= target_rows:
            selected.append(int(position))
            selected_rows += size
        else:
            skipped.append(int(position))

    singleton_needed = min(target_rows - selected_rows, len(singleton))
    if singleton_needed > 0:
        selected.extend(singleton[:singleton_needed].astype(int).tolist())
        selected_rows += singleton_needed

    if selected_rows < target_rows and skipped:
        best_overshoot = min(
            skipped,
            key=lambda position: (
                abs(selected_rows + int(group_sizes[position]) - target_rows),
                int(group_sizes[position]),
            ),
        )
        if abs(selected_rows + int(group_sizes[best_overshoot]) - target_rows) < abs(
            selected_rows - target_rows
        ):
            selected.append(best_overshoot)

    return group_hashes[np.asarray(selected, dtype=np.int64)].astype(
        np.uint64, copy=False
    )


def choose_conflict_test_groups(
    conflict_matrix: pd.DataFrame,
    target_fraction: float = 0.25,
    seed: int = 42,
) -> tuple[np.ndarray, dict]:
    """Choose whole multi-label groups near their per-label row targets."""
    if conflict_matrix.empty:
        return np.array([], dtype=np.uint64), {
            "candidate_subsets": 1,
            "selected_group_count": 0,
            "selected_rows": 0,
        }
    values = conflict_matrix.to_numpy(dtype=np.int64)
    group_rows = values.sum(axis=1)
    target_by_label = values.sum(axis=0) * target_fraction
    label_scale = np.maximum(target_by_label, 1.0)
    target_rows = group_rows.sum() * target_fraction
    row_scale = max(target_rows, 1.0)

    if len(conflict_matrix) <= 20:
        subset_ids = np.arange(1 << len(conflict_matrix), dtype=np.uint32)
        bit_positions = np.arange(len(conflict_matrix), dtype=np.uint32)
        membership = ((subset_ids[:, None] >> bit_positions) & 1).astype(np.int8)
        subset_label_rows = membership @ values
        subset_total_rows = membership @ group_rows
        label_error = np.mean(
            ((subset_label_rows - target_by_label) / label_scale) ** 2,
            axis=1,
        )
        total_error = ((subset_total_rows - target_rows) / row_scale) ** 2
        score = label_error + total_error
        best_index = int(np.argmin(score))
        selected = membership[best_index].astype(bool)
        method = "exhaustive"
        candidate_subsets = int(len(subset_ids))
        objective_score = float(score[best_index])
        selected_rows = int(subset_total_rows[best_index])
    else:
        def objective(label_rows: np.ndarray, total_rows: int) -> float:
            label_error = np.mean(((label_rows - target_by_label) / label_scale) ** 2)
            total_error = ((total_rows - target_rows) / row_scale) ** 2
            return float(label_error + total_error)

        rng = np.random.default_rng(seed)
        order = rng.permutation(len(conflict_matrix))
        selected = np.zeros(len(conflict_matrix), dtype=bool)
        current_labels = np.zeros(values.shape[1], dtype=np.int64)
        current_rows = 0
        current_score = objective(current_labels, current_rows)
        for position in order:
            candidate_labels = current_labels + values[position]
            candidate_rows = current_rows + int(group_rows[position])
            candidate_score = objective(candidate_labels, candidate_rows)
            if candidate_score < current_score:
                selected[position] = True
                current_labels = candidate_labels
                current_rows = candidate_rows
                current_score = candidate_score

        # One deterministic toggle pass removes avoidable local imbalance.
        for position in order:
            direction = -1 if selected[position] else 1
            candidate_labels = current_labels + direction * values[position]
            candidate_rows = current_rows + direction * int(group_rows[position])
            candidate_score = objective(candidate_labels, candidate_rows)
            if candidate_score < current_score:
                selected[position] = not selected[position]
                current_labels = candidate_labels
                current_rows = candidate_rows
                current_score = candidate_score
        method = "deterministic_greedy_with_toggle_pass"
        candidate_subsets = 0
        objective_score = current_score
        selected_rows = current_rows

    hashes = conflict_matrix.index.to_numpy(dtype=np.uint64)[selected]
    return hashes, {
        "method": method,
        "candidate_subsets": candidate_subsets,
        "input_group_count": int(len(conflict_matrix)),
        "selected_group_count": int(selected.sum()),
        "selected_rows": selected_rows,
        "target_rows": float(target_rows),
        "objective_score": objective_score,
    }


def deterministic_stratified_row_split(
    labels: np.ndarray,
    test_fraction: float,
    seed: int,
) -> np.ndarray:
    """Return a test mask using independent deterministic shuffles per Label."""
    test = np.zeros(len(labels), dtype=bool)
    for label in sorted(np.unique(labels).tolist()):
        positions = np.flatnonzero(labels == label)
        rng = np.random.default_rng(stable_label_seed(seed, str(label)))
        chosen_count = int(round(len(positions) * test_fraction))
        if chosen_count:
            chosen = rng.permutation(positions)[:chosen_count]
            test[chosen] = True
    return test


def row_random_leakage(
    hashes: np.ndarray,
    labels: np.ndarray,
    test_mask: np.ndarray,
) -> dict:
    frame = pd.DataFrame(
        {
            "feature_hash": hashes,
            "Label": labels,
            "is_test": test_mask,
        }
    )
    frame["binary_label"] = frame["Label"].ne("BENIGN").astype(np.int8)
    counts = (
        frame.groupby(["feature_hash", "Label", "binary_label", "is_test"], observed=True)
        .size()
        .rename("rows")
        .reset_index()
    )
    group_split = (
        counts.groupby(["feature_hash", "is_test"], observed=True)["rows"]
        .sum()
        .unstack(fill_value=0)
    )
    train_column = False if False in group_split.columns else None
    test_column = True if True in group_split.columns else None
    train_rows = (
        group_split[train_column] if train_column is not None else pd.Series(0, index=group_split.index)
    )
    test_rows = (
        group_split[test_column] if test_column is not None else pd.Series(0, index=group_split.index)
    )
    crossing_hashes = group_split.index[(train_rows > 0) & (test_rows > 0)]

    train_counts = counts.loc[~counts["is_test"]].copy()
    test_counts = counts.loc[counts["is_test"]].copy()
    train_same = train_counts.set_index(["feature_hash", "Label"])["rows"]
    test_key = pd.MultiIndex.from_frame(test_counts[["feature_hash", "Label"]])
    test_counts["has_same_label_train"] = test_key.isin(train_same.index)

    train_binary = (
        train_counts.groupby(["feature_hash", "binary_label"], observed=True)["rows"]
        .sum()
    )
    opposite_keys = pd.MultiIndex.from_arrays(
        [
            test_counts["feature_hash"].to_numpy(),
            1 - test_counts["binary_label"].to_numpy(),
        ]
    )
    test_counts["has_opposite_binary_train"] = opposite_keys.isin(train_binary.index)
    test_counts["feature_seen_in_train"] = test_counts["feature_hash"].isin(
        train_counts["feature_hash"]
    )

    test_total = int(test_mask.sum())
    seen_rows = int(test_counts.loc[test_counts["feature_seen_in_train"], "rows"].sum())
    same_rows = int(test_counts.loc[test_counts["has_same_label_train"], "rows"].sum())
    opposite_rows = int(
        test_counts.loc[test_counts["has_opposite_binary_train"], "rows"].sum()
    )
    crossing_all_rows = int(
        group_split.loc[crossing_hashes].to_numpy(dtype=np.int64).sum()
    )
    return {
        "test_rows": test_total,
        "cross_split_feature_groups": int(len(crossing_hashes)),
        "rows_in_cross_split_groups": crossing_all_rows,
        "test_rows_with_feature_seen_in_train": seen_rows,
        "test_rows_with_feature_seen_in_train_ratio": seen_rows / test_total,
        "test_rows_with_same_original_label_in_train": same_rows,
        "test_rows_with_same_original_label_in_train_ratio": same_rows / test_total,
        "test_rows_with_opposite_binary_label_in_train": opposite_rows,
        "test_rows_with_opposite_binary_label_in_train_ratio": opposite_rows / test_total,
    }


@dataclass
class GroupSplitResult:
    test_hashes: np.ndarray
    conflict_selection: dict
    per_label_targets: dict[str, int]


def build_group_stratified_split(
    group_label_counts: pd.DataFrame,
    test_fraction: float = 0.25,
    seed: int = 42,
) -> GroupSplitResult:
    """Keep exact-feature groups intact while approximating Label stratification."""
    label_totals = group_label_counts.groupby("Label", observed=True)["rows"].sum()
    targets = {str(label): int(round(rows * test_fraction)) for label, rows in label_totals.items()}
    labels = sorted(targets)

    label_counts_per_group = group_label_counts.groupby("feature_hash", observed=True).size()
    conflict_hashes = label_counts_per_group.index[label_counts_per_group > 1]
    conflict_rows = group_label_counts.loc[
        group_label_counts["feature_hash"].isin(conflict_hashes)
    ]
    conflict_matrix = (
        conflict_rows.pivot_table(
            index="feature_hash",
            columns="Label",
            values="rows",
            aggfunc="sum",
            fill_value=0,
            observed=True,
        )
        .reindex(columns=labels, fill_value=0)
        .sort_index()
    )
    selected_conflicts, conflict_selection = choose_conflict_test_groups(
        conflict_matrix, test_fraction, seed
    )
    selected_conflict_rows = (
        conflict_matrix.loc[selected_conflicts].sum(axis=0)
        if len(selected_conflicts)
        else pd.Series(0, index=labels)
    )

    consistent = group_label_counts.loc[
        ~group_label_counts["feature_hash"].isin(conflict_hashes)
    ]
    selected_parts = [selected_conflicts]
    for label in labels:
        label_groups = consistent.loc[consistent["Label"] == label]
        remaining_target = max(
            0, targets[label] - int(selected_conflict_rows.get(label, 0))
        )
        selected = closest_prefix_selection(
            label_groups["feature_hash"].to_numpy(dtype=np.uint64),
            label_groups["rows"].to_numpy(dtype=np.int64),
            remaining_target,
            stable_label_seed(seed, label),
        )
        selected_parts.append(selected)
    test_hashes = np.unique(np.concatenate(selected_parts)).astype(np.uint64)
    return GroupSplitResult(test_hashes, conflict_selection, targets)
