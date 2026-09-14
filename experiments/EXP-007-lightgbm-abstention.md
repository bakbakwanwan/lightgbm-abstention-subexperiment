---
id: EXP-007
title: LightGBM confidence abstention existence test
status: ready
depends_on: []
created: 2026-09-14
---

## 1. 질문

D-004 주 분할에서 LightGBM의 `confidence`가 오류를 무작위보다 잘 순위화하여, 제한된 검증 예산 안에서 실질적인 유보 구간을 만드는가.

## 2. 입력

- 데이터셋 / 버전: `results/d004_splits/split_manifest.json`의 원본 CSV 및 ZIP SHA256과 실행 시 재계산한 SHA256이 모두 일치해야 한다.
- 대상 행 집합: D-001·D-002 적용 후 1,929,529행. 관찰군은 학습·정답 기반 평가에서 제외한다.
- 사용 split: D-004 `group_seed42`가 주 분석, `row_random_seed42`가 낙관적 민감도 분석이다.
- 관찰군 취급: 주 분석 band를 `attempted`와 `invalid_class`에 그대로 적용하고 분포와 포함 수만 보고한다.
- 피처: `configs/features_whitelist.json#include` 59개.
- seed: 42.
- 설정 파일: `configs/exp/EXP-007.yaml`.
- 선행 산출물: `results/d004_splits/` 및 `reports/split_feasibility/conflict_group_assignment.csv`.

내부 validation, 후보 선택, 재학습, confidence, AURC, budget, 보조 지표의 모든 계산 규칙은 `docs/CURRENT_DECISIONS.md` D-006을 그대로 따른다. 이 문서에 목록이나 기준 수치를 복제하지 않는다.

## 3. 산출물 스키마

`results/EXP-007/` 아래에 다음을 기록한다.

- `metrics.json`, `manifest.json`, `validation_checks.json`
- `candidate_history.json`
- `predictions/{group_seed42,row_random_seed42}.parquet`: 해당 분석의 모든 외부 test 및 관찰군 예측
- `aurc_curve/{group_seed42,row_random_seed42}.csv.gz`: 모든 고유 confidence 경계의 곡선
- `budget_summary.csv`, `label_summary.csv`, `overlap_summary.csv`, `observation_summary.csv`
- `prediction_distribution_summary.csv`: 전체 test와 정답/오류·BENIGN/공격별 고정 분위수

비율 지표에는 가능한 모든 분자·분모 count를 함께 둔다. JSON은 NaN/Infinity를 허용하지 않는다.

## 4. 성공 / 실패 판정 기준

- **성공:** D-006 §2 항목 33을 모두 만족한다.
- **실패:** D-006 §2 항목 34 중 하나를 만족한다.
- **과학적 판정 불가:** D-006 §2 항목 35에 해당한다.
- **기술적 판정 불가:** D-006 §2 항목 36 또는 실행 guard 실패에 해당한다.

최종 판정에는 `group_seed42`만 사용한다. 민감도·관찰군·class-overlap 결과는 판정을 바꾸지 않는다.

## 5. 결과 요약

- 수치: 실행 전 공란.
- 관측된 이상 사항: 실행 전 공란.

## 6. 다음 분기

- 성공 시: 유보 구간 존재를 D-004 주 분할과 현재 모델·confidence 조건으로 한정해 보고하고, 배포 threshold는 별도 과제로 둔다.
- 실패 시: D-006의 제한 문구로만 결론 내리고, 더 엄격한 분할 또는 OOD 보조 게이트는 별도 사전 스펙으로 검토한다.
