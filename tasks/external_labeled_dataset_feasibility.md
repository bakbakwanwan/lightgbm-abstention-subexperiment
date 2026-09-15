# 독립 라벨 데이터 확보 후보 조사 (2026-09-15)

**상태:** 제공처 자료를 이용한 후보 조사. 파일을 다운로드하거나 스키마·라벨을 실제 CSV에서 검증하지 않았다. 이 문서는 새 실험 스펙이나 데이터 사용 승인 기록이 아니다.

## 1. 우선 후보: Improved CSE-CIC-IDS2018

EXP-007의 데이터와 다른 수집 환경·시기의 CSE-CIC-IDS2018을, CIC-IDS2017 정제판과 **같은 CNS2022 연구팀이 수정한 버전**이다. 제공처는 정제판 데이터와 별도의 [라벨링 문서](https://intrusion-detection.distrinet-research.be/CNS2022/CSECICIDS2018.html), [수정 CICFlowMeter 설명](https://intrusion-detection.distrinet-research.be/CNS2022/Tools_Documentation.html)을 공개한다. 같은 추출 도구 계열이므로 현재 59개 피처와의 의미 대응을 먼저 확인하기 좋은 후보라는 **추론**이다. 정확히 59개가 같은 이름·단위·값 정의로 제공되는지는 확인하지 못했다.

제공처 [다운로드 목록](https://intrusion-detection.distrinet-research.be/CNS2022/Datasets/)의 `CSECICIDS2018_improved.zip` 크기는 9.7GB다. 현재 PC의 C: 여유 공간은 조사 시점 약 29.4GB이므로, 전체 파일 확보와 압축 해제에 필요한 공간·저장 경로를 먼저 산정해야 한다. 내려받기를 아직 진행하지 않는다.

라벨 매핑도 그대로 복사할 수 없다. [정제판 2018 문서](https://intrusion-detection.distrinet-research.be/CNS2022/CSECICIDS2018.html)는 Attempted 사유와 DoS Hulk 문제를 다루지만, 일부 공격 구현·라벨 상태가 2017과 다르다고 기록한다. 다운로드 전 문서만으로 D-001·D-002의 관찰군 규칙을 새 데이터에 자동 적용하지 않는다. 우선 CSV 헤더와 원래 Label 전수, Attempted 코드, DoS Hulk 관련 행을 감사해야 한다.

## 2. 대안 후보: CIC-UNSW-NB15 Augmented

[UNB의 제공처 페이지](https://www.unb.ca/cic/datasets/cic-unsw-nb15.html)에 따르면 UNSW-NB15의 패킷에서 CICFlowMeter flow를 새로 추출해 원래 ground truth와 맞추고, 라벨이 모호한 flow는 제외했다. 다른 기관·수집 환경의 데이터를 같은 일반적인 flow 추출 계열로 본다는 점에서 독립성 후보가 된다. 다만 제공 페이지의 `Data.csv`는 정상 flow를 **80:20 비율로 무작위 축소**한 버전이고, `CICFlowMeter_out.csv`에는 추출·라벨된 원래 flow가 있다. 실제 트래픽 분포의 유보 처리량을 평가할 목적이라면 축소본을 무심코 사용하면 안 된다.

이 버전은 EXP-007의 CNS2022 수정 CICFlowMeter와 같다는 근거가 없다. 피처 명칭뿐 아니라 flow 종료 방식, 단위, 결측 처리의 동일성도 아직 미검증이다. 피처 대응이 맞지 않으면 현재 59-feature 모델의 직접 외부 test로 사용할 수 없다.

## 3. 더 독립적이지만 직접 비교가 어려운 UNSW-NB15 원본

[UNSW 원 제공처](https://research.unsw.edu.au/projects/unsw-nb15-dataset)는 Argus·Bro-IDS 등을 이용한 49개 특징과 라벨, 별도 train/test CSV를 제공한다. 수집 기관과 특징 추출 방법이 달라 독립 환경 평가에는 매력적이지만, **현재 59-feature 입력과 직접 호환되지는 않는다.** 이를 사용하려면 공통 피처 정의·모델 재학습부터 별도 사전 실험으로 설계해야 한다. EXP-007의 confidence 경계 이동 검증을 빠르게 수행하는 자료로 취급하지 않는다.

## 4. 파일 확보 전에 완료해야 할 감사

1. 원 제공처에서 받을 정확한 버전·파일 목록·라이선스/인용 조건과 SHA256을 기록한다. 임의의 3차 가공본으로 대체하지 않는다.
2. 헤더만 먼저 대조하고 59개 입력 피처 각각의 **이름·단위·계산 규칙**이 같은지 확인한다. 이름 변경만으로 값의 의미가 같다고 가정하지 않는다. `Protocol` 범주 값과 `Flow Bytes/s`의 Infinity·결측도 확인한다.
3. 원래 Label의 전수와 정상/공격 및 Attempted/무효 클래스의 취급을 결정 문서에 맞춰 별도 확정한다. 일부 공격의 원래 Label이 사라진 조건을 EXP-007의 같은 class 조건으로 비교하지 않는다.
4. 원본 분포를 유지할지, 저장 공간 때문에 사전 표본을 만들지, 별도 제공 split을 사용할지 **결과를 보기 전에** 정한다. 유보율의 분모와 후속 검증량을 함께 기록한다.
5. EXP-007 모델을 그대로 적용할 수 있다는 피처 감사 결과가 나올 때에만 독립 test의 AURC·고정 경계 유보율을 새 스펙으로 설계한다. 그렇지 않으면 새 모델과 새 연구 질문이 필요하다.

이 자료의 결과는 EXP-008의 같은 데이터 분할 민감도 분석과 구분한다. EXP-008 결과가 좋아도 독립 데이터 확보·감사가 생략되지는 않는다.
