"""그룹 키 생성 및 그룹 인덱스 테이블 (split_protocol_proposal.md 4-2, 4-3).

group_id = hash(src_ip, dst_ip, attack_label, floor(timestamp / bucket_seconds)).

파이썬 내장 hash()는 PYTHONHASHSEED에 따라 프로세스마다 값이 달라져 재현성이
깨지므로 쓰지 않는다. hashlib.md5 기반 결정적 해시를 쓴다 — "정확성과 재현성이
최우선"이라는 요구를 타협하지 않는다.

attack_label은 Label 컬럼 원문을 그대로 쓴다 ("- Attempted" 접미사 변종도 별개
레이블로 취급한다. 작업 지시서에 명시되지 않은 부분이라 여기 남겨둔다).
"""

from __future__ import annotations

import hashlib

import pandas as pd

from .columns import (
    COL_ATTACK_LABEL,
    COL_DAY,
    COL_DST_IP,
    COL_GROUP_ID,
    COL_LABEL,
    COL_N_FLOWS_IN_GROUP,
    COL_REP_TIME,
    COL_SRC_IP,
    COL_TIMESTAMP,
)


def add_attack_label(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df[COL_ATTACK_LABEL] = df[COL_LABEL]
    return df


def compute_group_id(df: pd.DataFrame, bucket_seconds: int) -> pd.Series:
    # datetime64의 내부 해상도(ns/us/...)는 pandas 버전에 따라 달라질 수 있다
    # (예: pandas 3.0.5는 기본 us) -- astype("int64")를 바로 쓰면 해상도에 따라
    # 값의 단위가 달라져 버킷 계산이 깨진다. datetime64[s]로 먼저 캐스팅해
    # 해상도에 의존하지 않는 정수 초 단위를 얻는다.
    epoch_seconds = df[COL_TIMESTAMP].astype("datetime64[s]").astype("int64")
    bucket_idx = epoch_seconds // bucket_seconds
    key = (
        df[COL_SRC_IP].astype(str)
        + "|"
        + df[COL_DST_IP].astype(str)
        + "|"
        + df[COL_ATTACK_LABEL].astype(str)
        + "|"
        + bucket_idx.astype(str)
    )
    return key.apply(lambda k: hashlib.md5(k.encode("utf-8")).hexdigest())


def build_group_index(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby(COL_GROUP_ID)
        .agg(
            **{
                COL_DAY: (COL_DAY, "first"),
                COL_ATTACK_LABEL: (COL_ATTACK_LABEL, "first"),
                COL_REP_TIME: (COL_TIMESTAMP, "min"),
                COL_N_FLOWS_IN_GROUP: (COL_GROUP_ID, "size"),
            }
        )
        .reset_index()
    )
    return grouped
