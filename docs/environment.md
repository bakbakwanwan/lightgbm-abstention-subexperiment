# 환경 — 미정

이 문서는 미확정 상태다. 확정되기 전까지 아래 항목을 사실로 가정하고 코드나 스크립트를
작성하지 않는다.

---

## 확인된 사실 (2026-09-10 기준)

- 이 세션의 실제 작업 환경은 **Windows 네이티브**다.
- 저장소 경로: `C:\Users\user1\RUSExperiment` — NTFS, WSL 마운트가 아니다.
- 셸: Git Bash (POSIX 문법을 지원하는 Windows 네이티브 셸이며 WSL이 아니다).
- git: `git version 2.55.0.windows.5`

## 이전 CLAUDE.md와의 불일치

CLAUDE.md 초기 버전(2026-09-10 17:38 작성)의 "환경" 절에는 다음과 같이 적혀 있었다.

> WSL2 Ubuntu, Python 3.11 이상. 저장소는 리눅스 파일시스템에 있다.

위 "확인된 사실"과 맞지 않는다. 사용자 확인 결과 이 서술은 지금 당장 고치지 않고
미정 사항으로 분리해 이 문서에서 추적하기로 했다. **CLAUDE.md 본문에는 더 이상
WSL2를 기정사실로 적지 않는다.**

## 미정 사항

1. 최종 실행 환경을 WSL2 Ubuntu로 할지, Windows 네이티브로 유지할지.
2. 의존성 관리(`uv`, `pyproject.toml`)가 두 환경에서 동일하게 동작하는지 검증 필요.
3. `Makefile` 진입점(`make exp ID=EXP-XXX` 등)이 Windows에서 `make` 명령 자체의
   가용성을 포함해 그대로 동작하는지.
4. 줄바꿈(LF/CRLF) 정책 — 현재 저장소는 Windows git 기본값(autocrlf)을 그대로 쓰고 있고
   `.gitattributes`는 아직 없다.
5. 대용량 CSV(`data/` 하위, 요일별 약 200~290MB)를 다루는 I/O 경로가 두 환경에서
   성능 차이가 있는지.

## 결정되면 이 문서에 반영할 것

- 위 미정 사항 각각의 결론
- CLAUDE.md "환경" 절을 확정된 내용으로 갱신
- 필요 시 `.gitattributes` 추가 여부

---

이 문서 자체가 `docs/`에 있으므로 Cowork·사용자가 관리 주체이고,
Claude Code는 내용을 임의로 확정하지 않는다.
