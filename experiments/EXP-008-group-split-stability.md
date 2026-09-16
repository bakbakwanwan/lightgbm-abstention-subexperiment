---
id: EXP-008
title: LightGBM confidence group-split stability analysis
status: ready
depends_on: [EXP-007]
created: 2026-09-16
---

# EXP-008 완전일치 그룹 분할 seed 민감도 분석

> 질문·입력·판정 기준과 실행·산출물 계약은 2026-09-16에 승인되었다.
> 구현 완료 전에는 아래 실행 명령을 사용하지 않는다.
>
> 결정과 수치의 정본은 `docs/CURRENT_DECISIONS.md` D-004 결정 8~18이다.
> 이 스펙과 정본이 충돌하면 D-004가 우선한다.

## 1. 질문과 주장 범위

D-004의 59-feature 완전일치 그룹 분할에서 배정 seed만 바꿨을 때도 다음 두 성질이
사전에 정한 허용폭 안에서 유지되는가.

1. EXP-007에서 관찰한 LightGBM `confidence`의 오류 순위 효과
2. EXP-007에서 정한 고정 1%·5% `confidence_threshold`가 만드는 실제 유보 규모

이는 같은 개선 CIC-IDS2017 대상 행 집합을 다시 배정하는 **구조적 분할 민감도 분석**이다.
독립 데이터셋 재현, 외부 환경 일반화, 배포 처리량 보장, 희소 클래스별 seed 변동성 추정,
고정 경계의 오류 포착 효과 유지를 주장하지 않는다. EXP-007의 `group_seed42` 결과와
성공 판정도 변경하지 않는다.

순위 판정과 고정 경계 처리량 판정은 서로 다른 질문에 답하므로 하나의 성공·실패 상태로
합치지 않는다. 두 판정의 허용 결론은 D-004 결정 14를 따른다.

## 2. 입력과 고정 조건

### 2.1 데이터와 대상 행

- 원본 CSV·ZIP·whitelist는 EXP-007과 같은 파일을 사용하며, SHA256은 EXP-007 정본과
  실행 시 재계산값이 일치해야 한다.
- 대상 행과 관찰군 처리는 D-001·D-002와 D-004를 그대로 따른다.
- 학습 입력은 `configs/features_whitelist.json#include`이며, 목록을 이 문서나 코드에
  복제하지 않는다.
- `Protocol` 처리, `Flow Bytes/s` Infinity 처리, 이진 라벨, 이진 판정 임계값,
  `confidence`, 동률 처리는 EXP-007 및 용어 정본과 동일하다.
- 확률 보정·보정 세트·ECE·Brier는 범위 밖이다.

### 2.2 외부 train/test 분할

- D-004와 같은 완전일치 그룹, 원래 `Label` 계층화, 목표 test 비율을 사용한다.
- 후속 분할 seed 집합은 D-004 결정 17에 고정된 값을 사용한다.
- 완전일치 그룹은 쪼개지 않으며, 정상·공격 class overlap 그룹도 전체가 한쪽에 배정된다.
- 관찰군은 train/test 어느 쪽에도 배정하지 않는다.
- 그룹 제약 때문에 생기는 seed별 실제 행 수를 기록하며 EXP-007의 정확한 행 수를 강제하지 않는다.
- 행 단위 랜덤 분할은 EXP-007에서 이미 낙관적 민감도 분석으로 수행했으므로 반복하지 않는다.

### 2.3 모델 고정

- 후보 탐색과 early stopping을 다시 수행하지 않는다.
- EXP-007 `candidate_history.json`과 `manifest.json`이 가리키는 C06 설정을 고정한다.
- 최종 반복 수와 모든 모델 난수는 D-004 결정 17을 따른다.
- 각 seed의 외부 train 전체에서 모델을 새로 학습하고 해당 seed의 test를 한 번 평가한다.
- 새 test 결과를 보고 후보, 반복 수, 피처, 전처리, 경계를 변경하지 않는다.

### 2.4 EXP-007 기준값

- 순위 비교 기준은 EXP-007 `group_seed42`의 `aurc_random_ratio`다.
- 고정 처리량 검증에는 EXP-007 `metrics.json`의 주 분석 1%·5%
  `confidence_threshold` 원값을 사용한다.
- 기준값은 config 또는 manifest에서 출처와 함께 읽으며 이 문서에 숫자를 복제하지 않는다.
- EXP-007의 `row_random_seed42`는 판정 기준으로 사용하지 않는다.

## 3. 평가 항목

### 3.1 오류 순위

각 seed의 전체 test에서 다음을 산출한다.

- 전체 오류 수
- `aurc`, `random_aurc`, `oracle_aurc`, `full_coverage_risk`
- `aurc_random_ratio`, `reference_aurc_random_ratio`, `maximum_aurc_random_ratio`
- `relative_aurc_improvement`
- test confidence를 사용한 오프라인 budget 스윕

순위 판정에는 충돌 행을 포함한 전체 test 지표만 사용한다. class overlap 제외 지표는
D-004 결정 11에 따른 진단 자료다.

### 3.2 고정 경계 처리량

EXP-007의 1%·5% 고정 경계를 각 seed의 test에 변경 없이 적용하고 다음을 산출한다.

- `n_test`, `n_abstained`, `n_accepted`, `actual_abstention_rate`
- `target_abstention_rows`, `abstention_row_delta`, `abstention_rate_delta`
- `allowed_abstention_rate_lower`, `allowed_abstention_rate_upper`
- 유보 및 수용 오류 수
- `error_capture_rate`, `error_enrichment`, `selective_risk`
- `attack_coverage`

처리량 판정에는 `actual_abstention_rate`만 사용한다. 나머지 지표는 D-004 결정 13에
따라 필수 보고하되 판정을 변경하지 않는다.

### 3.3 진단 분석

다음 결과는 판정과 분리해 보고한다.

- D-004 결정 11의 class overlap 그룹 배정 및 포함·제외 지표
- D-004 결정 15의 seed 쌍별 test 행·완전일치 그룹 Jaccard와 공통 오류 행 수
- 원래 `Label`, 관찰군, 예측 분포 및 confidence 포화 정도
- 새 test confidence로 다시 계산한 오프라인 budget 결과와 고정 경계 결과의 차이

seed별 test 집합이 서로 겹치므로 seed를 독립 표본으로 취급하거나 신뢰구간·유의성을
주장하지 않는다.

## 4. 판정 기준

### 4.1 기술적 유효성

D-004 결정 17의 입력·분할·모델 고정·결과 산술 검사를 seed마다 모두 통과해야 한다.
한 seed라도 실패하면 D-004 결정 16에 따라 EXP-008 전체가 기술적 판정 불가다.
유효한 두 seed만으로 순위 또는 처리량 종합 판정을 다시 계산하지 않는다.

### 4.2 오류 순위 판정

seed별 비교와 최소 오류 수, 허용 악화폭, 세 seed 종합 규칙은 D-004 결정 10을
그대로 적용한다.

- 각 seed는 판정 가능 여부와 기준 통과 여부를 먼저 기록한다.
- 최소 오류 수를 충족하지 않는 seed가 하나라도 있으면 전체 순위 판정은 불가다.
- 세 seed가 모두 판정 가능할 때 D-004 결정 10의 종합 규칙으로
  **순위 유지 / 순위 실패 / 순위 판정 불가** 중 하나를 결정한다.

### 4.3 고정 경계 처리량 판정

경계별 허용 범위, 한 seed 안에서 두 경계를 합치는 규칙, 세 seed 종합 규칙은
D-004 결정 12를 그대로 적용한다.

- 각 seed의 1%·5% 경계 결과를 먼저 개별 판정한다.
- D-004 결정 12의 seed 내부 규칙으로 seed별 처리량 상태를 결정한다.
- 세 seed 상태를 같은 결정의 종합 규칙으로 합쳐
  **처리량 유지 / 처리량 실패 / 처리량 판정 불가** 중 하나를 결정한다.
- 허용 범위 안이더라도 원래 목표를 초과한 행 수와 비율은 별도로 밝힌다.

### 4.4 전체 해석

하나의 `final_status`로 합치지 않고 순위와 처리량의 두 상태를 나란히 제시한다.
두 상태가 모두 유지일 때만 D-004 결정 14의 공동 유지 문장을 사용할 수 있다.
한쪽이 실패 또는 판정 불가이면 해당 항목을 그대로 명시하고 공동 유지 주장을 하지 않는다.

class overlap 제외 결과, 보조 효용 지표, seed 중복 진단은 위 판정을 바꾸지 않는다.

## 5. 실행 설계

### 5.1 설정 파일

`configs/exp/EXP-008.yaml`을 새로 만들고 기존 설정 구획을 유지한다. 실험 간 차이를
별도 Python 파일로 만들지 않는다.

| 구획 | EXP-008에서 담을 내용 | 고정 방법 |
|---|---|---|
| `experiment` | 실험 ID, 스펙 경로, 결과 경로 | 확정 스펙과 일치해야 한다. |
| `inputs` | 데이터·whitelist·정본 ZIP·EXP-007 참조 산출물 경로와 SHA256 | 경로만으로 신뢰하지 않고 해시를 함께 검사한다. |
| `analysis` | 평가할 group split seed, offline budget, 고정 경계 원천, 판정 기준 | D-004 항목 9~18을 설정으로 표현한다. |
| `training` | EXP-007 선택 후보, 고정 iteration, seed별 난수 제어 | 후보 재탐색과 early stopping을 금지한다. |
| `execution_guard` | clean worktree, test, 결과 디렉토리 비존재 조건 | 어느 하나라도 실패하면 학습 전에 중단한다. |

고정 confidence 경계는 YAML에 숫자를 다시 옮겨 적지 않는다. EXP-007 참조 산출물에서
읽고 그 파일의 SHA256과 경계 원천을 manifest에 기록한다. 이 방식으로 경계를 옮기는
과정의 전사 오류를 막는다.

### 5.2 실행 명령

구현 완료 후 사용할 표준 진입점은 기존 `scripts/run_experiment.py`를 일반화해 사용한다.
현재 코드는 아직 EXP-008을 지원하지 않는다. 폐기된 Makefile이나 EXP-008 전용 실행
파일을 만들지 않는다.

```powershell
python -m uv run --locked python scripts/run_experiment.py --config configs/exp/EXP-008.yaml --stage validate
```

`validate`는 쓰기 없는 사전 점검이다. 설정 스키마, 입력 및 EXP-007 참조 산출물의
존재와 SHA256, 고정 후보·iteration·경계의 출처, 데이터 대상 행 집합, seed별 split
구성 가능성을 확인한다. split은 메모리에서 재현해 정렬·누락·그룹 교차 여부까지
검사하지만 `results/EXP-008/`을 만들지 않는다. dirty worktree와 이미 존재하는 결과
경로도 보고하되 파일을 변경하지 않는다.

```powershell
python -m uv run --locked python scripts/run_experiment.py --config configs/exp/EXP-008.yaml --stage all
```

`all`은 같은 사전 점검을 다시 수행하고 실행 guard를 통과한 경우에만 split 생성,
고정 모델 학습, 예측, 지표 계산, 독립 재계산, 산출물 기록을 순서대로 수행한다.
`validate` 성공 결과를 캐시나 우회 근거로 사용하지 않는다.

### 5.3 구현 재사용 원칙

1. 설정 로더는 EXP-007 전용 검사를 일반화하되 기존 EXP-007 설정의 의미를 바꾸지 않는다.
2. split 생성 로직은 seed와 비교 방법을 인자로 받는 공용 함수로 만든다.
3. EXP-008은 후보 선택 함수를 호출하지 않고 EXP-007에서 고정한 후보와 iteration만 사용한다.
4. 순위 지표, tie 처리, budget 계산은 EXP-007의 평가 함수를 재사용한다.
5. seed별 차이는 설정과 인자만으로 표현하며 `train_v2.py` 같은 복사본을 만들지 않는다.

## 6. 실행 순서와 guard

### 6.1 `all` 실행 순서

| 순서 | 작업 | 통과 조건 | 실패 시 처리 |
|---:|---|---|---|
| 1 | config·스펙·참조 산출물 검증 | 경로, ID, SHA256, 고정 조건 일치 | 결과 경로 생성 전 중단 |
| 2 | 저장소 guard | clean worktree, 결과 경로 없음 | 결과 경로 생성 전 중단 |
| 3 | 테스트 | 아래 표준 명령 전체 통과 | 결과 경로 생성 전 중단 |
| 4 | 입력 및 split 검증 | D-004 항목 17의 데이터·split 조건 통과 | 기술적 무효로 중단 |
| 5 | seed별 학습·예측 | 고정 후보·iteration·난수·피처 계약 준수 | 기술적 무효로 중단 |
| 6 | 지표 독립 재계산 | 공식, tie, shuffle, oracle, 경계 적용 검사 통과 | 기술적 무효로 중단 |
| 7 | 산출물 완결성 검사 | 필수 파일과 행 수·키·SHA256 일치 | 기술적 무효로 중단 |
| 8 | manifest 확정 | 모든 필수 산출물 경로와 해시 기록 | 완료로 간주하지 않음 |

표준 테스트 명령은 다음과 같다.

```powershell
python -m uv run --locked python -m pytest
```

### 6.2 기술적 유효성 기록

`validation_checks.json`은 D-004 항목 17의 검사를 영역별로 기록한다.

| 영역 | 반드시 기록할 내용 |
|---|---|
| 입력 | 데이터·ZIP·whitelist·EXP-007 참조 산출물의 기대/실제 SHA256, 대상 행 수 |
| split | seed, train/test 행 수, 정렬 일치, 59-feature 그룹 교차 수, 잔존 label, 관찰군 혼입 수 |
| 학습 | 후보 ID, 고정 iteration, 실제 iteration, 난수 seed, 피처 수, `Protocol` 범주형 선언, calibration 미사용 |
| 예측 | 행 키 유일성, 확률·confidence 유한성, 행 수와 split 일치 |
| 평가 | AURC 3회 shuffle 차이, oracle 하한, 고정 경계 일치, 독립 재계산 차이 |
| 산출물 | 필수 파일 존재, 스키마, 행 수, 참조 무결성, SHA256 |

각 검사는 `passed`, 관측값, 기대값, 근거 파일을 함께 남긴다. 하나라도 실패하면 해당
seed만 제외하지 않고 EXP-008 전체를 기술적 무효로 처리한다.

## 7. 필수 산출물 계약

### 7.1 디렉토리 구성

```text
results/EXP-008/
  manifest.json
  validation_checks.json
  metrics.json
  splits/
    split_manifest.json
    group_seed{seed}/
      monday.csv.gz
      tuesday.csv.gz
      wednesday.csv.gz
      thursday.csv.gz
      friday.csv.gz
  predictions/
    group_seed{seed}.parquet
  aurc_curve/
    group_seed{seed}.csv.gz
  offline_budget_summary.csv
  fixed_threshold_summary.csv
  class_overlap_assignment.csv
  class_overlap_summary.csv
  seed_overlap_summary.csv
  label_summary.csv
  observation_summary.csv
  prediction_distribution_summary.csv
```

`{seed}`에는 EXP-008 평가 seed가 들어간다. 비교 기준인 EXP-007 seed의 원본 split·예측을
복제하지 않고 참조 경로와 SHA256만 manifest에 남긴다.

### 7.2 파일별 최소 내용

| 파일 | 최소 내용 | 무결성 조건 |
|---|---|---|
| `manifest.json` | 실험 ID, git commit, 실행 시각, 해석 완료 config, Python·패키지 버전, 입력·참조·산출물 경로와 SHA256 | manifest 자신은 자기 해시 대상에서 제외한다. 마지막에 기록한다. |
| `validation_checks.json` | 6.2의 검사별 상태·관측값·기대값·근거 | 모든 검사가 통과해야 완결 실행이다. |
| `metrics.json` | seed별 분류 지표, `aurc`, `oracle_aurc`, `random_aurc`, `aurc_random_ratio`, `total_errors`, offline budget 수치, 고정 경계 수치 | 수치와 기계적 사실만 기록하며 해석·최종 판정 문장은 넣지 않는다. |
| `splits/split_manifest.json` | seed별 split 파라미터, 요일별 행 수, 라벨 수, 배정 파일 SHA256 | 배정 파일과 집계값이 일치해야 한다. |
| `splits/group_seed{seed}/*.csv.gz` | `day`, `id`, `Label`, `observation_group`, `split` | `(day,id)` 유일, 원본 정렬·라벨과 일치한다. |
| `predictions/group_seed{seed}.parquet` | D-004 항목 18의 예측 필드 | test 배정과 1:1이며 확률·confidence가 유한해야 한다. |
| `aurc_curve/group_seed{seed}.csv.gz` | tie-aware coverage별 누적 수용 행·오류와 risk | 원자료 재계산 AURC와 일치해야 한다. |
| `offline_budget_summary.csv` | seed·budget별 목표/실제 유보율, 경계, `next_tie_inclusive_abstention_rate`, `accepted_errors`, `abstained_errors`, 오류 포착·농축, selective risk, 공격 coverage | predictions만으로 독립 재계산 가능해야 한다. |
| `fixed_threshold_summary.csv` | seed, `confidence_threshold_source`, 목표·허용·실제 유보율, `target_abstention_rows`, `abstention_row_delta`, `abstention_rate_delta`, 유보·수용 오류와 필수 효용 지표 | EXP-007 경계를 변형 없이 적용해야 한다. |
| `class_overlap_assignment.csv` | `feature_group_id`별 크기·라벨 구성과 seed별 train/test 배정 | 정본 충돌 그룹 집합과 일치해야 한다. |
| `class_overlap_summary.csv` | 포함/제외 두 벌의 seed별 오류·AURC·유보 진단 | 주 판정은 포함 결과만 사용한다. |
| `seed_overlap_summary.csv` | 모든 seed 쌍의 `common_test_rows`, `row_jaccard`, `common_test_feature_groups`, `feature_group_jaccard`, `common_error_rows` | D-004 항목 15의 전 조합을 한 번씩 기록한다. |
| `label_summary.csv` | seed·split·label별 행 수 | split 배정과 합계가 일치해야 한다. |
| `observation_summary.csv` | seed·split·관찰군 여부별 행 수 | test 관찰군은 0이어야 한다. |
| `prediction_distribution_summary.csv` | seed별 확률·confidence 분포, 극단 confidence 비율, 고유값 수 | predictions 집계와 일치해야 한다. |

코드 식별자는 `docs/glossary.md`를 따른다. 구현 중 새 필드가 더 필요하면 코드보다
glossary를 먼저 갱신한다.

## 8. 중단·재실행 규칙

1. `validate`는 결과 파일을 만들지 않으므로 실패 원인을 고친 뒤 같은 명령을 다시 실행할 수 있다.
2. `all`이 결과 디렉토리를 만들기 전에 guard에서 멈춘 경우에도 같은 EXP-008 ID로 재시도할 수 있다.
3. `all`이 `results/EXP-008/`을 만든 뒤 실패하면 부분 결과를 삭제·덮어쓰기하지 않는다. 실패
   위치와 로그를 보존하고, 원인을 고친 뒤 세 seed 전체를 `EXP-008-r2`로 다시 실행한다.
4. 한 seed만 재실행하거나 유효 seed만 모아 판정하지 않는다.
5. 재실행 ID는 새 config와 새 결과 경로를 사용하며 이전 실행을 참조할 때 SHA256을 기록한다.
6. 기술적 무효 실행에는 순위·처리량 판정을 부여하지 않는다.

## 9. 결과 보고 계약

실행 후 보고서는 원자료와 수치 산출물에서 별도로 작성하며 다음 질문에 답한다.

1. 세 seed 각각의 순위 판정과 집계 판정은 무엇인가.
2. 세 seed 각각의 고정 경계 처리량 판정과 집계 판정은 무엇인가.
3. 두 판정이 모두 유지일 때 공동 유지 문구를 사용할 수 있는가.
4. 최소 오류 수 조건과 class overlap 배정이 각 seed 결과에 어떤 영향을 주었는가.
5. seed 간 test 행·그룹·오류 중복이 결과 유사성을 얼마나 설명하는가.
6. 오류 포착률, 오류 농축도, selective risk, 공격 coverage의 비용·효익은 어떻게 변했는가.
7. EXP-007의 confidence 포화와 소수 오류 패턴 문제는 반복되었는가.

결론의 최대 범위는 같은 정본 데이터와 고정 프로토콜 안의 group split seed 민감도다.
독립 데이터 일반화, 운영 배포 성능, 확률 calibration, 2차 계층의 실제 성능은 주장하지 않는다.

## 10. 결과 요약

- 기술적 유효성: 실행 전 공란.
- 오류 순위 판정: 실행 전 공란.
- 고정 경계 처리량 판정: 실행 전 공란.
- 진단 결과와 관측된 이상 사항: 실행 전 공란.

수치 산출물에는 해석을 넣지 않는다. 실행 후 이 절을 고치지 않고 결과 해석을 별도 문서로
작성한다.
