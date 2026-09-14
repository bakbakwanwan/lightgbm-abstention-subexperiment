---
id: EXP-XXX
title:
status: draft          # draft | ready | running | done | discarded
depends_on: []         # 선행 실험 ID 목록
created:
---

> **이전 기록 (2026-09-13).** Cowork 프로젝트 `TEMPLATE.md`에서 저장소로 이전했다.
> D-004가 확률 보정을 범위 밖으로 두었으므로 §3 스키마에서 보정 관련 필드를 제거했고,
> 단계 번호 체계가 폐기되어 `roadmap_stage` 프론트매터를 제거했다.
> 식별자 체계는 `docs/glossary.md` A절을 따른다.

## 1. 질문

(이 실험 하나가 답하는 **단일** 질문. 두 개 이상이면 실험을 쪼갠다.)

## 2. 입력

- 데이터셋 / 버전: (`data/dataset_manifest.json`의 `file_sha256` 기재)
- 대상 행 집합: (`docs/CURRENT_DECISIONS.md`의 "대상 행 집합" 절 기준 1,929,529행에서 무엇을 쓰는가)
- 사용 split: (train / test 중 무엇을 어떻게 쓰는가. **calib split은 없다** — D-004)
- 관찰군 취급: (`attempted` / `invalid_class` 관찰군을 이 실험에서 어떻게 다루는가)
- 피처: `configs/features_whitelist.json`의 `include` (목록을 여기 옮겨 적지 않는다)
- seed:
- 설정 파일: `configs/exp/EXP-XXX.yaml`
- 선행 산출물: (이전 실험의 어떤 파일을 입력으로 쓰는가)

## 3. 산출물 스키마

`results/EXP-XXX/metrics.json`에 아래 필드를 포함한다.
필드명은 `docs/glossary.md` B절과 1:1로 대응하며, 임의로 바꾸지 않는다.
이 실험과 무관한 필드는 `null`로 남긴다.

```json
{
  "exp_id": "EXP-XXX",
  "git_commit": "",
  "seed": 42,
  "dataset": "",
  "aurc": null,
  "abstention_band": [null, null],
  "abstention_rate": null,
  "escalation_ratio": null,
  "fpr": null,
  "fnr": null,
  "notes": ""
}
```

**보정 관련 필드(`calibration`, `ece`, `adaptive_ece`, `brier_score`)는 두지 않는다.**
이 서브실험은 확률 보정을 수행하지 않는다(`docs/CURRENT_DECISIONS.md` D-004).
본 연구 단계에서 보정을 도입하면 그때 `docs/glossary.md` B-1의 용어를 B절로 옮기고
이 스키마에 필드를 추가한다.

클래스별 지표를 산출하는 경우 **`n_test`(해당 클래스의 test 표본 수)를 반드시 병기한다**(D-005).

추가 산출물(그림, 중간 테이블)은 `results/EXP-XXX/figures/`와 같은 디렉토리 하위에 둔다.

## 4. 성공 / 실패 판정 기준 ← 실행 전에 작성, 이후 수정 금지

- **성공:**
- **실패:**
- **판정 불가** (측정 자체가 무효가 되는 조건):

이 절이 비어 있으면 실행하지 않는다. 결과를 본 뒤 기준을 정하면 사후 합리화가 된다.

## 5. 결과 요약 (실행 후 작성)

- 수치:
- 관측된 이상 사항:

## 6. 다음 분기

- 성공 시:
- 실패 시:
