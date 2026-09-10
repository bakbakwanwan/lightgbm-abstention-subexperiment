---
id: EXP-002
title: 베이스 모델 학습과 확률 보정 기법 비교
status: draft
roadmap_stage: 4, 5
depends_on: [EXP-001]
created: 2026-09-10
---

## 1. 질문

보정 전후로 확률 품질이 어떻게 변하며, 어떤 보정법을 채택할 것인가.
그리고 오분류 샘플은 어느 신뢰도 구간에 분포하는가.

이 두 질문을 한 실험에 묶은 이유: 보정법 선택은 보정 후 지표로만 판정되므로 분리하면
동일 학습을 두 번 반복해야 한다. 학습과 보정은 실행상 하나의 파이프라인이다.

## 2. 입력

- 데이터셋: EXP-001에서 확정된 피처 집합
- 사용 split: `train`으로 학습, `calib`으로 보정기 적합, `test`로 평가.
  **calib은 학습에 절대 사용하지 않는다** (design-constraints A-2)
- seed: 42, 43, 44, 45, 46 (5개 반복)
- 설정 파일: `configs/exp/EXP-002.yaml`
- 선행 산출물: `results/EXP-001/metrics.json` (피처 집합 확정 근거)

### 학습 설정

- `objective: binary`, 클래스 가중 없음.
  불균형 처리(`is_unbalance`, `scale_pos_weight`)는 확률 보정과 충돌하므로 쓰지 않는다(로드맵 F절).
  불균형은 임계값·유보 밴드 설계로 흡수한다.
- `learning_rate: 0.05`, `num_leaves`는 작게 시작, `min_data_in_leaf`는 충분히 크게
  (희소 공격군 과적합으로 인한 신뢰도 극단화 방지), `feature_fraction`·`bagging_fraction` 0.8 내외.
- `n_estimators`는 조기종료. 조기종료 지표는 **PR-AUC와 로그손실 병행**. AUC 단독 사용 금지.

### 보정 조건

`none` / `platt`(시그모이드) / `isotonic` / `beta` 4종을 동일 학습 모델에 적용해 비교한다.

## 3. 산출물 스키마

`results/EXP-002/metrics.json`

```json
{
  "exp_id": "EXP-002",
  "git_commit": "",
  "seeds": [42, 43, 44, 45, 46],
  "dataset": "",
  "per_calibration": {
    "none":     {"ece": null, "adaptive_ece": null, "brier_score": null, "extreme_prob_ratio": null},
    "platt":    {"ece": null, "adaptive_ece": null, "brier_score": null, "extreme_prob_ratio": null},
    "isotonic": {"ece": null, "adaptive_ece": null, "brier_score": null, "extreme_prob_ratio": null},
    "beta":     {"ece": null, "adaptive_ece": null, "brier_score": null, "extreme_prob_ratio": null}
  },
  "seed_variance": {},
  "misclassification_by_confidence_bin": [],
  "selected_calibration": null,
  "notes": ""
}
```

- 모든 지표는 시드 5개의 평균과 표준편차를 함께 기록한다. 단일 시드 수치만 남기지 않는다.
- `misclassification_by_confidence_bin`: 보정 후 확률을 10구간으로 나눠 각 구간의
  오분류 건수와 비율. **로드맵 A-3의 첫 번째 주장(높은 집계 성능이 플로우 단위 신뢰도를 의미하지 않음)의 직접 근거**다.
- `extreme_prob_ratio`: 확률이 0.01 미만 또는 0.99 초과인 test 샘플 비율. EXP-001과 동일 정의.

추가 산출물: `figures/reliability_diagram_{method}.png`, `figures/prob_cdf_all_methods.png`,
그리고 전체 test 샘플의 보정 후 확률을 담은 `predictions.parquet`
(`row_uid`, `prob_calibrated`, `label`, `attack_label`, `split`).
이 파일은 EXP-003·004가 재학습 없이 오프라인 분석을 하기 위한 필수 산출물이다(로드맵 I절, L절).

## 4. 성공 / 실패 판정 기준 ← 실행 전에 작성, 이후 수정 금지

- **성공:** 4개 보정 조건 중 하나가 `brier_score`와 `adaptive_ece` **양쪽에서** 시드 5개 전부
  `none` 대비 개선되고, 시드 간 표준편차가 평균값의 20% 이내인 경우.
  → 해당 기법을 `selected_calibration`으로 채택하고 EXP-003 이후 전 실험에 고정 적용한다.

- **성공 (조건부):** 두 지표에서 서로 다른 기법이 우세한 경우.
  → `brier_score`를 우선한다. 유보 밴드 설계는 확률값의 순위가 아니라 절대 수준에 의존하기 때문이다.
  선택 근거를 `notes`에 남긴다.

- **실패:** 채택된 보정법 적용 후에도 `extreme_prob_ratio`가 0.90을 초과하는 경우.
  → 유보 밴드가 사실상 비어 신뢰도 단독 게이트가 성립하지 않는다.
  **EXP-003을 그대로 진행하지 말고** 로드맵 M절 대응을 먼저 검토한다:
  (a) 시간 기반 분할로 난이도 상향, (b) 부정적 결과 자체를 논지로 삼고 EXP-005(OOD)로 조기 전환.

- **판정 불가 (측정 자체가 무효):**
  - `calib` 인덱스가 `train`과 1건이라도 겹치는 경우. 보정 누수이므로 전체 결과 폐기.
  - `isotonic` 출력의 고유값 개수가 20 미만인 경우. 계단이 지나치게 거칠어 밴드 설계와 상성이 맞지 않으므로
    해당 기법만 비교에서 제외하고 나머지로 판정한다(전체 폐기 아님).
  - 시드 간 `extreme_prob_ratio` 표준편차가 0.15를 초과하는 경우. 시드를 3개 추가해 재실행한다.

## 5. 결과 요약 (실행 후 작성)

## 6. 다음 분기

- 성공 → EXP-003. 이때 `selected_calibration`과 `predictions.parquet`이 입력이 된다.
- 실패 → 로드맵 M절 대응 검토 후 재설계. EXP-003 착수 금지.
