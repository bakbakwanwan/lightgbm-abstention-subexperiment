# 문서 색인

이 저장소의 문서가 어디에 있는지 찾기 위한 지도다. 내용의 정본은 각 문서 자신이며,
이 색인은 정본을 옮겨 적지 않는다. 목록·수치가 여기와 원본 문서에서 어긋나면
원본 문서가 항상 옳다.

새 문서를 추가하거나 기존 문서를 옮기면 이 파일도 함께 갱신한다.

---

## 시작점

| 목적 | 문서 |
|---|---|
| Claude Code로 작업할 때 지켜야 할 규약 전체 | [CLAUDE.md](CLAUDE.md) |
| 지금 무엇이 확정되었고 왜 그런지 (결정 D-001~D-006) | [docs/CURRENT_DECISIONS.md](docs/CURRENT_DECISIONS.md) |
| 지금 당장 해야 할 작업 | [docs/CURRENT_DECISIONS.md](docs/CURRENT_DECISIONS.md)의 "다음 작업"과 EXP-008 확정 스펙 |

---

## docs/ — 결정·감사·용어 (정본)

| 문서 | 내용 |
|---|---|
| [CURRENT_DECISIONS.md](docs/CURRENT_DECISIONS.md) | **저장소의 유일한 결정 정본.** D-001~D-006과 각 근거 |
| [glossary.md](docs/glossary.md) | 용어·식별자 고정표. 코드 변수명·`metrics.json` 필드명의 정의처 |
| [dataset_audit_2026-09-11.md](docs/dataset_audit_2026-09-11.md) | 레이블 전수·파이프라인 감사, Attempted 코드북 |
| [feature_inventory_2026-09-12.md](docs/feature_inventory_2026-09-12.md) | 원본 91컬럼의 분포·고유값·결측 통계 |
| [doc_consistency_audit_2026-09-13.md](docs/doc_consistency_audit_2026-09-13.md) | 2026-09-13 문서 대조 감사 — Protocol 오기 등 발견 경위 |
| [environment.md](docs/environment.md) | 실행 환경(OS·의존성) — 미확정 상태 |
| [git-policy.md](docs/git-policy.md) | git 운영 지시문 |
| [ml_training_evaluation_method_comparison.md](docs/ml_training_evaluation_method_comparison.md) | D-006 학습 목적함수·early stopping·최종 평가 지표 선택지 비교 자료 |
| `decisions/` | 비어 있음(`.gitkeep`만 존재) |

## configs/ — 실행 설정 (쓰기 가능)

| 문서 | 내용 |
|---|---|
| [features_whitelist.json](configs/features_whitelist.json) | 학습 입력 컬럼 정본. `include` 59 / `exclude` 32 |
| `exp/` | 실험별 설정 파일을 두는 곳. 현재 `EXP-007.yaml`, `EXP-008.yaml`이 있음 |

## tasks/ — 확정 스펙 이전 단계의 작업 지시서

| 문서 | 내용 |
|---|---|
| [task_duplicate_class_overlap_measurement.md](tasks/task_duplicate_class_overlap_measurement.md) | 중복 행·class overlap 측정 지시서 (완료, D-004 개정 근거) |
| [instruction_attempted_hulk_investigation.md](tasks/instruction_attempted_hulk_investigation.md) | Attempted·DoS Hulk 조사 지시서 (완료, D-001·D-002의 근거) |
| [exp008_group_split_stability_proposal.md](tasks/exp008_group_split_stability_proposal.md) | 승인 완료된 EXP-008 제안 이력. 확정 내용은 실험 스펙 참조 |
| [external_labeled_dataset_feasibility.md](tasks/external_labeled_dataset_feasibility.md) | 독립 라벨 데이터 후보와 사용 전 감사 항목 조사 |

## experiments/ — 성공·실패 기준을 갖춘 확정 실험 스펙

| 문서 | 내용 |
|---|---|
| [TEMPLATE.md](experiments/TEMPLATE.md) | 새 실험 스펙 작성 템플릿 |
| [EXP-007-lightgbm-abstention.md](experiments/EXP-007-lightgbm-abstention.md) | confidence 기반 유보 구간 존재 검증 스펙 |
| [EXP-008-group-split-stability.md](experiments/EXP-008-group-split-stability.md) | 완전일치 그룹 분할 seed 민감도 분석 확정 스펙 |
| `QUEUE.md`, `EXP-001`~`EXP-006` | 없음 — 전부 `_superseded/`로 이동, 재작성 전 |

## reports/ — 완료된 조사의 산출물

| 경로 | 내용 |
|---|---|
| [reports/attempted_hulk_investigation/](reports/attempted_hulk_investigation/) | D-001·D-002의 근거 자료. `_superseded/` 대상 아님 — 유효 |
| [reports/class_overlap/](reports/class_overlap/) | 59-feature 중복 및 정상·공격 class overlap 실측 |
| [reports/split_feasibility/](reports/split_feasibility/) | D-004 완전일치 그룹 분할 가능성 및 랜덤 분할 누수 측정 |

## scripts/ — 실행 코드 (쓰기 가능)

| 경로 | 내용 |
|---|---|
| `scripts/investigation/attempted_hulk/` | 위 조사에 쓰인 코드 |
| `scripts/investigation/class_overlap/` | 59-feature 중복 및 class overlap 측정 코드 |
| `scripts/investigation/split_feasibility/` | D-004 그룹 분할 가능성 측정 코드 |
| `scripts/build_d004_splits.py` | D-004 주 분석·민감도 분석 split 생성 및 검증 진입점 |

## results/ — 고정 실행 산출물

| 경로 | 내용 |
|---|---|
| `results/d004_splits/` | D-004 주 분석·민감도 분석의 요일별 split 배정과 manifest |
| `results/EXP-007/` | EXP-007 실행 산출물 |

---

## _superseded/ — 폐기된 설계·코드 (참조 금지, 이력 보존용)

**현행 사양이 아니다.** "과거에 왜 그렇게 했는지" 추적할 때만 연다.
전체 목록과 각 폐기 사유는 [CLAUDE.md의 해당 표](CLAUDE.md)에 있다 — 여기에 다시 옮겨 적지 않는다.

- `docs/` — 보정·3분할 전제 설계 문서, 폐기된 파이프라인의 진행 기록
- `experiments/` — 보정·Dst Port 재도입·LOAO 전제 실험 스펙 6건 + QUEUE.md
- `tasks/` — split_protocol_proposal.md
- `configs/exp/cicids_prep.yaml`, `src/cicids_prep/`, `tests/cicids_prep/`, `scripts/build_dataset.py`, `results/cicids_prep/` — 폐기된 데이터 파이프라인 구현·테스트·진입점
- `Makefile` — 전 타겟이 위 진입점을 가리켜 함께 이동. 새 진입점은 재작성될 실험 스펙과 함께 정의

---

## 갱신 이력

- 2026-09-14 — 최초 작성. 결정 문서 통합(§단일 정본화)과 `_superseded/` 격리 완료 이후 스냅샷.
- 2026-09-14 — D-006 학습·평가 방식 비교 자료를 색인에 추가.
- 2026-09-15 — EXP-008 실행 전 제안서와 독립 라벨 데이터 후보 조사를 tasks/ 색인에 추가.
- 2026-09-16 — EXP-008 확정 스펙을 추가하고 승인 완료된 task를 이력 포인터로 전환.
- 2026-09-16 — EXP-008 실행 설정을 추가하고 다음 작업을 공용 실행 코드 구현으로 갱신.
