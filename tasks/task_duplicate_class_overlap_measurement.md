# 작업 지시 — 중복 행 및 class overlap 측정

> **대상 데이터셋:** `CICIDS2017_CNS2022_reprocessed`
> (로컬 경로: `data/CICIDS2017_improved/` — 폴더명은 미정정 상태, 3-1 참조)
> **작성일:** 2026-09-13
> **관련 결정:** D-001(Attempted 유보), D-002(DoS Hulk 관찰군), D-003(피처 구성 59/32)
> **관련 미결 항목:** `dataset_audit_2026-09-11.md` §5 "class overlap이 우리 데이터에서 몇 건인지 측정"

---

## 0. 이 작업의 목적

이 하위실험의 질문은 "**유보 구간이 존재하는가**"이다.

그런데 59개 feature 값이 완전히 동일한데 라벨이 갈리는 행이 존재하면, 그 지점에서는
어떤 모델도 확률 0.5 근처를 낼 수밖에 없고 무엇을 답하든 일정 비율로 틀린다.
즉 **유보 구간처럼 보이는 영역이 데이터셋 결함만으로도 생성된다.**

따라서 실험 실행 **전에** 그 규모를 알아야 한다.
실행 후에 측정하면 "결과를 보고 나서 해명을 만든" 형태가 된다.

CNS2022 원문 §V가 같은 현상을 보고했다:

> "It is more unusual to see post-processed samples from different traffic scenarios
> presenting identical values for every field in the extracted flows."
>
> "when samples with class overlap surface in the testing/validation partitions of the
> dataset, this makes theoretical 100% accuracy impossible"
>
> "It is possible to avoid the latter problem by removing duplicate rows before commencing
> the ML pipeline, but it does not address the underlying issue of a feature
> representation problem."

---

## 1. 선행 조건 — 무결성 검증 (건너뛰지 말 것)

### 1-1. 배경

구 PC에서 SHA256 5개 일치를 확인했다고 기록되어 있으나,
**감사 문서에는 "일치"라는 판정만 있고 해시 값 자체가 없다.**
그리고 `dataset_manifest.json`은 gitignore 대상이라 저장소에 없다.
즉 현재 PC에는 **대조할 기준값이 존재하지 않는다.**

### 1-2. 할 일

1. 5개 CSV의 행 수를 세어 아래 기록과 대조한다. **헤더 제외 데이터 행 수** 기준.

   | 파일 | 기대 행 수 |
   |---|---|
   | monday.csv | 371,624 |
   | tuesday.csv | 322,078 |
   | wednesday.csv | 496,641 |
   | thursday.csv | 362,076 |
   | friday.csv | 547,557 |
   | **합계** | **2,099,976** |

   하나라도 다르면 **즉시 중단하고 보고**한다. 다른 데이터다.

2. 5개 CSV의 SHA256을 계산해 `data/dataset_manifest.json`을 **새로 생성**한다.
   필드: `file_sha256`(파일명→해시), `row_counts`, `manifest_created_at`, `source_zip_sha256`.
   `original_download_date` 필드는 **만들지 않는다** (복원 불가능한 정보를 임의로 채우지 않는다).

3. 계산된 해시 5개를 **보고서 본문에도 값 그대로 적는다.**
   manifest 파일이 사라져도 문서만으로 재검증이 가능해야 한다.
   (이번 문제의 재발 방지 조치다.)

4. 컬럼 수가 91인지, 컬럼명 집합이 5개 파일에서 동일한지 확인한다.

---

## 2. 대상 행 집합 정의

### 2-1. 관찰군 제외

D-001과 D-002에 따라 아래 두 군은 학습·보정·평가 지표 산출 대상이 아니다.
이번 측정에서도 **제외한 집합**을 기준으로 한다.

| 관찰군 | 식별 조건 | 기대 행 수 |
|---|---|---|
| Attempted 유보군 | `Label`이 `- Attempted`로 끝나는 모든 행 | 11,979 |
| DoS Hulk 무효 클래스군 | `Label == "DoS Hulk"` | 158,468 |

```
2,099,976 − 11,979 − 158,468 = 1,929,529
```

**이 1,929,529를 반드시 코드로 확인할 것.** 숫자가 다르면 중단하고 보고한다.

주의: 두 관찰군은 **겹치지 않는다.** `DoS Hulk - Attempted`는 Attempted군에,
`DoS Hulk`는 Hulk군에 들어간다. 이중 카운트가 없는지 확인할 것.

### 2-2. 이진 라벨 정의

- `Label == "BENIGN"` → 0 (정상), 기대 1,582,566행
- 그 외 전부 → 1 (공격), 기대 346,963행

---

## 3. 피처 집합

`features_whitelist.json`의 **include 59개 컬럼만** 사용한다.

제외된 것 중 특히 주의: `Flow ID`, `Src IP`, `Dst IP`, `Src Port`, `Dst Port`,
`Protocol`, `Timestamp`, `id`, `Label`, `Attempted Category`는 **비교 키에 넣지 않는다.**
모델이 보지 않는 컬럼으로 중복을 판정하면 이 측정의 의미가 없어진다.

### 3-1. 경로 정정 사항 (별건, 이번 작업에서 변경하지 말 것)

문서상 데이터셋 명칭을 `CICIDS2017_CNS2022_reprocessed`로 통일하기로 했으나,
로컬 폴더명 `data/CICIDS2017_improved/`와 관련 config 경로는 **이번 작업에서 건드리지 않는다.**
경로 변경은 별도 커밋으로 분리한다. (한 번에 두 가지를 바꾸지 않는다.)

---

## 4. 측정 절차

### 4-1. 중복 판정 규칙

두 행이 **59개 컬럼의 값이 전부 동일**하면 같은 그룹으로 본다.

**금지 사항:**

- 부동소수 값을 반올림하거나 문자열로 포맷해서 비교하지 말 것.
  없던 중복이 생긴다. CSV에서 읽은 값을 그대로 쓴다.
- NaN이 있으면 `NaN != NaN` 때문에 groupby가 행을 누락시킬 수 있다.
  (참고: feature inventory 기준 전 컬럼 NaN 0건이지만, 코드는 방어적으로 작성한다.)
- `Flow Bytes/s`, `Flow Packets/s`에 `+Infinity` 10건이 있다. 별도로 취급하지 말고
  그대로 비교 대상에 포함한다. 다만 해당 행이 중복 그룹에 들어가면 보고서에 별도 표기한다.

**구현 권고:** 59개 컬럼을 그대로 groupby 키로 쓰면 메모리가 크다.
행별로 59개 값을 바이트로 직렬화해 해시(예: `pd.util.hash_pandas_object`, 또는
`numpy` 배열의 `tobytes()` → `hashlib.blake2b`)한 뒤 그 해시로 그룹핑한다.
**해시 충돌 검증:** 그룹 크기 > 1인 그룹에 대해서만 59개 원본 값을 실제로 비교해
동일함을 확인한다. 해시만 믿고 넘어가지 않는다.

### 4-2. 산출 항목

1. 중복 그룹 수 (그룹 크기 ≥ 2)
2. 중복에 속한 총 행 수, 그리고 전체 1,929,529 대비 비율
3. 그룹 크기 분포 (2, 3, 4, 5~10, 11~100, 100 초과 구간별 그룹 수)
4. **라벨 일치 그룹** 수 / 그에 속한 행 수 (그룹 내 이진 라벨이 전부 같음)
5. **라벨 충돌 그룹** 수 / 그에 속한 행 수 (그룹 내 이진 라벨이 갈림)
6. 라벨 충돌 그룹에 속한 행들의 **원래 `Label` 값 분포** (27종 기준, 내림차순)
7. 충돌 그룹 중 크기 상위 20개의 표본 — 각 그룹의 `row_uid`(또는 day+id), `Label`,
   그리고 59개 값 중 주요 몇 개
8. 충돌 그룹에 속한 행들이 어느 요일 파일에서 왔는지 분포
   (같은 파일 내부인지, 파일을 가로지르는지 — 라벨링 로직 결함의 성격을 가른다)

### 4-3. 참고 측정 (선택, 여유 있으면)

같은 절차를 **관찰군을 제외하지 않은 2,099,976행 전체**에 대해서도 한 번 돌려
숫자를 함께 보고한다. 관찰군 제외가 이 현상을 얼마나 줄이는지 알 수 있다.

---

## 5. 산출물

| 파일 | 내용 |
|---|---|
| `data/dataset_manifest.json` | 1-2에서 새로 생성 |
| `reports/class_overlap/summary.json` | 4-2의 1~5 집계값 |
| `reports/class_overlap/conflict_label_distribution.csv` | 4-2의 6 |
| `reports/class_overlap/conflict_groups_sample.csv` | 4-2의 7 |
| `reports/class_overlap/group_size_distribution.csv` | 4-2의 3 |
| `reports/class_overlap/report.md` | 사람이 읽는 보고서. SHA256 값 5개를 본문에 포함 |

측정 스크립트는 `scripts/investigation/class_overlap/` 아래에 둔다.

---

## 6. 하지 말 것

1. **중복 행을 삭제하지 말 것.** 이번은 측정만이다. 처리 정책은 측정값을 보고 결정한다.
2. **`data/` 아래 CSV 원본을 수정하지 말 것.**
3. 폴더명·config 경로 변경 (3-1 참조)
4. 관찰군을 학습·평가에 섞지 말 것
5. 결과가 "0건"으로 나오면 **정의가 의도대로 구현됐는지 먼저 의심할 것.**
   과거에 같은 항목을 `5-tuple + Timestamp` 일치로 판정해 0건이 나온 적이 있는데,
   `Timestamp` 고유값이 2,077,011개라 조건이 사실상 통과 불가능했다.
   0건이면 **인위적으로 동일한 행 2개를 넣어 검출되는지 확인**하고 보고한다.

---

## 7. 보고 형식

측정이 끝나면 다음을 요약해 보고한다.

1. 무결성 검증 결과 (행 수 일치 여부, SHA256 5개 값)
2. 4-2의 1~6 수치
3. 5번 항목(라벨 충돌)이 전체의 몇 %인지
4. 그 비율이 유보 구간 해석에 어떤 영향을 줄 수 있는지에 대한 소견 —
   단, **결론을 내리지 말고 수치와 관찰만 보고**한다. 해석은 별도 논의에서 한다.
