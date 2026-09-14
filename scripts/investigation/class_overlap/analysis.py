"""Core helpers for exact duplicate and class-overlap measurement.

The first-stage hash is only a candidate index. Every candidate group is split and
verified again with the original 59 parsed feature values before it contributes to
any result.
"""

from __future__ import annotations

import heapq
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd

PROTOCOL_MAP = {6: "TCP", 17: "UDP", 1: "ICMP", 0: "UNKNOWN"}
PROTOCOL_CATEGORIES = ["TCP", "UDP", "ICMP", "UNKNOWN"]
BENIGN_LABEL = "BENIGN"

GROUP_SIZE_BINS = ("2", "3", "4", "5-10", "11-100", ">100")
SAMPLE_FEATURES = (
    "Protocol",
    "Flow Duration",
    "Total Fwd Packet",
    "Total Length of Fwd Packet",
    "Total Length of Bwd Packet",
    "Flow Bytes/s",
    "SYN Flag Count",
    "RST Flag Count",
    "ACK Flag Count",
)


def map_protocol(series: pd.Series) -> pd.Series:
    """Map protocol numbers to the canonical categorical representation."""
    numeric = pd.to_numeric(series, errors="raise")
    unexpected = sorted(set(numeric.dropna().astype(int).unique()) - set(PROTOCOL_MAP))
    if unexpected:
        raise ValueError(f"Unexpected Protocol values: {unexpected}")
    mapped = numeric.map(PROTOCOL_MAP)
    if mapped.isna().any():
        raise ValueError("Protocol contains missing values")
    return pd.Series(
        pd.Categorical(mapped, categories=PROTOCOL_CATEGORIES),
        index=series.index,
        name=series.name,
    )


def normalize_features(frame: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    """Return the 59 comparison columns with fixed, cross-chunk dtypes."""
    features = frame.loc[:, feature_columns].copy()
    features["Protocol"] = map_protocol(features["Protocol"])
    numeric_columns = [c for c in feature_columns if c != "Protocol"]
    features[numeric_columns] = features[numeric_columns].astype("float64")
    return features


def feature_hash(features: pd.DataFrame) -> np.ndarray:
    """Compute a stable uint64 candidate hash without rounding values."""
    return pd.util.hash_pandas_object(
        features, index=False, categorize=True
    ).to_numpy(dtype=np.uint64, copy=False)


def duplicate_hashes(hashes: np.ndarray) -> np.ndarray:
    """Return sorted hash values occurring at least twice."""
    if len(hashes) == 0:
        return np.array([], dtype=np.uint64)
    values, counts = np.unique(hashes, return_counts=True)
    return values[counts >= 2]


def rows_equal_to_first(features: pd.DataFrame) -> np.ndarray:
    """Compare original values exactly, treating paired missing values as equal."""
    if len(features) == 0:
        return np.array([], dtype=bool)
    first = features.iloc[0]
    equal = features.eq(first) | (features.isna() & first.isna())
    return equal.all(axis=1).to_numpy(dtype=bool)


def split_exact_groups(
    hash_group: pd.DataFrame, feature_columns: list[str]
) -> list[pd.DataFrame]:
    """Split one candidate-hash group by all original feature values."""
    features = hash_group.loc[:, feature_columns]
    if rows_equal_to_first(features).all():
        return [hash_group]

    exact_groups: list[pd.DataFrame] = []
    grouped = hash_group.groupby(
        feature_columns,
        dropna=False,
        sort=False,
        observed=True,
    )
    for positions in grouped.indices.values():
        subgroup = hash_group.iloc[np.asarray(positions, dtype=np.int64)]
        if not rows_equal_to_first(subgroup.loc[:, feature_columns]).all():
            raise AssertionError("Exact-value collision split failed")
        exact_groups.append(subgroup)
    return exact_groups


def group_size_bin(size: int) -> str:
    if size == 2:
        return "2"
    if size == 3:
        return "3"
    if size == 4:
        return "4"
    if size <= 10:
        return "5-10"
    if size <= 100:
        return "11-100"
    return ">100"


@dataclass
class ScopeAccumulator:
    name: str
    duplicate_groups: int = 0
    duplicate_rows: int = 0
    label_match_groups: int = 0
    label_match_rows: int = 0
    label_conflict_groups: int = 0
    label_conflict_rows: int = 0
    size_distribution: Counter = field(default_factory=Counter)
    conflict_labels: Counter = field(default_factory=Counter)
    conflict_days: Counter = field(default_factory=Counter)
    conflict_day_combinations: Counter = field(default_factory=Counter)
    within_file_conflict_groups: int = 0
    cross_file_conflict_groups: int = 0
    within_file_conflict_rows: int = 0
    cross_file_conflict_rows: int = 0
    duplicate_groups_with_infinite_flow_bytes: int = 0
    duplicate_rows_with_infinite_flow_bytes: int = 0
    conflict_groups_with_infinite_flow_bytes: int = 0
    conflict_rows_with_infinite_flow_bytes: int = 0
    _top_conflict_heap: list[tuple[int, int, list[dict]]] = field(default_factory=list)
    _heap_sequence: int = 0

    def add_group(self, group: pd.DataFrame, group_id: str) -> None:
        size = len(group)
        if size < 2:
            return
        self.duplicate_groups += 1
        self.duplicate_rows += size
        self.size_distribution[group_size_bin(size)] += 1

        binary_labels = group["_label"].ne(BENIGN_LABEL)
        is_conflict = binary_labels.nunique(dropna=False) > 1
        has_infinite = np.isinf(group["Flow Bytes/s"].to_numpy(dtype=float)).any()
        if has_infinite:
            self.duplicate_groups_with_infinite_flow_bytes += 1
            self.duplicate_rows_with_infinite_flow_bytes += size

        if not is_conflict:
            self.label_match_groups += 1
            self.label_match_rows += size
            return

        self.label_conflict_groups += 1
        self.label_conflict_rows += size
        self.conflict_labels.update(group["_label"].astype(str))
        self.conflict_days.update(group["_day"].astype(str))
        day_combination = "+".join(sorted(group["_day"].astype(str).unique()))
        self.conflict_day_combinations[day_combination] += 1

        crosses_files = group["_day"].nunique(dropna=False) > 1
        if crosses_files:
            self.cross_file_conflict_groups += 1
            self.cross_file_conflict_rows += size
        else:
            self.within_file_conflict_groups += 1
            self.within_file_conflict_rows += size

        if has_infinite:
            self.conflict_groups_with_infinite_flow_bytes += 1
            self.conflict_rows_with_infinite_flow_bytes += size

        rows = conflict_sample_rows(group, group_id)
        item = (size, self._heap_sequence, rows)
        self._heap_sequence += 1
        if len(self._top_conflict_heap) < 20:
            heapq.heappush(self._top_conflict_heap, item)
        elif item[:2] > self._top_conflict_heap[0][:2]:
            heapq.heapreplace(self._top_conflict_heap, item)

    def summary(self, population_rows: int) -> dict:
        ratio = self.duplicate_rows / population_rows if population_rows else 0.0
        conflict_ratio = (
            self.label_conflict_rows / population_rows if population_rows else 0.0
        )
        return {
            "scope": self.name,
            "population_rows": population_rows,
            "duplicate_groups": self.duplicate_groups,
            "duplicate_rows": self.duplicate_rows,
            "duplicate_row_ratio": ratio,
            "label_match_groups": self.label_match_groups,
            "label_match_rows": self.label_match_rows,
            "label_conflict_groups": self.label_conflict_groups,
            "label_conflict_rows": self.label_conflict_rows,
            "label_conflict_row_ratio": conflict_ratio,
            "conflict_file_scope": {
                "within_file_groups": self.within_file_conflict_groups,
                "within_file_rows": self.within_file_conflict_rows,
                "cross_file_groups": self.cross_file_conflict_groups,
                "cross_file_rows": self.cross_file_conflict_rows,
                "row_distribution_by_day": dict(
                    sorted(self.conflict_days.items())
                ),
                "group_distribution_by_day_combination": dict(
                    sorted(self.conflict_day_combinations.items())
                ),
            },
            "infinite_flow_bytes": {
                "duplicate_groups": self.duplicate_groups_with_infinite_flow_bytes,
                "duplicate_rows": self.duplicate_rows_with_infinite_flow_bytes,
                "conflict_groups": self.conflict_groups_with_infinite_flow_bytes,
                "conflict_rows": self.conflict_rows_with_infinite_flow_bytes,
            },
        }

    def top_conflict_rows(self) -> list[dict]:
        items = sorted(self._top_conflict_heap, reverse=True)
        rows: list[dict] = []
        for _, _, item_rows in items:
            rows.extend(item_rows)
        return rows


def conflict_sample_rows(group: pd.DataFrame, group_id: str) -> list[dict]:
    """Keep up to 20 identifying rows, while representing every label when possible."""
    ordered = group.sort_values(["_label", "_day", "_id"], kind="stable")
    chosen_indices: list[int] = []
    for _, label_rows in ordered.groupby("_label", sort=False, observed=True):
        chosen_indices.append(label_rows.index[0])
    remaining = [idx for idx in ordered.index if idx not in set(chosen_indices)]
    chosen_indices.extend(remaining[: max(0, 20 - len(chosen_indices))])
    chosen = ordered.loc[chosen_indices[:20]]

    result = []
    for _, row in chosen.iterrows():
        record = {
            "group_id": group_id,
            "group_size": len(group),
            "sampled_rows": min(len(group), 20),
            "sample_truncated": len(group) > 20,
            "day": str(row["_day"]),
            "id": int(row["_id"]),
            "Label": str(row["_label"]),
            "binary_label": int(str(row["_label"]) != BENIGN_LABEL),
        }
        for column in SAMPLE_FEATURES:
            value = row.get(column, pd.NA)
            record[column] = value.item() if hasattr(value, "item") else value
        result.append(record)
    return result


def process_candidate_bucket(
    candidate_frame: pd.DataFrame,
    feature_columns: list[str],
    target_accumulator: ScopeAccumulator,
    full_accumulator: ScopeAccumulator,
) -> int:
    """Verify and accumulate one hash bucket; return true hash-collision count."""
    collision_count = 0
    for hash_value, hash_group in candidate_frame.groupby(
        "_feature_hash", sort=False, observed=True
    ):
        exact_groups = split_exact_groups(hash_group, feature_columns)
        if len(exact_groups) > 1:
            collision_count += len(exact_groups) - 1
        for exact_index, exact_group in enumerate(exact_groups):
            group_id = f"g_{int(hash_value):016x}_{exact_index}"
            full_accumulator.add_group(exact_group, group_id)
            target_group = exact_group.loc[exact_group["_target"]]
            target_accumulator.add_group(target_group, group_id)
    return collision_count


def distribution_rows(accumulator: ScopeAccumulator) -> Iterable[dict]:
    for size_bin in GROUP_SIZE_BINS:
        yield {
            "scope": accumulator.name,
            "group_size_bin": size_bin,
            "group_count": int(accumulator.size_distribution[size_bin]),
        }
