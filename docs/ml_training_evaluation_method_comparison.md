# ML 학습·평가 방식 비교표

이 문서는 D-006을 결정하기 위한 **설명 자료**다. 확정된 프로토콜의 정본은
[`CURRENT_DECISIONS.md`](CURRENT_DECISIONS.md)의 D-006이며, 이 문서는 결정 상태를 기록하지 않는다.

---

## 1. 세 역할의 구분

| 역할 | 답하는 질문 | 적용 데이터 | 예시 |
|---|---|---|---|
| 학습 목적함수 | 트리를 어느 방향으로 갱신할 것인가 | 내부 train | binary log loss |
| early stopping 지표 | 몇 번째 boosting iteration에서 멈출 것인가 | 내부 validation | validation binary log loss |
| 최종 주 지표 | 완성된 모델이 연구 질문에 답하는가 | 외부 test | AURC |

세 역할은 서로 대체하는 지표가 아니다. 학습 목적함수는 모델 파라미터를 만들고, early stopping
지표는 학습 길이를 선택하며, 최종 주 지표는 선택이 끝난 모델을 평가한다. 외부 test는 앞의 두
선택에 사용하지 않는다.

## 2. 학습 목적함수 비교

| 방식 | 핵심 원리 | 장점 | 한계·주의점 | 이 서브실험에서의 적합성 |
|---|---|---|---|---|
| 무가중 binary log loss | 모든 표본의 이진 교차엔트로피를 동일 가중치로 최소화 | 표준 구현, 안정적 학습, 확률 출력과 자연스럽게 연결, 해석이 단순 | 클래스별 운영 비용을 직접 반영하지 않음 | 최초 기준 모델에 적합 |
| 가중 binary log loss | 정상·공격 또는 표본별 손실에 다른 가중치를 부여 | 소수 클래스 또는 미탐 비용을 강조 가능 | 확률 분포와 0.5 임계값의 의미가 변할 수 있고 가중치가 추가 튜닝 대상이 됨 | 비용비가 확정된 후 비교 후보 |
| Focal loss | 쉬운 표본의 영향을 줄이고 어려운 표본에 집중 | 극심한 불균형·hard example 학습에 유리할 수 있음 | 사용자 정의 구현과 추가 파라미터가 필요하고 확률이 왜곡될 수 있음 | 후속 비교 후보 |
| 비용 민감 손실 | 오탐·미탐의 실제 비용을 손실에 직접 반영 | 운영 목적과 직접 정렬 가능 | 신뢰할 수 있는 비용비가 먼저 필요함 | 현재 비용비가 없어 보류 |
| AURC 직접 최적화 | selective prediction 성능을 학습 중 직접 개선 | 최종 연구 목표와 표면적으로 가장 가까움 | 전체 confidence 순위에 의존하여 표본별 미분 손실로 쓰기 어렵고 구현·검증 부담이 큼 | 평가 지표로 사용하는 편이 적합 |

## 3. Early stopping 지표 비교

| 지표 | 무엇을 보는가 | 장점 | 한계·주의점 | 이 서브실험에서의 적합성 |
|---|---|---|---|---|
| Validation binary log loss | 정답 클래스에 부여한 확률의 손실 | 목적함수와 일치, 전 표본을 사용, 변화가 비교적 안정적, 임계값 비의존 | confidence 순위 자체를 직접 최적화하지는 않음 | 기준 지표로 적합 |
| Validation AUROC | 공격 점수가 정상보다 높은 순위에 놓이는 정도 | 임계값 비의존, 전반적인 분리 능력 평가 | 불균형 상황에서 낙관적일 수 있고 확률 품질을 보지 않음 | 보조 모니터링 후보 |
| Validation AUPRC / Average Precision | 공격 클래스의 precision-recall 순위 품질 | 불균형 데이터의 양성 탐지에 민감 | 정상 측 오류와 양방향 abstention confidence를 충분히 표현하지 못함 | 보조 모니터링 후보 |
| Validation error / Accuracy | 0.5 임계값 기준 오분류율 | 직관적이고 계산이 단순 | 확률 변화에 둔감하고 불균형의 영향을 받으며 confidence 품질을 보지 않음 | early stopping 기준으로 부적합 |
| Validation AURC | 낮은 confidence부터 보류했을 때의 risk-coverage 면적 | 최종 목표와 직접 연결 | iteration별 순위 변동에 민감하고 계산·구현 규칙 의존성이 크며 validation에 과적합될 수 있음 | AURC 정의 검증 후 연구 확장 후보 |

LightGBM은 여러 validation 지표가 주어지면 기본적으로 모두 early stopping에 관여시킨다.
한 지표만 기준으로 삼으려면 `first_metric_only=true`로 명시해야 한다.

## 4. 최종 평가 지표 비교

| 지표 | 답하는 질문 | 장점 | 한계·주의점 | 권장 역할 |
|---|---|---|---|---|
| AURC | 오류 가능성이 높은 flow를 confidence로 잘 선별해 보류할 수 있는가 | 전체 risk-coverage 관계를 하나의 값으로 요약, abstention 연구 질문과 직접 일치 | confidence·동률·적분 규칙을 사전에 고정해야 함 | 주 지표 |
| 특정 coverage의 selective risk | 정해진 처리량을 유지할 때 남은 판정의 오류율은 얼마인가 | 운영적으로 직관적 | 선택한 coverage 한 지점에 결론이 좌우됨 | 사전 지정 budget별 보조 지표 |
| Error capture | 유보된 표본이 전체 오류 중 얼마를 포착하는가 | 유보의 실질적 효율을 직접 설명 | 유보율과 함께 읽어야 함 | 보조 지표 |
| FPR / FNR | 정상 오탐과 공격 미탐이 각각 얼마나 발생하는가 | IDS 운영 의미가 명확 | 단일 임계값 의존, abstention 전체 곡선을 요약하지 못함 | 보조 지표 |
| AUROC | 정상·공격 점수의 전반적 순위 분리 능력은 어떤가 | 임계값 비의존, 널리 비교 가능 | 불균형 데이터에서 낙관적일 수 있고 오류 선별 능력과 다름 | 보조 지표 |
| AUPRC | 공격 탐지의 precision-recall 균형은 어떤가 | 불균형 데이터에 유용 | 양성 클래스 관점이며 abstention 능력을 직접 평가하지 않음 | 보조 지표 |
| Accuracy / F1 | 고정 임계값에서 분류 결과가 얼마나 맞는가 | 이해하기 쉬움 | 임계값 의존, confidence와 risk-coverage 구조를 놓침 | 참고 지표; 주 지표로 사용하지 않음 |
| Log loss | 예측 확률이 정답에 얼마나 적합한가 | 고신뢰 오답을 크게 벌점, 학습과 직접 연결 | 오류 선별 순위를 직접 측정하지 않음 | 학습·validation 진단 지표 |
| Brier / ECE | 확률값과 실제 빈도의 보정 정도는 어떤가 | calibration 평가에 적합 | D-004에서 calibration을 범위 밖으로 확정 | 이 서브실험에서는 산출하지 않음 |

## 5. 목적함수와 평가 지표 조합의 해석

| 조합 | 얻는 것 | 잃는 것 또는 위험 |
|---|---|---|
| 무가중 log loss 학습 + log loss early stopping + AURC 최종 평가 | 안정적인 표준 학습과 독립적인 abstention 평가 | AURC를 학습 과정에서 직접 최적화하지 않음 |
| 가중 log loss 학습 + log loss early stopping + AURC 평가 | 공격 오류를 더 강조할 가능성 | confidence와 확률 분포 변화가 AURC에 미치는 영향을 별도 해석해야 함 |
| log loss 학습 + AURC early stopping + AURC 평가 | 학습 길이를 selective 성능에 직접 맞춤 | 내부 validation AURC 과적합과 순위 변동 가능성 |
| focal loss 학습 + AURC 평가 | 어려운 표본 집중 효과를 시험 가능 | 구현 복잡도와 추가 파라미터로 기준 실험의 해석이 어려워짐 |

## 6. 참고 자료

- LightGBM 공식 Parameters 문서: <https://lightgbm.readthedocs.io/en/latest/Parameters.html>
- LightGBM 공식 Python early stopping 문서: <https://lightgbm.readthedocs.io/en/v4.6.0/pythonapi/lightgbm.early_stopping.html>
- 이 프로젝트의 확정사항: [`CURRENT_DECISIONS.md`](CURRENT_DECISIONS.md) D-006

