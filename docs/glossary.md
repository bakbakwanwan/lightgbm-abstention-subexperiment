# 용어 및 식별자 고정표

이 문서는 프로젝트 내 모든 식별자와 용어의 **단일 정의처**다.
코드 변수명, `metrics.json` 필드명, 문서 참조는 전부 이 표를 따른다.
여기에 없는 식별자를 새로 만들지 않는다. 필요하면 이 문서를 먼저 갱신한다.

> **2026-09-13 개정.** 결정 ID 체계를 `ADR-NNN`에서 `D-NNN`으로 통일하고,
> 무효화된 로드맵을 정의처에서 제거하고, 폐기된 3분할·보정 전제 용어를 정리했다.
> 개정 사유는 `docs/doc_consistency_audit_2026-09-13.md`에 있다.

---

## A. 식별자 체계

이 프로젝트에는 두 개의 독립된 번호 체계가 있다. 서로 다른 것을 가리키므로 혼용하지 않는다.

| 체계 | 형식 | 가리키는 것 | 정의된 곳 |
|---|---|---|---|
| 결정 ID | `D-NNN` | 확정된 설계 결정 1건 | `docs/CURRENT_DECISIONS.md` |
| 실험 ID | `EXP-NNN` | 저장소에서 실행되는 실험 1건 | `experiments/QUEUE.md` |

### A-1. 폐기된 식별자 체계

아래 세 체계는 **더 이상 쓰지 않는다.** 과거 문서에 등장하면 폐기된 설계를 가리키는 것이다.

| 폐기된 체계 | 형식 | 폐기 사유 |
|---|---|---|
| 결정 ID (구) | `ADR-NNN` | `docs/decisions/`에 실물이 한 건도 작성되지 않은 채 8곳에서 참조되었다. `D-NNN`으로 통일 |
| 단계 번호 | `N단계` (1~10) | 로드맵 10단계 체계가 `CURRENT_DECISIONS.md`로 대체됨 |
| 정책 번호 | `1-1` ~ `1-12` | 위와 동일 |
| 절 기호 | `A-3`, `C-8`, `D-7` 등 | 로드맵 문서 내부 참조. 로드맵이 `_superseded/`로 이동 |

**`ADR-001`은 존재한 적이 없다.** 구 `experiments/QUEUE.md`·`EXP-003`·`EXP-005`가
"`ADR-001`이 EXP-003을 참조하므로 이 ID의 의미를 바꾸지 말 것"을 실험 ID 고정의 근거로
삼았으나, 그 근거 문서는 작성되지 않았다. 해당 파일들은 `_superseded/`로 이동했으며,
재작성 시 `D-NNN`을 참조해야 한다.

### A-2. 참조 규칙

1. 문서에서 다른 문서의 식별자를 참조할 때는 **참조 대상이 실제로 정의되어 있는지 먼저 확인한다.**
   정의되지 않은 식별자를 참조 형태로 쓰면 그 순간 유령 참조가 된다.
   (`ADR-001` 8곳이 정확히 이 실패 사례다.)
2. 새 식별자를 만들 때는 이 문서의 A절 표에 먼저 등록하고 사용한다.
3. 재실행은 새 ID로 만든다: `EXP-003-r2`. 기존 ID의 결과를 덮어쓰지 않는다.
4. 기존 식별자의 **의미를 바꾸지 않는다.** 의미가 달라지면 번호를 새로 딴다.

### A-3. 같은 사실을 두 곳에 쓰지 않는다

| 사실 | 유일한 정본 |
|---|---|
| 결정과 근거 | `docs/CURRENT_DECISIONS.md` |
| 학습 입력 컬럼 목록 | `configs/features_whitelist.json` |
| 레이블 전수·Attempted 코드북 | `docs/dataset_audit_2026-09-11.md` |
| 원본 91컬럼 통계 | `docs/feature_inventory_2026-09-12.md` |
| 용어·식별자 | 이 문서 |

---

## B. 연구 용어 ↔ 코드 식별자

| 국문 | 코드 식별자 / 영문 | 정의 |
|---|---|---|
| 판정 유보 | `abstention` | 1차 모델이 판정을 내리지 않고 심층 검증으로 넘기는 동작 |
| 유보 구간 | `abstention_band` | 유보가 발생하는 예측 확률 구간. `[lower, upper]`. 사전 고정하지 않고 test 확률 전량을 오프라인 스윕해 구한다 |
| 유보 비율 | `abstention_rate` | 전체 플로우 대비 유보된 플로우의 비율 |
| 에스컬레이션 비율 | `escalation_ratio` | 전체 플로우 대비 심층 검증으로 넘어간 비율 |
| 검증 예산 | `verification_budget` | 심층 검증에 할당 가능한 처리량(초당 플로우). 유보 구간 폭을 결정하는 상한 제약 |
| 위험-커버리지 곡선 | `risk_coverage_curve` | 커버리지(비유보 비율) 대비 오류율 곡선 |
| 위험-커버리지 곡선 하 면적 | `aurc` | 위 곡선의 적분값. 낮을수록 좋음. **이 서브실험의 주 지표.** 단조변환 불변이므로 보정 전에 계산된다 |
| 관찰군 | `observation_group` | 학습·평가 지표 산출에서 제외하고 별도 관찰하는 행 집합. 값: `none` / `attempted` / `invalid_class` |
| Attempted 관찰군 | `attempted` | `Label`이 `- Attempted`로 끝나는 11종 11,979행 (D-001) |
| 무효 클래스 관찰군 | `invalid_class` | `Label == "DoS Hulk"` 158,468행 (D-002) |
| 분포 외 스코어 | `ood_score` | 정상 트래픽 기준 이상 정도. 보조 게이트 후보. 미착수 |
| 예측 기여 특징 | `feature_attribution` | SHAP 등이 산출한 예측 기여도. **인과적 이유가 아님** |
| 검색된 근거 문서 | `retrieved_evidence_documents` | RAG가 회수한 CTI/ATT&CK/CVE 문서 (2·3차 계층) |
| 문서 지지율 | `groundedness` | 제시된 근거가 검색된 문서에 의해 지지되는 비율 (2·3차 계층) |

### B-1. 이 서브실험의 범위 밖인 용어

아래는 **정의는 유지하되 이번 서브실험에서 산출하지 않는다.** D-004가 보정을 수행하지 않기로 했다.

| 국문 | 코드 식별자 | 상태 |
|---|---|---|
| 확률 보정 | `calibration` | **범위 밖.** 이 실험에서는 항상 `none` |
| 보정 세트 | `calib` | **범위 밖.** D-004는 train/test 2분할이며 calib split이 없다 |
| 기대 보정 오차 | `ece` | **범위 밖** |
| 적응형 보정 오차 | `adaptive_ece` | **범위 밖** |
| 브라이어 점수 | `brier_score` | **범위 밖** |
| 미학습 공격군 일반화 평가 | `LOAO` | **범위 밖.** D-004는 LOAO를 쓰지 않는다 |
| 배제 공격군 | `held_out_attack` | **범위 밖.** 위와 동일 |

본 연구(3단 구조) 단계에서 다시 쓰게 되면 그때 이 절에서 B절로 옮긴다.

---

## C. 분할 관련 필드명 (D-004 기준)

| 필드 | 정의 |
|---|---|
| `split` | 값: `train` / `test`. **`calib`는 없다** (D-004) |
| `observation_group` | B절 참조. `none` / `attempted` / `invalid_class` |

### C-1. 폐기된 필드명

아래는 폐기된 파이프라인(`_superseded/src/cicids_prep/`)의 산출물이다. **새 코드에서 쓰지 않는다.**

`row_uid`, `group_id`, `original_split`, `below_min_group_count`, `label_conflict_flag`,
`invalid_negative_duration_flag`, `reserved_for_early_features.parquet`,
`dropped_constant_duplicate_columns.json`, `clipping_values.json`,
`split_summary_report.csv`, `validation_log.json`, `duplicate_flow_report.{json,csv}`

**예외:** `dataset_manifest.json`은 유효하다. 재생성 대상이며 필드는
`file_sha256`, `row_counts`, `manifest_created_at`, `source_zip_sha256`이다
(`original_download_date` 필드는 만들지 않는다 — 복원 불가능한 정보를 임의로 채우지 않는다).

---

## D. 폐기된 표현

아래 표현은 코드·문서·논문 어디에도 쓰지 않는다.

- **3분기 판정** (정상/의심/공격) — `abstention` 프레이밍으로 대체 확정
- **재라벨링** — 검증 결과의 라벨 환류는 기각됨. 환류 범위는 임계값 조정까지
- **피처 기여도**, **판단 근거 특징** — `예측 기여 특징`(feature attribution)으로 통일
- **밀리초 단위**, 측정 전 지연 수치 — 실측 전 수치 주장 금지
- **정확도(accuracy)를 주 지표로** — 클래스 불균형이 심해 무의미
- **`ADR-NNN`** — `D-NNN`으로 대체
- **"CNS2022 공식 split"** — CNS2022는 고정 split을 규정하지 않았다 (D-004 §3-2)

---

## E. 갱신 규칙

1. 새 식별자 도입, 필드명 변경, 용어 확정·폐기가 발생하면 **이 문서를 먼저 고치고** 코드·문서를 따라 고친다.
2. `metrics.json` 필드명과 B절 코드 식별자가 어긋나면 이 문서가 우선이다.
3. 갱신 시 아래 이력에 날짜와 변경 내용을 한 줄 추가한다.

**갱신 이력**

- 2026-09-10 — 최초 작성. 식별자 체계 4종(단계/정책/EXP/ADR) 정의, 1·2단계 산출물 필드명 등록.
- 2026-09-13 — 결정 ID를 `ADR-NNN` → `D-NNN`으로 통일(유령 참조 8곳 해소).
  무효화된 로드맵을 정의처에서 제거. 보정·LOAO·3분할 관련 용어를 B-1·C-1로 격리.
  A-3(같은 사실을 두 곳에 쓰지 않는다) 신설.
