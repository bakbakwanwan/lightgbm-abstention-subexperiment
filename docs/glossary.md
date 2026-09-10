# 용어 및 식별자 고정표

이 문서는 프로젝트 내 모든 식별자와 용어의 **단일 정의처**다.
코드 변수명, `metrics.json` 필드명, 문서 참조는 전부 이 표를 따른다.
여기에 없는 식별자를 새로 만들지 않는다. 필요하면 이 문서를 먼저 갱신한다.

---

## A. 식별자 체계

이 프로젝트에는 네 개의 독립된 번호 체계가 있다. 서로 다른 것을 가리키므로 혼용하지 않는다.

| 체계 | 형식 | 가리키는 것 | 정의된 곳 |
|---|---|---|---|
| 단계 번호 | `N단계` (1~10) | 연구 설계상의 작업 단위 | `project_context_roadmap.md` B절 |
| 정책 번호 | `1-1` ~ `1-12` | 1단계 데이터 처리 확정 정책 | `project_context_roadmap.md` C-2 |
| 절 기호 | `A-3`, `C-8`, `D-7` 등 | 로드맵 문서 내부 절 참조 | `project_context_roadmap.md` |
| 실험 ID | `EXP-NNN` | 저장소에서 실행되는 실험 1건 | `experiments/QUEUE.md` |
| 결정 ID | `ADR-NNN` | 확정·기각된 설계 결정 1건 | `docs/decisions/` |

### A-1. 단계 번호와 실험 ID의 관계

**둘은 1:1이 아니다.** 단계는 연구 설계 단위이고, 실험 ID는 `make exp`로 한 번에 실행되는
실행 단위다. 한 실험이 여러 단계를 포함할 수 있고, 한 단계가 실험 여러 건으로 쪼개질 수도 있다.
대응표는 `experiments/QUEUE.md`가 유일한 근거이며, 로드맵 B절 표와 함께 갱신한다.

### A-2. 참조 규칙

1. 문서에서 다른 문서의 식별자를 참조할 때는 **참조 대상이 실제로 정의되어 있는지 먼저 확인한다.**
   정의되지 않은 식별자를 참조 형태로 쓰면 그 순간 유령 참조가 된다.
2. 새 식별자를 만들 때는 이 문서의 A절 표에 먼저 등록하고 사용한다.
3. 재실행은 새 ID로 만든다: `EXP-003-r2`. 기존 ID의 결과를 덮어쓰지 않는다.
4. 기존 식별자의 **의미를 바꾸지 않는다.** 의미가 달라지면 번호를 새로 딴다.
   (예: `EXP-003`은 항상 배제 공격군 신뢰도 분포를 가리킨다. `ADR-001`이 이 ID를 참조하고 있다.)

---

## B. 연구 용어 ↔ 코드 식별자

| 국문 | 코드 식별자 / 영문 | 정의 |
|---|---|---|
| 판정 유보 | `abstention` | 1차 모델이 판정을 내리지 않고 심층 검증으로 넘기는 동작 |
| 유보 구간 | `abstention_band` | 유보가 발생하는 **보정 후** 신뢰도 구간. `[lower, upper]`. 폭은 config로만 주입 |
| 유보 비율 | `abstention_rate` | 전체 플로우 대비 유보된 플로우의 비율 |
| 에스컬레이션 비율 | `escalation_ratio` | 전체 플로우 대비 심층 검증으로 넘어간 비율 |
| 검증 예산 | `verification_budget` | 심층 검증에 할당 가능한 처리량(초당 플로우). 유보 구간 폭을 결정하는 상한 제약 |
| 배제 공격군 | `held_out_attack` | LOAO에서 학습·보정 양쪽 모두에서 제외한 공격 유형 |
| 미학습 공격군 일반화 평가 | `LOAO` (Leave-One-Attack-Out) | 특정 공격군을 완전 배제하고 학습한 뒤 그 공격군으로 평가하는 프로토콜 |
| 위험-커버리지 곡선 | `risk_coverage_curve` | 커버리지(비유보 비율) 대비 오류율 곡선 |
| 위험-커버리지 곡선 하 면적 | `aurc` | 위 곡선의 적분값. 낮을수록 좋음 |
| 기대 보정 오차 | `ece` | Expected Calibration Error. 단독 사용 금지, Brier·신뢰도 다이어그램 병행 |
| 적응형 보정 오차 | `adaptive_ece` | 등빈도 구간 기반 ECE |
| 브라이어 점수 | `brier_score` | 확률 예측의 제곱 오차 |
| 확률 보정 | `calibration` | 값: `none` / `platt` / `isotonic` / `beta` |
| 보정 세트 | `calib` | 학습·평가와 분리된 보정기 적합 전용 분할 |
| 분포 외 스코어 | `ood_score` | 정상 트래픽 기준 이상 정도. 보조 게이트 후보(EXP-006) |
| 예측 기여 특징 | `feature_attribution` | SHAP 등이 산출한 예측 기여도. **인과적 이유가 아님** |
| 검색된 근거 문서 | `retrieved_evidence_documents` | RAG가 회수한 CTI/ATT&CK/CVE 문서 |
| 문서 지지율 | `groundedness` | 제시된 근거가 검색된 문서에 의해 지지되는 비율 |

---

## C. 데이터 파이프라인 필드명 (1·2단계 산출물)

코드에서 이 이름을 임의로 바꾸지 않는다. 로드맵 C-8·D-8의 실행 결과가 이 이름으로 기록되어 있다.

| 필드 / 파일 | 정의 | 근거 정책 |
|---|---|---|
| `row_uid` | `f"{day}_{id}"`. 요일 병합 후의 전역 유일 행 식별자. 원본 `id`는 요일마다 1부터 재시작하므로 사용 금지 | C-9 |
| `split` | 값: `train` / `calib` / `test` | 2단계 |
| `label_conflict_flag` | 완화기준 중복(5-tuple+timestamp 일치)인데 라벨이 다른 행. **자동 삭제 금지** | 1-7 |
| `invalid_negative_duration_flag` | Duration이 음수인 행. CICFlowMeter 계산 버그 가능성. **자동 삭제 금지** | 1-11 |
| `below_min_group_count` | 그룹 수가 `min_group_count_for_split` 미만이라 전량 test로 배정된 레이블 표시 | D-3, D-8 |
| `reserved_for_early_features.parquet` | 기본 학습 테이블에서 뺀 보류 컬럼의 원본값(`row_uid` + `Dst Port`) | 1-5 |
| `dataset_manifest.json` | `file_sha256`, `repo_commit_hash`, `manifest_created_at`. 다운로드 일자 불명 시 필드 자체 생략 | 1-9 |
| `duplicate_flow_report.{json,csv}` | 완전일치/완화기준 중복 검출 건수, 라벨 충돌 건수 | 1-2, 1-7 |
| `dropped_constant_duplicate_columns.json` | train 기준 제거·유지 컬럼 목록과 판단 근거 | 1-6 |
| `clipping_values.json` | 컬럼별 클리핑 상·하한(train 기준) | 1-8, 1-11 |
| `split_summary_report.csv` | 요일×레이블×split 행 수, `below_min_group_count` 표시 | D-8 |
| `validation_log.json` | 분할 검증 9개 항목 pass/fail | D-6 |

---

## D. 폐기된 표현

아래 표현은 코드·문서·논문 어디에도 쓰지 않는다.

- **3분기 판정** (정상/의심/공격) — `abstention` 프레이밍으로 대체 확정
- **재라벨링** — 검증 결과의 라벨 환류는 기각됨. 환류 범위는 신뢰도 보정과 임계값 조정까지
- **피처 기여도**, **판단 근거 특징** — `예측 기여 특징`(feature attribution)으로 통일
- **밀리초 단위**, 측정 전 지연 수치 — 실측 전 수치 주장 금지
- **정확도(accuracy)를 주 지표로** — 클래스 불균형이 심해 무의미

---

## E. 갱신 규칙

1. 새 식별자 도입, 필드명 변경, 용어 확정·폐기가 발생하면 **이 문서를 먼저 고치고** 코드·문서를 따라 고친다.
2. `metrics.json` 필드명과 B절 코드 식별자가 어긋나면 이 문서가 우선이다.
3. 갱신 시 아래 이력에 날짜와 변경 내용을 한 줄 추가한다.

**갱신 이력**
- 2026-09-10 — 최초 작성. 식별자 체계 4종(단계/정책/EXP/ADR) 정의, 1·2단계 산출물 필드명 등록.
  기존에 `EXP-NNN`이 어디에도 정의되지 않은 채 참조되던 문제 해소.
