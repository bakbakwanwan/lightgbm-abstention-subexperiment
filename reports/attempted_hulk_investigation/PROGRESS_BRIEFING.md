# 진행 상황 브리핑 (세션 인계용)

작성 시각: 2026-09-10. 대상 작업: `tasks/instruction_attempted_hulk_investigation.md`.
승인된 실행 계획: `C:\Users\user1\.claude\plans\prancy-jingling-crown.md`.

## 지금까지 한 일

1. `scripts/investigation/attempted_hulk/` 패키지 작성 완료 (읽기 전용 조사 코드).
   `columns_resolve.py`, `raw_loader.py`, `label_inventory.py`, `attempted_breakdown.py`,
   `hulk_shortcut.py`, `scenario_compare.py`, `manifest_util.py`, `run_investigation.py`.
2. `.venv\Scripts\python.exe scripts\investigation\attempted_hulk\run_investigation.py` 실행 완료 (2회 — 1회차는
   BENIGN 혼입 게이트가 과민하게 잡혀 중단, 게이트를 실제 비율 기준으로 고쳐 재실행).
3. `--target-reason-codes 1 6` 옵션으로 3회차 실행 완료 (아래 "코드→사유명 매핑" 확정 후 S2 시나리오 산출).
4. `reports/attempted_hulk_investigation/`에 산출물 전부 생성됨 (파일 목록은 아래).

## 확정된 핵심 사실 (report.md 작성 시 그대로 쓸 것)

- **헤더**: 5개 CSV 헤더 완전 동일, 91개 컬럼. 라벨=`Label`, Attempted 사유=`Attempted Category`,
  Hulk shortcut 대상=`Total Length of Bwd Packet`(지시서가 언급한 복수형 `Packets`가 아니라 단수형).
- **판정: 작업2는 A(직접 구분 가능)로 확정.** `Attempted Category`와 `Label`의 Attempted 여부가
  전체 2,099,976행에서 **완전히 일치**(`n_mismatch=0`, `attempted_breakdown_summary.json`).
- **코드→사유명 매핑을 저자 공식 사이트에서 확보함** (GitHub API로 `CNS2022_Code` 저장소의
  `Labelling/CICIDS2017_labelling_fixed_CICFlowMeter.ipynb`를 확인 → 코드가 사유명 대신 정수로만
  기록되어 있고 "저자 웹사이트 참고"라 되어 있어, `https://intrusion-detection.distrinet-research.be/CNS2022/CICIDS2017.html`을
  WebFetch로 조회해 확보):
  - 0 = No payload sent by attacker (≈ 지시서의 "Empty Payload")
  - 1 = Port/System closed
  - 2 = Attack Startup/Teardown Artefact
  - 3 = No malicious payload
  - 4 = Attack Artefact
  - 5 = **Attack Implemented Incorrectly**
  - 6 = Target System Unresponsive
  - **중요**: 지시서 3-1은 "Attack Implemented Incorrectly"가 2018에만 등장한다고 가정했으나,
    저자 사이트의 2017 문서에 명시되어 있고 실제 데이터에도 존재함(`DoS Slowloris - Attempted` 138행이
    코드 5). **지시서의 이 전제는 실측과 어긋난다** — report.md "구 문서 주장과의 대조"에 반드시 명시.
  - S2 시나리오는 이 매핑에 따라 `Target Unresponsive`=6, `Port/System Closed`=1로 지정해 계산함.
- **라벨 인벤토리**: 원본 기준 고유 라벨 27개, Attempted 총 11,979행.
  **구 문서 447,362건과 차이 -435,383 — 자릿수 자체가 다른 규모의 불일치.** (`label_inventory_summary.json`)
- **DoS Hulk shortcut**:
  - Hulk 계열(주1) 전체 159,049행 중 4개 값(11595/23190/11606/23201)에 해당하는 행 158,354행,
    **해당 안 되는 행 695행** — 구 문서의 "8개 예외"와 불일치(695 ≠ 8).
  - BENIGN 오염: 4개 값을 가진 BENIGN 행은 총 8행 (`11606`에 4행, `23201`에 3행, `11595`에 1행),
    전체 BENIGN 1,582,566행 대비 비율 5.06e-06 — **"상당수"로 보기 어려움**. 지시서 8-3의 문자 그대로는
    중단 대상이나, 규모가 무의미할 정도로 작아 실행을 계속했음(그 판단 근거를 `run_investigation.py`
    주석과 `hulk_shortcut.json`의 `benign_contamination` 필드에 남김). **report.md에 이 판단을 그대로
    적을지, 아니면 사용자 확인을 받을지는 사용자가 최종 결정할 사안으로 "판단이 필요한 지점"에 남길 것.**
  - 구 문서 545,438(모수)에 대응하는 값을 데이터에서 찾지 못함 — 가장 가까운 후보는
    `dos_hulk_exact_label_rows_raw`=158,468 또는 Hulk 계열 전체=159,049. 545,438과는 자릿수가 다름.
  - `n_unique_values`=10 (Hulk 계열 컬럼 값 종류), 상위 2개 값이 전체의 99.5% 이상 차지.
  - 원본 CSV와 파이프라인 산출물(`_cache_flow_pre_pruning.parquet`, `final_training_table.parquet`) 간
    행수 차이 없음 — `duplicate_flow_report.json` 확인 결과 **이 데이터셋에는 완전일치·완화기준 중복이
    0건**(이미 정제되어 있음). 따라서 이번 조사에서 "원본 기준"과 "파이프라인 기준" 수치가 시나리오
    비교를 포함해 전부 동일하게 나옴 — 우연이 아니라 이 데이터셋의 실제 특성.
- **단일 컬럼 shortcut 예비 스캔**: 1,668건의 (라벨,컬럼) 조합이 top10-coverage≥0.9로 걸림
  (`single_column_shortcut_scan.csv`, 미검토). **주의**: `Attempted Category` 자체가 비-Attempted 라벨에서는
  거의 전부 -1 고정값이라 이 스캔에서 자동으로 "shortcut"처럼 잡힌다 — 이건 컬럼 정의상 당연한 것이지
  진짜 발견이 아니므로 report 작성 시 이 컬럼 관련 행은 별도로 걸러서 설명해야 한다.
- **시나리오 비교(S0~S4, `scenario_comparison.csv`)**: raw_predup과 pipeline_postdedup 두 기준이
  완전히 동일(위 dedup=0건 이유). 핵심 수치:

  | 시나리오 | 총행수 | 공격행수 | 남은 공격라벨 | below_min_group_count | train에 남는 공격라벨(추정) |
  |---|---|---|---|---|---|
  | S0(현행) | 2,099,976 | 517,410 | 26 | 18 | **8** |
  | S1(Hulk만 제외) | 1,940,927 | 358,361 | 24 | 16 | **8** |
  | S2(Hulk제외+Attempted 중 코드1·6만 채택) | 1,936,400 | 353,834 | 16 | 9 | **7** |
  | S3(Hulk+Attempted 전량 제외) | 1,929,529 | 346,963 | 14 | 8 | **6** |
  | S4(Hulk제외, Attempted 전량 채택=S1과 행집합 동일) | 1,940,927 | 358,361 | 24 | 16 | **8** |

  "train에 남는 공격라벨"은 (남은 공격라벨 수 − below_min_group_count 라벨 수)로 계산(코드 근거:
  `min_group_count_for_split=10`이면 `int(n*0.6)`이 항상 ≥1이므로 이 등식이 성립함, `splitting.py` 로직 확인함).
  **S0 기준으로도 이미 26개 공격 라벨 중 8개만 train에 등장** — Hulk/Attempted 결정과 무관하게 존재하는
  근본적인 문제(CLAUDE.md가 이미 알고 있는 "DDoS가 그룹 수 미달로 전량 test" 사실의 확장판).
  S3(가장 보수적 제외)에서는 **6개**로 더 줄어듦 — 6단계 LOAO 설계가 성립하려면 이 숫자가 핵심 근거.

## ⚠️ 미해결 — 다음 세션이 반드시 먼저 확인할 것

`scenario_below_min_group_count.json`의 **S2** 항목에 `DoS Hulk`(5그룹), `DoS Hulk - Attempted`(6그룹)가
**S0과 완전히 동일한 수치로 다시 나타난다.** S2는 정의상 S1(Hulk 전량 제외)의 부분집합이어야 하므로
Hulk 계열 행이 S2에 단 한 건도 남아있으면 안 되고, 따라서 이 목록에 아예 등장하지 않아야 정상이다
(0행짜리 라벨은 groupby 결과에 나타나지 않음). 이 이상 현상은 디버깅 도중 사용자 요청으로 작업이
중단되어 **원인을 확인하지 못했다.**

다음 세션에서 가장 먼저 할 일:
1. `scenario_compare.build_scenario_masks`가 반환한 `S2` 마스크로 `raw_df[s2]`를 직접 필터링해
   `Label`이 `DoS Hulk`/`DoS Hulk - Attempted`인 행이 실제로 0건인지 확인한다.
   - 0건이면: `compute_below_min_group_count` 또는 `run_scenario_set`의 `exclusion_report` 키 매핑에서
     기저(basis)나 시나리오 이름이 잘못 섞이는 버그(예: 이전 시나리오의 `excluded` 리스트를 덮어쓰지 못하고
     누적하는 문제)를 의심하고 코드를 다시 본다.
   - 0건이 아니면: `build_scenario_masks`의 S2 계산식(`s2 = s1 & (~attempted_mask | keep_attempted)`) 자체나
     `hulk_family_labels`/`attempted_labels_list` 산출 로직을 재검토한다.
2. 버그를 고친 뒤 `run_investigation.py --target-reason-codes 1 6`을 다시 실행해 `scenario_comparison.csv`,
   `scenario_comparison_per_label.csv`, `scenario_below_min_group_count.json`을 재생성한다.
3. 그 다음에야 위 표의 S2 관련 수치(총행수 1,936,400 등)를 신뢰할 수 있다 — **현재 커밋되는 S2 수치는
   검증 전이므로 report.md를 쓸 때 이 사실을 명시하거나, 검증 후에 report.md를 작성한다.**

## 아직 안 한 일

1. `single_column_shortcut_scan.csv` 검토·요약 (Attempted Category 노이즈 제외하고 의미있는 것만 추림).
2. **`report.md` 작성 자체를 아직 안 함** — 이게 지시서의 최종 산출물인데 위 S2 버그 때문에 보류 중.
   지시서 7장 형식(판정요약→작업별 결과→구문서대조→확인불가항목→판단필요지점) 그대로 쓰면 됨,
   재료는 이 브리핑과 `reports/attempted_hulk_investigation/*.json,*.csv`에 다 있음.
3. `run_manifest.json`은 매 실행마다 덮어써짐 — 최종 실행 기준으로 다시 한번 확인 필요.

## 파일 목록 (`reports/attempted_hulk_investigation/`)

`label_inventory_summary.json`, `label_inventory.csv`, `label_by_split.csv`,
`attempted_breakdown_summary.json`, `attempted_breakdown.csv`,
`hulk_shortcut.json`, `single_column_shortcut_scan.csv`,
`scenario_comparison.csv`, `scenario_comparison_per_label.csv`, `scenario_below_min_group_count.json`,
`run_findings.json`, `run_manifest.json`, 그리고 이 브리핑 파일.

지시서가 요구한 `attempted_breakdown.csv`는 "라벨×사유"인데 사유명이 아니라 사유코드로 되어 있다 —
위 코드→사유명 매핑표를 report.md에서 join해서 보여줘야 한다(CSV 자체를 코드로 재생성할 필요는 없음,
매핑은 report.md 텍스트에서 설명).
