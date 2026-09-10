"""헤더 문자열 매칭 유틸 (지시서 1-6: 컬럼명을 추정하지 않는다).

후보가 0개 또는 2개 이상이면 예외를 던진다 — 호출부가 이를 잡아 해당 하위
작업만 중단하고 사유를 보고서에 남긴다.
"""

from __future__ import annotations


class ColumnResolutionError(Exception):
    def __init__(self, purpose: str, tokens: list[str], matches: list[str]):
        self.purpose = purpose
        self.tokens = tokens
        self.matches = matches
        super().__init__(
            f"{purpose}: tokens={tokens} -> 후보 {len(matches)}개 {matches}"
        )


def find_columns(header: list[str], required_tokens: list[str]) -> list[str]:
    """header 중 모든 required_tokens를 (대소문자 무시) 부분 문자열로 포함하는 컬럼명."""
    return [
        c for c in header
        if all(tok.lower() in c.lower() for tok in required_tokens)
    ]


def resolve_single(header: list[str], required_tokens: list[str], purpose: str) -> str:
    matches = find_columns(header, required_tokens)
    if len(matches) != 1:
        raise ColumnResolutionError(purpose, required_tokens, matches)
    return matches[0]
