# CICIDS2017 데이터 준비 파이프라인 — 완료 브리핑

## 0. 이 문서의 목적

`tasks/split_protocol_proposal.md`(2단계: 그룹 기반 분할+LOAO)와
`docs/stage1_briefing.md`(1단계: 중복 검출·Destination Port 분리·상수/중복 컬럼
제거·Infinity 클리핑) 두 작업 지시서를 통합 구현한 결과를 정리한다. 아직
`EXP-ID`가 없는 단계(`experiments/`의 확정 실험 이전, `tasks/` 단계 산출물)라
`results/<EXP-ID>/` 관례를 따르지 않고 `results/cicids_prep/`에 둔다.

두 지시서는 여전히 유효한 스펙 문서다 — 이 브리핑은 "무엇을 했는가"만 담고,
"왜 이렇게 설계했는가"의 근거는 원본 두 문서에 있다.

---

## 1. 구현 범위

`docs/stage1_briefing.md` §5의 통합 실행 순서 그대로 구현했다.

| 단계 | 내용 | 코드 |
|---|---|---|
| 1 [1단계] | 로드 + `dataset_manifest.json` | `src/cicids_prep/io.py`, `manifest.py` |
| 2 [1단계] | 중복 플로우 검출·처리 | `dedup.py` |
| 3 [1단계] | Destination Port 분리·보존 | `reserved_columns.py` |
| 4 [2단계] | 그룹키 → 커트라인 → split → LOAO | `grouping.py`, `splitting.py`, `loao.py` |
| 5 [1단계] | train 기준 상수/완전동일 컬럼 제거 | `column_pruning.py` |
| 6 [1단계] | train 기준 Infinity 클리핑 | `clipping.py` |
| 7 [1단계] | 최종 학습 테이블 저장 | `pipeline.py` |

진입점: `scripts/build_dataset.py` (`--config`, `--loao-only`), config:
`configs/exp/cicids_prep.yaml`, `Makefile`(`prep-dataset`, `prep-dataset-loao`).
테스트: `tests/cicids_prep/` 30개 (합성 데이터, 실데이터 미사용), 전부 통과.

## 2. 실제 데이터 실행 결과 (2026-09-10)

입력: `data/CICIDS2017_improved_2022ver/` 요일별 CSV 5개, 총 2,099,976행 × 91열.

- **중복 (1-2/1-7)**: 완전일치 0건, 완화기준(5-tuple+timestamp) 라벨일치 제거 0건,
  라벨충돌 보존 0건. **이 데이터셋(CNS2022 정제판)엔 원본 CICIDS2017의 알려진
  중복 문제가 이미 없다** — 0건이 버그인지 의심해 원본 CSV에서 독립적으로
  재확인했고, 실제로 0건이 맞다.
- **Destination Port (1-5)**: 기본 테이블에서 제거, `reserved_for_early_features.parquet`
  (2,099,976행 × `row_uid`+`Dst Port`)에 보존.
- **분할 (2단계)**: `train` 1,110,339 / `calib` 372,299 / `test` 617,338행.
  test 비중이 높은 건 그룹 수 10 미만 레이블(예: Friday DDoS — 그룹 5개에 95,144행)이
  전량 test로 배정되기 때문이며, 의도된 동작이다(`split_summary_report.csv`의
  `below_min_group_count` 컬럼에 표시됨).
- **상수/중복 컬럼 (1-6)**: `Bwd URG Flags`(train에서 상수) 제거,
  `URG Flag Count`(train에서 `Fwd URG Flags`와 완전 동일) 제거.
- **Infinity 클리핑 (1-4/1-8)**: `Flow Bytes/s`(상한 186,000,000),
  `Flow Packets/s`(상한 6,000,000)에서 `+Infinity` 발견, train 99.9퍼센타일×3으로
  클리핑. `-Infinity`(음수/제로 Duration 케이스)는 **이 데이터셋엔 0건**.
- **검증**: `validation_log.json` 9개 항목 전부 `passed: true` (경고 레벨 1개는
  `6-3 split_skew_warning` — 그룹 수 미달로 100% test인 레이블 18개, 정상 발생).
- **`--loao-only` 재실행**: `Heartbleed`를 대상으로 테스트 — 그룹 재계산 없이
  1분(전체 실행 2분 20초 대비)만에 완료, `train`에 0건 확인.

산출물은 전부 `data/processed/cicids_prep/`에 있다(`.gitignore`로 git 추적 제외,
스크립트+config로 언제든 재생성 가능). 커밋: `dfcd871`(환경) →
`b247310`(파이프라인 코드) → `84f207c`(테스트).

## 3. 구현 중 발견해 고친 문제

- **pandas 3.0.5의 `datetime64` 기본 해상도가 마이크로초(`us`)다.** 그룹 버킷
  계산 코드가 나노초를 가정해(`astype("int64") // 10**9`) 버킷이 1000배 틀렸다
  (5분 버킷이 실제로는 약 83시간 버킷이 됨). `astype("datetime64[s]")`를 경유하도록
  고쳤다(`grouping.py`). 유닛 테스트로 회귀를 막아뒀다.
- **`id` 컬럼이 요일 파일마다 1부터 다시 시작한다** (전역 유일 아님). 요일 병합 후
  `row_uid = f"{day}_{id}"`를 새로 만들어 모든 행 단위 식별(calib/train 교집합
  검증, Destination Port 재조인 키)에 이것만 쓰도록 했다.

## 4. 아직 안 된 것 / 사용자·Cowork 판단이 필요한 것

- **`make`가 이 Windows 환경에 미설치 상태다** (choco install이 권한 문제로 실패).
  `Makefile`은 작성해뒀지만 검증하지 못했다 — `uv run python
  scripts/build_dataset.py --config configs/exp/cicids_prep.yaml`로 대신 실행했다.
- **`docs/environment.md`의 "미정 사항"이 이번에 일부 확정됐다** (uv 설치됨/make
  미설치, Python 3.14 + pandas 3.0.5 조합에서 실제 파이프라인 정상 동작 확인).
  `docs/`는 제가 직접 쓰지 않는 영역이라 반영은 보고로 남긴다.
- **`docs/stage1_briefing.md`는 커밋하지 않았다** — Cowork가 만든 것으로 추정되는
  `docs/` 파일이라 커밋 여부는 사용자·Cowork 판단.
- Flow ID/Src IP/Dst IP/Timestamp는 이번 파이프라인에서도 제거하지 않았다
  (`split_protocol_proposal.md` §7 그대로, stage1_briefing이 명시적으로 확정한
  누수 컬럼은 Destination Port뿐).
- `docs/glossary.md`가 아직 없어 컬럼/필드명을 이 문서와 대조 검증하지 못했다.

## 5. 다음 단계와의 연결

`data/processed/cicids_prep/final_training_table.parquet`
(+ `group_index.parquet`, `reserved_for_early_features.parquet`)가 3단계(피처
설계)·4단계(베이스 모델 학습)의 유일한 입력이다. `split`/`original_split`,
`label_conflict_flag`, `invalid_negative_duration_flag` 컬럼이 포함돼 있다.
Destination Port 재도입 여부는 3단계 "실시간성 정의" 확정 이후 결정 사항으로
남아 있다(`reserved_for_early_features.parquet`에서 `row_uid`로 재조인 가능).
