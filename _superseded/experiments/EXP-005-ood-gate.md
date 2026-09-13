---
id: EXP-005
title: OOD 보조 게이트의 상보적 기여 검증
status: blocked
roadmap_stage: 8
depends_on: [EXP-003]
created: 2026-09-10
---

## 1. 질문

OOD 스코어를 보조 게이트로 추가하면, 신뢰도 밴드가 놓치는 배제 공격군을
추가로 포착할 수 있는가. 두 경로는 상보적인가 중복인가.

## 2. 실행 조건 (중요)

**이 실험은 EXP-003이 실패 판정(배제 공격군이 저확률 구간에 쏠림)일 때만 실행한다.**
EXP-003이 성공하면 신뢰도 단독 게이트로 충분하므로 이 실험은 `discarded`로 전환하거나
부록 실험으로 강등한다. 그래서 초기 상태가 `blocked`이다.

조건 없이 미리 실행하면 로드맵 A-5의 범위 고정을 깨고 초록에 담기지 않는 분량이 된다.

## 3. 입력

- 선행 산출물: `results/EXP-003/` 전체, `results/EXP-002/predictions.parquet`
- 배제 공격군: EXP-003에서 확정된 목록과 **동일하게 고정**. 여기서 바꾸면 비교가 불가능해진다
- seed: EXP-002·003과 동일한 5개
- 설정 파일: `configs/exp/EXP-005.yaml`

### OOD 스코어 산출 방식

1. **1순위: LightGBM 리프 인덱스 재활용.** 학습된 모델의 리프 인덱스를 표현 벡터로 쓰고,
   `train`의 정상 트래픽 리프 분포를 기준으로 마할라노비스 거리 또는 kNN 거리를 계산한다.
   별도 모델을 학습하지 않으므로 추가 비용과 추가 실패 지점이 없다.
2. 대안(1순위가 수치적으로 불안정할 때): 정상 전용 Isolation Forest, 오토인코더 재구성 오차.
   대안을 쓰면 그 사유를 `notes`에 기록한다.

PCA·오토인코더 계열은 1차 모델의 **입력 피처**로는 여전히 금지다(로드맵 E절).
여기서는 게이트 스코어 산출에만 쓰며, 모델 입력을 바꾸지 않는다.

### 게이트 구성

게이트 조건을 논리합으로 확장한다: `확률이 밴드 안` OR `OOD 스코어가 임계 초과`.
OOD 임계값도 절대값을 고정하지 않고 **에스컬레이션 예산 기반으로 역산**한다(EXP-004와 동일 원칙).
전체 검증 예산을 두 경로에 어떻게 배분할지는 스윕 대상이다.

## 4. 산출물 스키마

`results/EXP-005/metrics.json`

```json
{
  "exp_id": "EXP-005",
  "git_commit": "",
  "seeds": [],
  "ood_method": "",
  "held_out_attacks": [],
  "budget_allocation_sweep": [
    {
      "total_escalation_ratio": null,
      "band_share": null,
      "ood_share": null,
      "heldout_capture_rate": null,
      "fpr": null,
      "fnr": null
    }
  ],
  "overlap": {
    "captured_by_band_only": null,
    "captured_by_ood_only": null,
    "captured_by_both": null,
    "captured_by_neither": null
  },
  "notes": ""
}
```

- `heldout_capture_rate`: 배제 공격군 샘플 중 게이트에 포착되어 심층 검증으로 넘어간 비율.
  **이 실험의 핵심 측정치**다.
- `overlap`: 두 경로의 중복 검출 분해. 겹침이 크면 OOD 경로에 예산을 쓸 이유가 없다.

추가 산출물: `figures/gate_overlap_venn.png`, `figures/budget_allocation_vs_capture.png`.

## 5. 성공 / 실패 판정 기준 ← 실행 전에 작성, 이후 수정 금지

- **성공:** 동일 총 에스컬레이션 예산에서 논리합 게이트의 `heldout_capture_rate`가
  밴드 단독 대비 절대값 15%p 이상 높고, `captured_by_ood_only`가 전체 포착 건수의 20% 이상인 경우.
  → OOD 경로가 상보적이다. 중심축을 "신뢰도 + OOD 스코어 기반 선택적 검증"으로 확정하고
  `ADR-001`을 갱신한다.

- **실패 (중복):** `captured_by_ood_only`가 전체 포착 건수의 5% 미만인 경우.
  → 두 경로가 같은 샘플을 잡는다. OOD 게이트에 예산을 배분할 근거가 없다.
  이 경우 **"신뢰도 단독 게이트의 한계와 OOD로도 해소되지 않음"을 부정적 결과로 보고**한다.
  로드맵 M절이 예상한 대응 경로이며, 이것 자체가 보고할 가치가 있는 결과다.

- **실패 (비용 초과):** `heldout_capture_rate`가 개선되더라도 동일 예산에서 `fpr`이
  밴드 단독 대비 악화되는 경우. 오탐 저감이 목표이므로 목표에 역행한다.

- **판정 불가 (측정 자체가 무효):**
  - OOD 스코어 계산에 `calib` 또는 `test` 분포가 사용된 경우. 누수이므로 전체 폐기.
  - 배제 공격군 목록이 EXP-003과 다른 경우. 비교 불가.
  - 마할라노비스 공분산 행렬이 특이(singular)해 수치적으로 불안정한 경우.
    대안 방식으로 교체하고 사유를 기록한 뒤 재실행한다.

## 6. 결과 요약 (실행 후 작성)

## 7. 다음 분기

- 성공 → EXP-004를 논리합 게이트 전제로 재실행(`EXP-004-r2`)한 뒤 EXP-006으로 진행.
- 실패 → 부정적 결과를 그대로 논지에 반영하고 EXP-006으로 진행. 기준을 바꿔 재판정하지 않는다.
