# 환경 — 미정

이 문서는 미확정 상태다. 확정되기 전까지 아래 항목을 사실로 가정하고 코드나 스크립트를
작성하지 않는다.

---

## 확인된 사실 (2026-09-10 기준)

- 이 세션의 실제 작업 환경은 **Windows 네이티브**다.
- 저장소 경로: `C:\Users\user1\RUSExperiment` — NTFS, WSL 마운트가 아니다.
- 셸: Git Bash (POSIX 문법을 지원하는 Windows 네이티브 셸이며 WSL이 아니다).
- git: `git version 2.55.0.windows.5`
- Python 3.14.7(`C:\Python314`) + `uv 0.12.12`(pip로 설치) + `pyproject.toml`/
  `uv.lock` 조합이 Windows 네이티브에서 실제로 동작함을 확인했다. pandas 3.0.5 +
  pyarrow 25.0.1 + pyyaml + pytest 9.1.1로 `cicids_prep` 파이프라인을 실제
  CICIDS2017 데이터(약 210만 행)에 전체 실행(2분 20초)·`--loao-only` 재실행
  (1분) 모두 성공시켰다.
- `make`는 이 환경에 **미설치 상태로 확정**됐다 — `choco install make -y`가
  `UnauthorizedAccessException`(관리자 권한 필요)으로 실패했다. 설치 재시도
  여부는 사용자 판단으로 보류 중이다. `Makefile`은 작성해뒀지만 `make` 명령
  자체로 실행 검증은 하지 못했고, 지금은 `uv run python scripts/build_dataset.py
  ...`로 직접 실행해 확인했다.
- `uv run pytest`(콘솔 스크립트 실행)는 numpy import 오류가 났지만
  `uv run python -m pytest`(모듈 실행)는 문제없이 동작했다 — 원인 불명, 후자를
  표준 실행 방식으로 채택.

## 이전 CLAUDE.md와의 불일치

CLAUDE.md 초기 버전(2026-09-10 17:38 작성)의 "환경" 절에는 다음과 같이 적혀 있었다.

> WSL2 Ubuntu, Python 3.11 이상. 저장소는 리눅스 파일시스템에 있다.

위 "확인된 사실"과 맞지 않는다. 사용자 확인 결과 이 서술은 지금 당장 고치지 않고
미정 사항으로 분리해 이 문서에서 추적하기로 했다. **CLAUDE.md 본문에는 더 이상
WSL2를 기정사실로 적지 않는다.**

## 미정 사항

1. 최종 실행 환경을 WSL2 Ubuntu로 할지, Windows 네이티브로 유지할지. (여전히 미정 —
   Windows 네이티브가 "동작한다"는 것만 확인됐을 뿐, WSL2와 비교해 선택한 것은 아니다.)
2. `uv`/`pyproject.toml` 조합이 **WSL2 쪽에서도** 동일하게 동작하는지는 아직
   검증 전이다(Windows 네이티브 쪽만 확인됨, 위 "확인된 사실" 참고).
3. `make`를 이 환경에 설치할지 말지 — **보류 중** (사용자 지시, choco 권한 문제로
   재시도하지 않음). `Makefile` 자체는 있으니 설치되면 바로 검증 가능하다.
4. 줄바꿈(LF/CRLF) 정책 — 현재 저장소는 Windows git 기본값(autocrlf)을 그대로 쓰고 있고
   `.gitattributes`는 아직 없다.
5. 대용량 CSV(`data/` 하위, 요일별 약 200~290MB)를 다루는 I/O 경로의 WSL2 대비
   성능 차이는 비교 대상이 없어 여전히 미정이다 (Windows 네이티브 단독 수치는
   위 "확인된 사실"의 실행 시간 참고).

## 결정되면 이 문서에 반영할 것

- 위 미정 사항 각각의 결론
- CLAUDE.md "환경" 절을 확정된 내용으로 갱신
- 필요 시 `.gitattributes` 추가 여부

---

이 문서 자체가 `docs/`에 있으므로 Cowork·사용자가 관리 주체이고,
Claude Code는 내용을 임의로 확정하지 않는다.
