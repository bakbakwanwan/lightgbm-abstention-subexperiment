---
id: EXP-001
title: 누수 후보 피처 기여도 측정 및 Destination Port 재도입 판단
status: draft
roadmap_stage: 3
depends_on: []
created: 2026-09-10
---

## 1. 질문

Destination Port를 학습 테이블에 재도입해도 되는가.
즉, 이 피처가 라벨 대리 변수로 작동해 예측 확률을 인위적으로 극단화시키는가.

### 범위 한정 근거

누수 후보 5개 중 `Flow ID` / `Src IP` / `Dst IP` / `Timestamp`는 정책 1-12로 **무조건 제거가 이미 확정**되었고
3단계 논의 대상이 아니다. 열려 있는 결정은 Destination Port 하나뿐이며(정책 1-5),
그 원본값은 `reserved_for_early_features.parquet`에 보존되어 있다.

## 2. 입력

- 데이터셋: CNS2022 정제판 CICIDS2017. `dataset_manifest.json`의 `repo_commit_hash` 기재
- 사용 split: `train`으로 학습, `test`로 평가. `calib`은 이 실험에서 **사용하지 않는다**
- seed: 42 단일 시드 (다중 시드는 EXP-002 범위)
- 설정 파일: `configs/exp/EXP-001.yaml` (`calibration.method: none`)
- 선행 산출물: 1·2단계 최종 학습 테이블(parquet), `reserved_for_early_features.parquet`

### 비교 조건

| 조건 | 피처 집합 |
|---|---|
| A (기준) | 최종 학습 테이블 그대로 (Dst Port 없음) |
| B | A + `row_uid`로 재조인한 `Dst Port` |

두 조건은 동일 seed·동일 하이퍼파라미터로 학습한다. 하이퍼파라미터는 로드맵 F절 초기값을 쓰되,
이 실험의 목적이 성능 최적화가 아니므로 튜닝하지 않는다.

## 3. 산출물 스키마

`results/EXP-001/metrics.json`에 조건 A·B 각각에 대해 기록한다.

```json
{
  "exp_id": "EXP-001",
  "git_commit": "",
  "seed": 42,
  "dataset": "",
  "calibration": "none",
  "conditions": {
    "A_without_dst_port": {
      "pr_auc": null,
      "logloss": null,
      "extreme_prob_ratio": null,
      "top10_feature_attribution": []
    },
    "B_with_dst_port": {
      "pr_auc": null,
      "logloss": null,
      "extreme_prob_ratio": null,
      "dst_port_attribution_rank": null,
      "dst_port_attribution_share": null,
      "top10_feature_attribution": []
    }
  },
  "notes": ""
}
```

- `extreme_prob_ratio`: 예측 확률이 0.01 미만 또는 0.99 초과인 test 샘플의 비율.
  보정 전 원시 확률 기준이며, 이 실험의 **핵심 측정치**다.
- `top10_feature_attribution`: TreeSHAP 전역 기여도(평균 절대값) 상위 10개.
  배경 데이터셋을 지정한 interventional 방식을 쓰고 설정을 `notes`에 기록한다.

추가 산출물: `figures/prob_histogram_A.png`, `figures/prob_histogram_B.png` (동일 축으로 그린다).

## 4. 성공 / 실패 판정 기준 ← 실행 전에 작성, 이후 수정 금지

이 실험은 "모델이 잘 나오는가"가 아니라 **재도입 여부를 판정할 근거를 산출하는가**로 평가한다.

- **성공 (Dst Port 제외 확정):** 조건 B에서 `dst_port_attribution_rank`가 상위 5위 이내이고,
  동시에 `extreme_prob_ratio`가 조건 A 대비 절대값 5%p 이상 증가한 경우.
  → Dst Port는 최종 학습 테이블에 재도입하지 않는다. 정책 1-5를 "제외 확정"으로 종결.

- **성공 (Dst Port 재도입 허용):** 조건 B의 `dst_port_attribution_rank`가 10위 밖이고
  `extreme_prob_ratio` 증가가 1%p 미만인 경우.
  → 3단계 실시간성 정의에서 조기 피처로 정당화되면 재도입 가능. 단 재도입 자체가 자동 확정되는 것은 아니며,
  실시간성 정의(로드맵 E절)를 별도로 통과해야 한다.

- **실패 (판정 보류):** 위 두 구간 어디에도 해당하지 않는 중간 결과.
  → 단일 시드로는 판정 불가. seed 3개로 재실행(`EXP-001-r2`)하고 시드 간 분산을 함께 보고한다.

- **판정 불가 (측정 자체가 무효):**
  - 조건 A의 `extreme_prob_ratio`가 이미 0.95를 넘는 경우.
    Dst Port와 무관하게 확률이 포화된 것이므로 이 실험으로는 기여를 분리할 수 없다.
    로드맵 M절의 가장 현실적 리스크가 현실화된 것이며, 즉시 보고 후 EXP-002 설계를 재검토한다.
  - `row_uid` 재조인에서 매칭 실패 행이 1건이라도 발생한 경우.

### 해석 시 주의

`below_min_group_count`로 전량 `test`에 배정된 레이블이 18개 있다(로드맵 D-8). DDoS가 대표적이다.
따라서 test 성능 수치는 미학습 공격군이 섞인 값이며, **일반 탐지 성능으로 인용하지 않는다.**
이 실험에서 test는 확률 분포 관측용으로만 쓴다.

## 5. 결과 요약 (실행 후 작성)

## 6. 다음 분기

- 어느 쪽으로 판정되든 EXP-002로 진행한다. 이 실험은 EXP-002의 피처 집합을 확정할 뿐이다.
- 판정 불가 조건이 걸리면 EXP-002 착수 전에 로드맵 M절 대응(시간 기반 분할로 난이도 상향)을 먼저 검토한다.
