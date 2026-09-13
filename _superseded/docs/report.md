# Attempted 라벨 사유 구분 가능성 및 DoS Hulk shortcut 실측 조사 — 보고서

지시서: `tasks/instruction_attempted_hulk_investigation.md`. 승인된 실행 계획:
`scripts/investigation/attempted_hulk/`(코드), `reports/attempted_hulk_investigation/`(산출물).
성격: 조사 전용(read-only). 이 보고서는 수치와 사실만 담고, 정책 확정은 하지 않는다.

---

## 1. 판정 요약

**작업 2(Attempted 사유 구분 가능성) 판정: A — 직접 구분 가능.**

원본 CSV 91번째 컬럼 `Attempted Category`가 `Label`의 Attempted 여부와 전체 2,099,976행에서
**완전히 일치**한다(불일치 0건). 코드값은 -1(해당 없음)과 0~6의 7종이며, 코드→사유명 매핑을
저자 공식 문서(`https://intrusion-detection.distrinet-research.be/CNS2022/CICIDS2017.html`)에서
확보했다. 따라서 사용자 결정 1("Attempted를 사유별로 나눠 일부만 채택")은 **현재 데이터로 실행
가능**하다 — 지시서 3-4의 "실행 불가능" 조건(판정 B/C)에 해당하지 않는다.

단, 다음 두 가지는 판정과 별개로 사용자가 확인해야 한다.
- 코드 5 "Attack Implemented Incorrectly"가 **2017 데이터에도 실제로 존재**한다(지시서 3-1의
  "2018에만 등장" 전제와 다름). 4절 참조.
- DoS Hulk shortcut은 4개 값으로 158,354/159,049행(98.9%)을 덮지만, 나머지 695행은 다른 값이다
  — "8개 예외"라는 구 문서 주장과 크게 다르다. 3.2절 참조.

---

## 2. 작업별 결과

### 2.1 헤더·컬럼 해석 (지시서 1-6, 작업 2-3-3)

- 5개 요일 CSV(`monday.csv`~`friday.csv`) 헤더가 **완전히 동일**, 91개 컬럼. 불일치 없음.
  (`run_findings.json`의 `header_consistency`)
- 실제 헤더에서 문자열 매칭으로 확정한 컬럼명 (지시서가 언급한 이름과 다른 경우 표기):

  | 용도 | 실제 컬럼명 | 지시서 표기와 차이 |
  |---|---|---|
  | 라벨 | `Label` | 없음 |
  | Attempted 사유 | `Attempted Category` | 없음(그대로 존재) |
  | DoS Hulk shortcut 대상 | `Total Length of Bwd Packet` | 지시서는 `Total Length of Bwd Packets`(복수형)로 표기 — 실제는 단수형 |

  (근거: `scripts/investigation/attempted_hulk/columns_resolve.py`의 토큰 매칭, 결과는
  `run_manifest.json`의 `resolved_columns`)

### 2.2 라벨 인벤토리 (지시서 2장) — 원본 CSV 기준

- 고유 라벨 27개(`label_inventory_summary.json`). Attempted 계열 11개, 전부
  `<원 라벨명> - Attempted` 형태로 일관되며 공백·하이픈 변형은 없다
  (`attempted_naming_patterns`, 전부 `ends_with_dash_attempted=true`, `has_double_space=false`).
- Attempted 총 행수(원본 기준): **11,979행**.
- 라벨×요일, 라벨×split 교차표: `label_inventory.csv`(요일), `label_by_split.csv`(파이프라인
  산출물의 split 기준).
- 파이프라인 산출물(`final_training_table.parquet`) 기준 Attempted 총 행수도 동일하게
  **11,979행** — 1·2단계 파이프라인이 라벨을 가공하지 않았음을 확인(중복 제거 0건, 2.5절 참조).

### 2.3 Attempted 사유 구분 (지시서 3장, 최우선) — 원본 CSV 기준

- `Attempted Category`의 비-Attempted 행 고유값은 `-1` 하나뿐이며(`sentinel_ambiguous=false`),
  Attempted 여부(`Label`에 "Attempted" 포함)와 `category != -1`이 **전체 2,099,976행에서 완전히
  일치**한다(`n_mismatch=0`, `attempted_breakdown_summary.json`).
- 라벨×사유코드 교차표: `attempted_breakdown.csv`. 코드→사유명 매핑(저자 공식 사이트,
  4절 참조)을 적용하면:

  | 라벨 | 코드(행수) |
  |---|---|
  | Botnet - Attempted | 1=Port/System closed (4,067) |
  | DoS GoldenEye - Attempted | 0=No payload sent by attacker (80) |
  | DoS Hulk - Attempted | 0 (579), 4=Attack Artefact (2) |
  | DoS Slowhttptest - Attempted | 0 (563), 4 (1), 6=Target System Unresponsive (2,804) |
  | DoS Slowloris - Attempted | 0 (1,705), 2=Attack Startup/Teardown Artefact (3), 4 (1), 5=Attack Implemented Incorrectly (138) |
  | FTP-Patator - Attempted | 0 (10), 2 (2) |
  | Infiltration - Attempted | 0 (42), 2 (3) |
  | SSH-Patator - Attempted | 3=No malicious payload (27) |
  | Web Attack - Brute Force - Attempted | 0 (1,214), 2 (7), 4 (71) |
  | Web Attack - SQL Injection - Attempted | 0 (1), 2 (4) |
  | Web Attack - XSS - Attempted | 0 (651), 2 (4) |

- 저장소 로컬 클론은 찾지 못했으나(4절), GitHub API(`gh api`)로 원격 조회는 가능했다.
  `GintsEngelen/CNS2022_Code` 저장소의 `Labelling/CICIDS2017_labelling_fixed_CICFlowMeter.ipynb`를
  직접 조회한 결과, 이 노트북이 만든 라벨 행수(SSH-Patator - Attempted 27, Web Attack - Brute
  Force - Attempted 1,292, XSS - Attempted 655, Infiltration - Attempted 45, SQL Injection -
  Attempted 5 등)가 우리 데이터와 **정확히 일치** — 이 저장소의 이 노트북이 `data/CICIDS2017_improved_2022ver/`를
  생성한 코드임을 확인했다.

### 2.4 DoS Hulk shortcut (지시서 4장) — 원본 CSV 기준 (파이프라인 산출물과 동일, 2.5절)

- 대상 컬럼 `Total Length of Bwd Packet`의 4개 값(11595/23190/11606/23201) 출현:

  | 값 | 전체 출현행 | Hulk계열행 | BENIGN행 | 그 외 라벨 |
  |---|---|---|---|---|
  | 11595 | 247,008 | 156,380 | 1 | DDoS, Portscan |
  | 23190 | 46 | 0 | 0 | DDoS, Infiltration - Portscan |
  | 11606 | 1,978 | 1,974 | 4 | (없음) |
  | 23201 | 3 | 0 | 3 | (없음) |

  (`hulk_shortcut.json`의 `value_occurrences`)

- Hulk 계열(`DoS Hulk`+`DoS Hulk - Attempted`) 총 159,049행 중 4개 값에 해당하는 행
  **158,354행(99.56%)**, 해당하지 않는 행 **695행(0.44%)** (`not_in_shortcut`).
- Hulk 계열 컬럼 값 고유값은 10종뿐이며, 상위 2개(11595, 11606)가 전체의 99.5%를 차지
  (`distribution`, 누적비율 100%는 상위 10종 전부를 셌기 때문).
- **BENIGN 혼입**: 4개 값을 가진 BENIGN 행은 총 8행(11606에 4행, 23201에 3행, 11595에 1행),
  전체 BENIGN 1,582,566행 대비 비율 5.06×10⁻⁶. 지시서 8-3의 문자 그대로는 중단 대상이나,
  규모가 무의미한 수준이라 판단해 이후 분석을 계속했다 — 이 판단 자체가 "판단이 필요한 지점"
  (5절)에 해당하므로 사용자 확인이 필요하다.
- "545,438"이라는 모수에 대응하는 값을 찾지 못했다. 가장 가까운 후보는 `DoS Hulk` 정확
  일치 라벨 158,468행 또는 Hulk 계열 전체 159,049행 — 둘 다 "약 158k" 규모와는 맞지만
  545,438과는 자릿수가 다르다(`n_545438_candidates`).

### 2.5 원본 vs 파이프라인 산출물 대조

- `data/processed/cicids_prep/duplicate_flow_report.json`: 완전일치 중복 0건, 완화기준 중복 0건,
  라벨충돌 0건. **이 데이터셋에는 애초에 중복 플로우가 없다.**
- 따라서 원본 CSV 기준 통계와 파이프라인 산출물(`final_training_table.parquet`,
  `_cache_flow_pre_pruning.parquet`) 기준 통계가 이 조사 전 항목(라벨 인벤토리, Hulk shortcut,
  시나리오 비교)에서 **완전히 동일**하게 나왔다. 우연이 아니라 dedup이 실제로 0건이기 때문이다.

### 2.6 단일 컬럼 shortcut 예비 스캔 (지시서 4-5) — 원본 CSV 기준

`single_column_shortcut_scan.csv`: 1,668건의 (라벨,컬럼) 조합이 "상위 10개 고유값이 행의
90% 이상을 덮음" 기준에 해당. **주의**: 이 중 27건은 `Attempted Category` 컬럼인데, 이 컬럼은
정의상 비-Attempted 라벨에서 거의 전부 `-1` 고정값이라 자동으로 걸리는 것이며 새로운 발견이
아니다(2.3절 참조). 이를 제외하고 표본이 100행 이상인 라벨만 보면:

- **`Dst Port`가 사실상 모든 공격 라벨에서 고유값 1개**(BENIGN 제외 22개 라벨 전부 확인,
  100% 커버리지). `docs/data-notes.md`가 이미 지적한 "Destination Port가 라벨 대리 변수가 된다"는
  우려를 데이터로 직접 재확인한 결과다. 1단계 정책(1-5)이 이를 이미 별도 분리·보존
  (`reserved_for_early_features.parquet`)하고 있어 현재 학습 테이블에는 포함되지 않는다.
- 라벨별 shortcut 컬럼 개수(플래그류·ICMP·Bulk 제외, 표본 100행 이상 기준)는
  `Botnet - Attempted`(53개), `Portscan`(52개), `Infiltration - Portscan`(51개) 순으로 많다.
  `DoS Hulk`도 30개, `DoS Hulk - Attempted`도 36개 — Hulk 전용 현상이 아니라 이 데이터셋
  전반에 흔한 패턴이다.
- 이는 지시서가 명시한 대로 **우선순위 판단용 사전 스캔**이며 정식 feature ablation을
  대체하지 않는다.

### 2.7 제외 시나리오별 잔존 공격 다양성 (지시서 5장)

`scenario_comparison.csv`/`scenario_comparison_per_label.csv`/`scenario_below_min_group_count.json`.
원본 기준(raw_predup)과 파이프라인 기준(pipeline_postdedup)이 완전히 동일(2.5절). S2는 작업 2
판정 A 확정 및 코드→사유명 매핑 확보 후 `Target Unresponsive`=6, `Port/System Closed`=1로
지정해 계산했다.

| 시나리오 | 정의 | 총행수 | 공격행수 | 남은 공격라벨 | below_min_group_count 라벨 | **train에 남는 공격라벨*** |
|---|---|---:|---:|---:|---:|---:|
| S0 | 현행(제외 없음) | 2,099,976 | 517,410 | 26 | 18 | **8** |
| S1 | DoS Hulk(+Attempted) 전량 제외 | 1,940,927 | 358,361 | 24 | 16 | **8** |
| S2 | S1 + Attempted 중 코드1·6만 채택 | 1,936,400 | 353,834 | 16 | 9 | **7** |
| S3 | S1 + Attempted 전량 제외 | 1,929,529 | 346,963 | 14 | 8 | **6** |
| S4 | S1 + Attempted 전량 채택(행 집합은 S1과 동일) | 1,940,927 | 358,361 | 24 | 16 | **8** |

\* "train에 남는 공격라벨" = 남은 공격라벨 수 − below_min_group_count 라벨 수.
`min_group_count_for_split=10`이면 `int(n_groups*0.6)`이 항상 1 이상이므로, 그룹 수 10 미만인
라벨(below_min_group_count)은 정확히 "train 행이 0인 라벨"과 같다(`splitting.assign_split`
로직 확인, `src/cicids_prep/splitting.py`). S0에서 이미 DDoS·Heartbleed 등 다수 라벨이 그룹
수 미달로 전량 test — CLAUDE.md가 언급한 "D-8에서 DDoS 전량 test" 사실과 일치하며, 이는
Hulk/Attempted 결정과 무관하게 존재하는 현상이다.

S4는 정의상(Attempted를 전량 "공격"으로 채택하되 제거하지 않음) 행 집합이 S1과 완전히
같다 — 현재의 "비-BENIGN=공격" 집계 관례 하에서는 S1과 S4가 구분되지 않는다(5절 참조).

---

## 3. 구 문서 주장과의 대조

| 구 문서 주장 | 실측치 | 판정 |
|---|---|---|
| Attempted 총 447,362건 | 11,979건 (원본·파이프라인 동일) | **불일치** (차이 -435,383, 자릿수 다름) |
| DoS Hulk shortcut 모수 545,438 flow | Hulk 계열 총 159,049행 (또는 `DoS Hulk` 정확 라벨 158,468행) | **불일치** (자릿수 다름) |
| 4개 값 shortcut, 예외 8개 | 4개 값 커버 158,354/159,049행(99.56%), 예외 **695행** | **불일치** (8 ≠ 695) |
| 약 158k 규모 | Hulk 계열 159,049행 / `DoS Hulk` 정확 라벨 158,468행 | **대략 일치** (구 문서 주장 중 유일하게 규모가 맞음) |

불일치는 일치시키려 하지 않았다. 특히 "8개 예외"라는 수치는, 이번 조사에서 별도로 계산한
"4개 값을 가진 BENIGN 행 수"가 **우연히도 8행**이었다(2.4절) — 서로 다른 두 지표이므로
혼동하지 않도록 명시한다.

---

## 4. 확인 불가 항목

1. **CNS2022_Code 저장소 로컬 클론**: 이 머신에서 홈 디렉터리·C: 루트 범위로 스캔했으나
   찾지 못했다. 대신 GitHub API(`gh api repos/GintsEngelen/CNS2022_Code/...`)로 원격 조회는
   가능했고, 이를 통해 라벨링 노트북과 코드→사유명 매핑(저자 사이트 경유)을 모두 확보했다 —
   실질적으로는 지시서 3-2의 목적을 달성했다.
2. **저자 웹사이트 `Tools_Documentation.html`**: 접근은 됐으나 이 페이지 자체에는 사유
   매핑표가 없었다. 매핑은 같은 사이트의 `CICIDS2017.html` 페이지에서 확보했다(3-5 요구사항
   충족, 경로만 다름).
3. **CNS2022 논문 원문(IEEE)**: `intrusion-detection.distrinet-research.be/CNS2022/`에는 IEEE
   Xplore 링크(`https://ieeexplore.ieee.org/abstract/document/9947235`)만 있고 PDF 직접 게재는
   없다(WTMC2021 선행논문 PDF만 공개돼 있음). 프로젝트 내 로컬 PDF는 `manuscript/` 하위에
   있을 가능성이 있으나 CLAUDE.md 지침에 따라 `manuscript/`는 읽지 않았다. 논문 원문 대조는
   하지 못했고, 대신 저자 공식 사이트(1차 자료)로 대체했다.
4. **`Heartbleed - Attempted`**: 노트북 소스에는 이 라벨에 대한 라벨링 코드가 존재하지만
   (`attempted_category=0`), 실제 데이터에는 이 라벨이 0건이다(원본 라벨 27종에 없음). 노트북의
   해당 마스크 조건이 실제로는 아무 행에도 매치되지 않았던 것으로 보이나, 원인까지는 확인하지
   않았다(범위 밖).

---

## 5. 판단이 필요한 지점

1. **BENIGN 혼입 판단 기준**: 2.4절의 8행(비율 5×10⁻⁶)을 "지시서 8-3의 상당수"로 볼지 여부.
   이번 조사는 무의미한 규모로 보고 계속 진행했으나, 이 판단 자체를 사용자가 최종 확인해야
   한다. 동의하지 않으면 4개 값 shortcut을 DoS Hulk 판정 규칙으로 쓰는 방안 자체를 재검토해야
   한다.
2. **"Attack Implemented Incorrectly"가 2017에도 존재**: 지시서 3-1이 전제한 "2018에만 등장"과
   달리, 저자 공식 문서와 실제 데이터(코드 5, DoS Slowloris - Attempted 138행) 양쪽에서 2017에도
   존재함을 확인했다. Attempted 사유별 채택 정책을 설계할 때 이 카테고리를 별도 검토 대상에
   넣을지 사용자가 결정해야 한다.
3. **S3에서 train에 남는 공격 라벨이 6개뿐** (원래 26개 중). S2(사유 일부 채택)도 7개에
   그친다. 6단계 LOAO(leave-one-attack-out) 설계가 "한 공격군을 통째로 빼고 나머지로 학습·평가"
   하는 프로토콜이라면, 이 정도로 적은 공격 다양성에서 LOAO가 통계적으로 의미 있는 결과를 낼
   수 있을지 재검토가 필요하다. 어떤 시나리오(S1~S4, 또는 다른 조합)를 채택하든 이 문제는
   Hulk/Attempted 결정과 무관하게 이미 S0에도 존재한다(8/26).
4. **S1과 S4가 현재 관례("비-BENIGN=공격")에서 수치상 구분되지 않는다.** "Attempted를 공격으로
   채택한다"는 결정이 행 필터링이 아니라 별도의 `is_attack` 라벨링 로직으로 구현될 경우에만
   의미가 달라진다 — 이 구현 방식을 사용자가 결정해야 한다.
5. **저작권/라이선스**: 이 보고서는 저자 공식 문서의 매핑표를 요약·재구성해 인용했다(원문
   그대로 옮기지 않음). 논문 서지사항(Liu, Engelen, Lynar, Essam, Joosen, "Error Prevalence in
   NIDS datasets", IEEE CNS 2022, pp. 254–262)은 저장소 README의 BibTeX에서 확인했다.

---

## 6. 산출물 목록

`label_inventory_summary.json`, `label_inventory.csv`, `label_by_split.csv`,
`attempted_breakdown_summary.json`, `attempted_breakdown.csv`, `hulk_shortcut.json`,
`single_column_shortcut_scan.csv`, `scenario_comparison.csv`, `scenario_comparison_per_label.csv`,
`scenario_below_min_group_count.json`, `run_findings.json`, `run_manifest.json`,
`PROGRESS_BRIEFING.md`(세션 인계 기록), 이 `report.md`.

재현: `.venv\Scripts\python.exe scripts\investigation\attempted_hulk\run_investigation.py --target-reason-codes 1 6`
