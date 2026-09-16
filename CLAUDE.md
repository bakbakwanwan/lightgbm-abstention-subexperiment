# CLAUDE.md

이 저장소에서 작업할 때 반드시 따르는 규약이다.

---

## 프로젝트

**CTI 및 다중 에이전트 RAG를 결합한 하이브리드 실시간 IDS 프레임워크.**

LightGBM이 전량 트래픽을 처리하되, 신뢰도를 기준으로 정상·공격이
명확히 구분되는 구간만 즉시 판정하고 나머지는 **판정을 유보(abstention)** 한다.
유보된 소수 플로우만 LLM 기반 2차 검증과 다중 Agent RAG로 넘긴다.

중심축은 **확신 기반 선택적 검증**이다. LLM, XAI, RAG, Critic Agent는 모두 하위 구성요소이며,
이들 중 어느 것도 프로젝트의 중심 기여로 취급하지 않는다.

## 단일 기준 문서

**`docs/CURRENT_DECISIONS.md`가 이 저장소의 유일한 결정 정본이다.**
다른 문서·코드와 충돌하면 항상 그 문서가 우선한다.

같은 사실을 두 문서에 쓰지 않는다. 정본 위치는 다음과 같다.

| 사실 | 정본 |
|---|---|
| 결정과 그 근거 (D-001~D-006) | `docs/CURRENT_DECISIONS.md` |
| 학습 입력 컬럼 59개 / 제외 32개 | `configs/features_whitelist.json` |
| 레이블 전수·파이프라인 감사·Attempted 코드북 | `docs/dataset_audit_2026-09-11.md` |
| 원본 91컬럼 통계 | `docs/feature_inventory_2026-09-12.md` |
| 용어·식별자 | `docs/glossary.md` |
| Claude Code 행동 규약·폐기 목록 | 이 문서 |

**목록이나 수치를 다른 문서에 옮겨 적지 않는다.** 2026-09-13에 `Protocol`의 처분이
요약본에서 "제외"로 뒤바뀐 사고가 있었고, 원인은 원본을 산문으로 압축한 것이었다.
경위: `docs/doc_consistency_audit_2026-09-13.md`.

## 현재 단계

예비 실험(sub experiment) 단계다.

- EXP-007은 D-004 주 분할에서 confidence 기반 유보 구간의 존재를 확인했고 결과를
  `results/EXP-007/`에 보존했다.
- 다음 실험은 확정 스펙 `experiments/EXP-008-group-split-stability.md`에 따른
  완전일치 그룹 분할 seed 민감도 분석이다. 같은 데이터의 구조적 민감도만 평가하며
  독립 데이터 일반화를 주장하지 않는다.
- 확률 보정·ECE·Brier는 범위 밖이고, 2·3차 계층(LLM 검증, RAG, Critic)은 아직
  구현 대상이 아니다. 요청받지 않은 한 해당 코드를 작성하지 않는다.
- 현재 작업은 EXP-008 설정과 공용 실행 코드 구현이다. 구현·테스트·사전 검증을 마치기
  전에는 EXP-008을 실행하지 않는다.

`docs/CURRENT_DECISIONS.md`의 "다음 작업" 절과 EXP-008 확정 스펙을 먼저 읽는다.

---

## 항상 적용되는 규약

@docs/glossary.md

특히 자주 어겨지는 네 가지를 재강조한다. 상세와 근거는 `docs/CURRENT_DECISIONS.md`에 있다.

1. **확률 보정을 하지 않는다.** 보정 세트도 만들지 않는다(D-004). 보정을 전제한 코드·지표를
   추가하지 않는다. 과거 문서(`_superseded/docs/design-constraints.md`,
   `_superseded/docs/metrics-spec.md`)는 반대로 적혀 있으나 폐기되었다.
2. **유보 구간 폭을 코드에 하드코딩하지 않는다.** config로만 주입하거나 오프라인 스윕으로 구한다.
3. **검증 결과를 학습 라벨에 되먹이지 않는다.** 환류는 임계값 조정까지다.
4. **학습 입력 컬럼은 `configs/features_whitelist.json`에서 읽는다.** 코드에 목록을 박지 않는다.
   `Protocol`은 포함이며 pandas `category` dtype 변환 후 LightGBM `categorical_feature`로
   **명시 선언**해야 한다. 선언을 빠뜨리면 정수 서열로 다시 취급된다.

---

## 상황별로 읽을 문서

- **무엇이 확정되었고 왜 그런지** → `docs/CURRENT_DECISIONS.md`
- **데이터 로딩·전처리·분할 코드를 만지기 전** → `docs/CURRENT_DECISIONS.md` D-001·D-002·D-004와
  "대상 행 집합" 절. 데이터셋의 알려진 결함은 `docs/dataset_audit_2026-09-11.md`
- **컬럼 하나의 포함 여부·사유** → `configs/features_whitelist.json`
- **컬럼의 분포·고유값·결측** → `docs/feature_inventory_2026-09-12.md`
- **환경·의존성 문제** → `docs/environment.md`
- **지금 또는 다음에 처리해야 할 작업** → `tasks/`
  `tasks/`는 아직 `experiments/EXP-XXX-*.md` 형태의 확정 스펙으로 정리되기 전 단계의
  업무 지시서·요청서를 모아두는 곳이다. `experiments/`는 성공·실패 기준까지 갖춘
  확정 실험 스펙만 들어간다. 둘을 혼동해 넣지 않는다.

## 읽지 않을 것

**`_superseded/` 하위 전체를 현행 사양으로 참조하지 않는다.**
폐기된 파이프라인 설계와 폐기된 진행 기록이 들어 있으며, 이미 기각된 설계를
정당한 근거처럼 제안하게 만든다. 이력 보존 목적으로만 남겨 두었다.

`_superseded/` 아래 파일을 읽어야 하는 경우는 **"과거에 왜 그렇게 했는지"를 추적할 때뿐**이며,
그때도 현행 사양은 `docs/CURRENT_DECISIONS.md`에서 확인한다.

### `_superseded/`에 들어 있는 것

| 경로 | 폐기 사유 |
|---|---|
| `docs/design-constraints.md` | 보정 전제. D-004와 충돌 |
| `docs/metrics-spec.md` | 보정 지표 전제. D-004와 충돌 |
| `docs/data-notes.md` | "무작위 분할 금지". D-004와 충돌 |
| `docs/report.md`, `docs/stage1_briefing.md`, `docs/PROGRESS_BRIEFING.md` | 폐기된 파이프라인의 진행 기록 |
| `docs/project_context_roadmap.md` | 10단계 로드맵·정책 1-1~1-12. `CURRENT_DECISIONS.md`가 대체 |
| `docs/handoff_2026-09-13.md` | 세션 인계용. 근거는 `CURRENT_DECISIONS.md` D-004로 이관 완료 |
| `experiments/EXP-001 ~ EXP-006`, `experiments/QUEUE.md` | 보정·Dst Port 재도입·LOAO 전제. 재작성 필요 |
| `tasks/split_protocol_proposal.md` | D-004가 대체 |
| `configs/exp/cicids_prep.yaml` | `split_ratios 0.6/0.2/0.2`, `bucket_seconds 300` 무효 |
| `src/cicids_prep/**`, `tests/cicids_prep/**`, `scripts/build_dataset.py` | 폐기된 파이프라인 구현·테스트·진입점 |
| `results/cicids_prep/**` | 폐기된 실행 결과 |

**`reports/attempted_hulk_investigation/**`는 폐기가 아니다.** D-001·D-002의 근거 자료이며 유효하다.

---

## 쓰기 권한

- **쓴다**: `src/`, `configs/`, `tests/`, `scripts/`, `results/`, `pyproject.toml`
- **읽기만 한다**: `docs/`, `experiments/`, `tasks/`, `_superseded/`

`docs/`, `experiments/`, `tasks/`는 Cowork와 사용자가 관리한다. 수정이 필요하다고
판단되면 직접 고치지 말고 무엇을 왜 고쳐야 하는지 보고한다.

**예외:** 사용자가 `tasks/` 아래 지시서로 명시적으로 위임한 작업은 그 지시서의 범위 안에서 수행한다.

### 삭제 금지

- 사용자가 특정 파일·디렉토리를 지정해 명시적으로 삭제를 지시하지 않는 한,
  어떤 파일도 임의로 삭제하지 않는다. "안 쓰는 것 같다", "정리 차원" 같은
  판단만으로 삭제하지 않는다.
- 삭제가 필요하다고 판단되면 먼저 무엇을, 왜 삭제해야 하는지 보고하고
  사용자의 확인을 받는다.
- 되돌릴 수 없는 삭제(`rm -rf`, `git clean -fd`, 원격 브랜치 삭제, 대용량 데이터 삭제 등)는
  사용자가 그 명령을 정확히 확인한 뒤에만 실행한다.
- 코드에서 더 이상 쓰이지 않는 것으로 보이는 파일을 발견하면, 삭제 대신 발견한 사실만 보고한다.

---

## 실험 실행 절차

`experiments/`는 현재 전부 `_superseded/`로 이동했고 재작성 전이다.
아래 절차는 새 스펙이 작성된 뒤에 적용된다.

1. `experiments/EXP-XXX-*.md` 스펙을 읽는다. 스펙이 없으면 실행하지 않고 사용자에게 알린다.
2. 스펙 4절(성공·실패 기준)이 비어 있으면 실행하지 않는다. 결과를 본 뒤 기준을 정하면
   사후 합리화가 된다.
3. `git status`가 clean인지 확인한다. 아니면 커밋을 먼저 제안한다.
4. 결과 디렉토리가 이미 있으면 실행하지 않는다. 덮어쓰지 말고 `EXP-XXX-r2`로 새 ID를 만든다.
5. `results/EXP-XXX/metrics.json`에 `git_commit`, `seed`, `dataset` 버전을 기록한다.
6. 결과 해석은 `metrics.json`에 쓰지 않는다. 수치만 남기고 해석은 사용자에게 보고한다.

**주의.** 구 `CLAUDE.md`는 `make exp ID=EXP-XXX`를 지시했으나 **Makefile에 `exp` 타겟이 없다.**
`git-policy.md`가 언급한 `guard-clean` 타겟도 없다. 실행 진입점은 새 스펙과 함께 정의한다.

---

## 환경

**실행 OS·파일시스템은 미정이다.** 상세와 근거는 `docs/environment.md` 참고.

확정된 것만 적는다.

- 의존성은 `uv`로 관리한다. `pip install`을 직접 실행하지 않고 `pyproject.toml`을 수정한다.
- `data/`는 git에 없다. 없다고 새로 다운로드하지 말고 사용자에게 경로를 확인한다.
- 데이터 실제 경로는 `data/CICIDS2017_CNS2022_reprocessed/`(요일별 CSV 5개)다.

## 코드 규약

- 코드 식별자와 `metrics.json` 필드명은 `docs/glossary.md`의 용어와 1:1로 맞춘다.
- 실험 간 차이는 코드가 아니라 `configs/exp/`로 표현한다.
  `train_v2.py` 같은 파일 복사본을 만들지 않는다.
- 난수를 쓰는 모든 곳에 seed를 명시한다.
- 노트북에서 나온 수치를 실험 결과로 인용하지 않는다.

---

## 판단이 필요할 때

- 제약과 충돌하는 더 나은 방법이 보이면, 코드를 고치기 전에 무엇이 왜 충돌하는지 보고한다.
- 데이터에서 예상과 다른 것을 발견하면 우회하지 말고 보고한다.
  특히 신뢰도 분포가 0과 1에 극단적으로 몰려 있으면 즉시 알린다. 이 프로젝트의
  가장 큰 위험이며, 실험 설계 전체를 재검토해야 하는 신호다.
- 논문을 인용할 때는 서지사항을 원문에서 확인한다. 확인하지 못했으면 확인하지 못했다고 적는다.
- 확신이 없으면 추측해서 진행하지 말고 묻는다. 이 단계에서 잘못된 수치를 만드는 것이
  아무것도 만들지 않는 것보다 훨씬 나쁘다.

## 응답

한국어로 응답한다. 설명은 카드형·박스형 강조 없이 번호를 매긴 평문으로 한다.
