# 문서 대조 감사 — 프로젝트 문서 ↔ 저장소 문서

> **작성일:** 2026-09-13
> **대조 대상:** Cowork 프로젝트 문서 8종 ↔ 저장소 `lightgbm-abstention-subexperiment` (commit `91fa16f`)
> **대조 방법:** 저장소를 clone해 전문 대조. 로컬 작업본과 파일 크기 14개 전부 일치 확인.
> **범위:** 불일치만 기록한다. 일치 항목은 적지 않는다.

---

## 0. 대조 가능 여부

| 항목 | 상태 |
|---|---|
| 저장소 문서 전문 | 대조 완료 (clone) |
| 프로젝트 문서 8종 | 대조 완료 |
| `Claude outputs/handoff_2026-09-13.md` | **대조 불가** — git 미추적이라 clone에 없음. 크기 8,699바이트만 확인 |

Cowork↔PC 브리지는 오늘 기준 **파일 읽기(stage)가 HTTP 401, PC 셸이 마운트 실패**다.
디렉토리 조회와 파일 쓰기는 동작한다. handoff §9의 기록과 일치한다.

---

## A. 사실관계가 서로 반대인 것

### A-1. `Protocol` — 포함인가 제외인가 (최우선)

**정본 (일치하는 두 곳)**

- 프로젝트 `claude/decisions.md` D-003 §6: **포함.** 누수가 아니며 실제 운영 환경에서 일반화되는
  정당한 피처. 단 `6→TCP / 17→UDP / 1→ICMP / 0→UNKNOWN` 매핑 후 pandas `category` dtype +
  LightGBM `categorical_feature` 명시 선언 필수.
- `configs/features_whitelist.json`: `include` 배열 3행에 `Protocol` 존재.

**오기 2건**

| 위치 | 현재 서술 |
|---|---|
| `docs/CURRENT_DECISIONS.md` §2 D-003 표 66행 | `Protocol` \| 정수 매핑이 서열로 오독됨. **제외 확정** |
| `tasks/task_duplicate_class_overlap_measurement.md` §3 105행 | `Protocol`을 "비교 키에 넣지 않는다" 목록에 포함 |

**산술 증거.** whitelist는 include 59 + exclude 32 = 91로 미분류 0개다.
`Protocol`이 제외라면 include는 58이 되어 "59열" 서술 자체가 깨진다.

**자기모순.** task 문서는 102행에서 "whitelist의 include 59개 컬럼만 사용한다"고 지시한 뒤
105행에서 그 59개에 속한 `Protocol`을 제외 목록에 넣는다. 같은 절 안에서 반대를 말한다.

**이것이 왜 중요한가.** handoff §8 실수 패턴 5번이 바로 이 오류
("원본 대조 없이 요약을 재작성 — `Protocol`을 '제외'로 잘못 적었다")를 기록하고 있다.
그런데 **저장소의 두 파일은 아직 정정되지 않았다.** handoff만 읽으면 해소된 것으로 보인다.

**영향.** 다음 작업(class overlap 측정)을 이 지시서대로 실행하면 58개 컬럼으로 비교 키를
만들게 되어 측정 결과가 무효가 된다. 실행 전에 반드시 정정해야 한다.

---

### A-2. 보정(calibration)을 수행하는가

**정본.** `docs/CURRENT_DECISIONS.md` §1 — AURC는 단조변환 불변이므로 보정 전에 계산된다.
**따라서 이 실험은 보정을 수행하지 않는다. ECE/Brier는 범위 밖.**
§2 D-004 — calibration set 없음, 교차검증 없음.

**반대로 적힌 곳 6군데**

| 위치 | 서술 |
|---|---|
| `CLAUDE.md` 46행 | "보정을 거치지 않은 확률에 임계값을 적용하지 않는다" — **항상 적용되는 규약 3개 중 1번** |
| `docs/design-constraints.md` A-1 | "보정을 거친 확률만 임계값 판단에 쓴다" |
| `docs/design-constraints.md` A-2 | "보정기는 학습 데이터와 분리된 데이터로 적합시킨다" |
| `docs/design-constraints.md` A-5 | "배제 공격군은 학습·보정 양쪽에서 모두 제외한다" |
| `docs/metrics-spec.md` §1·§3 | "모든 지표는 **보정 후 확률**을 입력으로 계산한다" / `ece`·`mce`·`brier` 필드 정의 |
| `docs/glossary.md` B절 | `abstention_band` = "**보정 후** 신뢰도 구간" / `calib` = 보정 전용 분할 |
| `experiments/EXP-002` | 실험 자체가 "보정 전후 확률 품질 비교" |

**구조적 문제.** `CLAUDE.md` 40~42행은 `design-constraints.md`·`glossary.md`를 `@`로 import한다.
즉 Claude Code가 세션마다 **가장 먼저 읽는 내용이 현행 결정과 반대**다.
`CURRENT_DECISIONS.md` §5가 "미대조, 충돌 시 이 문서 우선"으로 덮어두었으나,
`CLAUDE.md` 44~48행의 "특히 자주 어겨지는 세 가지" 재강조는 그 우선순위 선언보다 앞에 읽힌다.

---

### A-3. 분할 방식

**정본.** D-004 — 단순 계층 랜덤 2분할 75:25. 그룹 분할·시간 분할·LOAO 없음.

**반대로 적힌 곳**

| 위치 | 서술 |
|---|---|
| `docs/data-notes.md` §3-4 | "분할은 파일(요일) 단위가 아니라 **시간 순서를 고려해** 수행한다. **무작위 분할은** 동일 공격 세션의 플로우를 학습·평가에 나눠 넣어 **누수를 만든다**" |
| `project_context_roadmap.md` D절 전체 | 3분할(60/20/20), 그룹키 `hash(src_ip, dst_ip, attack_label, bucket)`, LOAO 마스크, `bucket_seconds 300`, `min_group_count_for_split 10` |
| `docs/glossary.md` C절 | `split` = train/calib/test, `below_min_group_count` 필드 |

**구조적 문제.** `CLAUDE.md` 54행은 "**데이터 로딩·전처리·분할 코드를 만지기 전 → `docs/data-notes.md`**"를
명시적으로 지시한다. 지시대로 읽으면 현행 결정과 정반대인 지침을 먼저 만난다.

---

### A-4. 저장소 공개 상태 vs git 정책

`docs/git-policy.md` §6-6: **"원격 저장소를 public으로 바꾸지 않는다.
데이터셋 라이선스와 미공개 원고가 포함되어 있다."**

현재 저장소는 공개 상태이며, 자격증명 없이 clone되었다.

부수 사항: 금지 근거로 든 **"미공개 원고"(`manuscript/`)는 저장소에 존재하지 않는다.**
`CLAUDE.md` 69행의 "`manuscript/` 하위 전체를 읽지 않는다"도 없는 디렉토리를 가리킨다.

정책을 개정할지, 저장소를 비공개로 되돌릴지 판단이 필요하다.

---

## B. 한쪽에만 있는 것

### B-1. D-004·D-005 — 저장소가 프로젝트보다 앞서 있다

| 문서 | 상태 |
|---|---|
| `docs/CURRENT_DECISIONS.md` §2 | D-004·D-005가 **"잠정" 표시로 이미 본문 기록됨** |
| `claude/decisions.md` | 여전히 **"다음 결정 (미착수)"** 스텁. 구 D-004(그룹키 진단 자료)만 있음 |
| `claude/handoff_2026-09-13.md` §7 | "D-004 정식 기록", "D-005 정식 기록"이 **미완 항목**으로 남아 있음 |

세 문서가 같은 결정에 대해 서로 다른 진행 단계를 주장한다. 어느 쪽이 정본인지 불명확하다.

또한 `claude/decisions.md`의 기록 규칙은 "5개 항목(질문·결정·근거·영향·미결)이 모두 채워져야 확정"인데,
`CURRENT_DECISIONS.md`의 D-004는 결정 내용과 해석 규칙만 있고 **근거란이 없다.**

### B-2. 분할 방식 기각 근거가 handoff에만 있다

`handoff` §5의 아래 내용이 `decisions.md`·`CURRENT_DECISIONS.md` 어디에도 없다.

- Temporal 분할 붕괴 — 13개 클래스 중 2개만 test 생존, 전 모델 macro-F1 ≈ 0.50
- 5-tuple group 분할 무의미 — 그룹당 평균 ~2행, RF macro-F1 0.769 → 0.778로 **상승**
- Campaign group 분할 붕괴 — campaign ≈ 라벨 자체
- 출처: Moczkodan & Ragab, *Do Transformers Actually Help Intrusion Detection?*, arXiv:2606.11098 (2026)
  — **주의: 공개판(2,827,677 flows) 기준이므로 설계 근거로만 쓰고 수치 비교 대상으로 쓰지 않는다**
- baseline 75:25 출처: Engelen et al., WTMC 2021 원문 확인
  — **주의: 분류기가 Random Forest, 평가가 per-class. CNS2022는 고정 split을 규정하지 않았다**

handoff는 인계용 문서다. D-004를 정식 기록할 때 이 표가 근거란으로 이동하지 않으면 유실된다.
`decisions.md` 기록 규칙 3번(출처 필수)이 이를 요구한다.

### B-3. whitelist 구현 미결 항목이 이미 해소되어 있다

`claude/decisions.md` D-003 §7-3·§8은 "**`configs/features.yaml`**에 whitelist를 기록"을 미결로 둔다.
실제로는 **`configs/features_whitelist.json`으로 구현 완료**되어 있다
(include 59 / exclude 32, 각 제외 항목에 `code`·`axis`·`reason` 부여, 미분류 0개).

- 파일명이 `features.yaml` → `features_whitelist.json`으로 바뀐 사실이 프로젝트 문서에 미반영
- 다만 §7-3의 **검증 항목 3개**(입력 컬럼 집합 일치 / 미분류 0개 / exclude 0개 존재)는
  여전히 미구현이다. 학습 코드가 아직 없기 때문이며, whitelist 파일 존재만으로 해소되지 않는다

### B-4. 데이터 폴더는 이미 개명되어 있다

세 문서(`decisions.md` 서두, `dataset_audit` 서두, `CURRENT_DECISIONS.md` §0, task 문서 §3-1)가
모두 "로컬 경로는 `data/CICIDS2017_improved/`로 **미정정 상태**"라고 적는다.

실제 PC 상태:

```
data/CICIDS2017_CNS2022_reprocessed/   ← 이미 개명됨. CSV 5개 (monday~friday)
data/CICIDS2017_improved.zip           ← 원본 zip, 343MB
```

"미정정" 서술 4곳이 낡았다. 단 `configs/exp/cicids_prep.yaml`의 경로는 폐기 대상이므로
그대로 두는 것이 맞다.

---

## C. 가리키는 대상이 없는 참조

`docs/glossary.md` A-2 규칙 1번은 "정의되지 않은 식별자를 참조 형태로 쓰면 그 순간 유령 참조가 된다"고
규정한다. 아래는 그 규칙을 저장소 스스로 위반하고 있는 목록이다.

| # | 참조 대상 | 참조하는 곳 | 실제 |
|---|---|---|---|
| C-1 | `ADR-001` | `QUEUE.md` 2곳, `EXP-003` 3곳, `EXP-005` 1곳, `glossary.md` 2곳 — **총 8곳** | `docs/decisions/`에 `.gitkeep`만. 존재하지 않음 |
| C-2 | `configs/base.yaml`의 `gating.lower/upper` | `CLAUDE.md` 27행, `design-constraints.md` A-3, `QUEUE.md` §2-2 | `configs/`에는 `exp/`와 `features_whitelist.json`뿐 |
| C-3 | `make exp ID=EXP-XXX` | `CLAUDE.md` 실험 실행 절차 4번 | Makefile 타겟은 `prep-dataset`, `prep-dataset-loao`, `test` 3개뿐 |
| C-4 | `guard-clean` 타겟 | `git-policy.md` §4 말미 | Makefile에 없음 |
| C-5 | `manuscript/` | `CLAUDE.md` 69행, `git-policy.md` §5·§6-6 | 디렉토리 없음 |
| C-6 | 결정 ID 체계 | `glossary.md` A절은 `ADR-NNN` | 실제 운용은 `D-NNN`. handoff §7-6에 미결로 있으나 glossary 미갱신 |
| C-7 | `project_context_roadmap.md` | `glossary.md` A절이 단계/정책/절 기호의 **정의처**로 지목 | `decisions.md` 서두가 "로드맵 10단계를 대체한다"고 선언, `CLAUDE.md` 22행이 정책 1-1~1-12·단계 1~10을 무효로 선언. **정의처는 무효인데 참조 체계는 살아 있다** |

`ADR-001`은 특히 문제다. `QUEUE.md` §2-4와 §4는 "`ADR-001`이 EXP-003을 참조하고 있으므로
이 ID의 의미를 바꾸거나 재번호하지 않는다"를 **EXP-003 ID를 고정하는 근거**로 삼는데,
그 근거 문서가 존재하지 않는다.

---

## D. 환경 기록이 낡음

| # | 항목 | 문서 기록 | 실제 |
|---|---|---|---|
| D-1 | 저장소 경로 | `environment.md` 11행 — `C:\Users\user1\RUSExperiment` | `C:\Users\wan2t\RUSExperiment`. PC가 교체됨 |
| D-2 | 런타임 | Python 3.14.7 / uv 0.12.12 / pandas 3.0.5 / make 미설치 | 전부 **구 PC의 2026-09-10 확인값**. 현 PC 미검증 |
| D-3 | Cowork 브리지 | 저장소에 기록 없음 | 파일 읽기(stage) HTTP 401, PC 셸 마운트 실패. handoff §9에만 있음 |
| D-4 | `final_training_table.parquet` | `dataset_audit` §5 미결 — "400MB 초과로 컬럼 확인 불가" | 현 PC의 `data/`에 **그 파일이 없다**. 폐기 파이프라인 산출물이므로 재생성 불필요하나 미결 목록에는 남아 있음 |

---

## E. 정정 우선순위

1. **A-1 `Protocol`** — 다음 작업(class overlap 측정)을 무효화한다. 실행 전 필수.
2. **A-2 보정 / A-3 분할** — Claude Code가 세션마다 먼저 읽는 파일에 반대 지침이 있다.
   `CURRENT_DECISIONS.md` §5의 권장 조치(`_superseded/`로 격리)를 실행하거나,
   최소한 해당 파일 머리에 폐기 표시를 달아야 한다.
3. **C-1 `ADR-001`** — 실험 ID 고정 근거가 비어 있다. ADR 문서를 쓰거나, `D-NNN`으로 체계를 통일하고
   glossary A절과 QUEUE.md 참조를 함께 고쳐야 한다.
4. **B-1 D-004·D-005 정본 확정** — 근거란(B-2)을 채워 한 곳에 확정 기록.
5. **A-4 저장소 공개** — 정책 개정 또는 비공개 전환 판단.
6. **B-3·B-4·D-1~D-4** — 낡은 서술 정정. 위험도는 낮다.
