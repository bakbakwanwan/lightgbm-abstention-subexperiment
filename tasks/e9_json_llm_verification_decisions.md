# E9 JSON LLM 검증 — 단계적 결정 기록

> 상태: 작업용 결정 기록. 이 문서는 확정 실험 스펙이 아니다.
>
> 목적: 첫 Layer 2 실험에 필요한 결정을 한꺼번에 확정하지 않고, 맥락상 함께 결정할 수 있는 묶음 단위로 합의·기록한다. 현행 Layer 1의 확정 결정과 충돌할 경우 `docs/CURRENT_DECISIONS.md`가 우선한다.

## 1. 이번 기록에서 확정한 범위

1. 첫 Layer 2 실험은 **RAG 없이**, 유보된 flow의 구조화된 JSON 직렬화만 local LLM에 제공하는 LLM-only 검증이다.
2. CTI corpus, MITRE ATT&CK, CVE 및 retrieval은 이 첫 실험의 범위에 넣지 않는다. 이후 별도 실험에서 검토한다.
3. 첫 실험의 주 비교는 같은 유보 flow에 대한 Layer 1 forced decision과 LLM-only JSON verification이다.
4. 실제 운영의 유보 처리량은 가용 `verification_budget`과 당시 confidence 분포에 따라 동적으로 변할 수 있다.
5. 실험의 1%·2%·5%·10% 유보 집합은 운영 유보율을 고정하는 정책이 아니라, 서로 다른 처리 예산 조건을 비교하기 위한 재현 가능한 평가 snapshot이다.
6. 각 LLM 실행 결과에는 그 실행에서 실제 사용한 유보 행 식별자와 선택 규칙을 남긴다. 이를 통해 prompt·모델 변경 시 같은 flow 집합에서 비교한다.

## 2. 현재 미결 — 다음 논의 묶음

### A. Layer 1 → Layer 2 입력 계약 — 확정

1. 기본 LLM 입력에는 Layer 1의 `p_attack`, `confidence`, `predicted_label`을 넣지 않는다. 이 값들은 평가 및 fallback 전용으로 보존한다.
2. 실제 운영의 유보 행은 동적으로 선택한다. 각 완료된 LLM 실행은 재현성을 위해 실제 사용한 `(day, id)` 목록, budget, threshold 및 source prediction artifact hash를 결과 manifest에 남긴다.
3. 기본 LLM 입력의 관측값은 Layer 1 whitelist의 59개 피처로 한정한다. `day`, `id`, `Label`, `binary_label`, `is_error`, `Attempted Category`는 평가·추적 전용이며 prompt JSON에 넣지 않는다.
4. `abstained`는 모든 E9 입력에서 상수 `true`이므로 prompt JSON에 넣지 않는다. 선택 사실과 관련 메타데이터는 실행 manifest에만 기록한다.
5. Layer 2 전용 schema snapshot과 input template 파일은 필요하지만, 실제 파일 생성은 후속 구현 단계로 보류한다.

### B. JSON 직렬화 규칙

1. LLM prompt의 JSON 본문은 `flow_features` 객체 하나만 둔다. schema version·whitelist SHA·실행 ID 같은 재현성 메타데이터는 실행 manifest에만 기록한다.
2. 키 이름은 Layer 1 whitelist의 원래 피처명을 그대로 사용하며, 키 순서는 후속 구현에서 생성할 Layer 2 feature schema snapshot의 배열 순서로 고정한다.
3. 값은 Layer 1에 실제 입력된 전처리 후 값으로 쓴다. `Protocol`은 `TCP`/`UDP`/`ICMP`/`UNKNOWN`으로, 유한 수치는 원값 JSON number로, `NaN`·`+Infinity`·`-Infinity`는 `null`로 표현한다.
4. 반올림, 로그 변환, 범위 등급화, 문자열 단위 표기는 하지 않는다.
5. 첫 실험에는 정상 범위, 포트 서비스명, 사람이 읽는 파생 설명을 추가하지 않는다.

### C. LLM 생성·평가 계약

1. 첫 E9의 LLM 출력은 아래 최소 JSON schema로 고정한다. `attack_type`, LLM confidence, reason, observed indicators는 첫 E9 범위 밖이며 이후 별도 조건에서만 추가한다.

   ```json
   { "decision": "BENIGN | ATTACK | INDETERMINATE" }
   ```

2. `INDETERMINATE`, parsing failure, timeout의 처리 및 fallback 규칙은 다음 논의에서 확정한다.
   - 유효한 출력은 `decision` 키만 가진 JSON object이며, 값은 대문자 `BENIGN`, `ATTACK`, `INDETERMINATE` 중 하나여야 한다. 여분 키, Markdown code fence, 전후 자연어는 schema 위반이다.
   - `INDETERMINATE`는 정상 결과로 기록하되 시스템 최종 판정에는 Layer 1 forced decision을 사용한다.
   - timeout, 연결 오류, 빈 응답, JSON parse 오류, schema 위반은 `generation_failure`로 기록하고, 시스템 최종 판정에는 Layer 1 forced decision을 사용한다.
   - 첫 E9에서는 요청당 생성 시도 1회만 허용하고 자동 재시도는 하지 않는다.
   - 모든 요청의 raw response, 파싱 결과, 실패 유형 및 latency를 평가용 결과 로그에 보존한다.
3. 아래 모델·generation 설정을 고정한다.
   - Ollama `0.34.1`; model tag `gemma:7b-instruct`; Ollama model ID `a72c7f4d0a15`; base blob SHA-256 `ef311de6af9db043d51ca4b1e766c28e0a1ac41d60420fed5e001dc470c64b77`.
   - Gemma architecture, 9B parameters, Q4_0; model maximum context 8192.
   - `num_ctx=4096`, `temperature=0`, `top_p=1.0`, `num_predict=64`, `seed=42`, `concurrency=1`, `timeout_seconds=60`.
   - Modelfile의 `penalize_newline=false`, `repeat_penalty=1`, stop token `<start_of_turn>`, `<end_of_turn>`을 실행 manifest에 기록한다.
4. pilot은 100 flows로 한다. schema valid rate ≥95%, timeout rate ≤5%, OOM/crash 0을 성공 기준으로 하며 latency p50/p95와 parsing failure rate를 기록한다.
5. pilot source experiment·method·budget은 현재 미지정(`null`)으로 둔다. 이 값들은 pilot 실행 전에 명시적으로 채워야 하며, 비어 있으면 실행을 거부한다.
6. pilot 표본은 대상 유보 집합에서 `(day, id)`의 안정 hash 오름차순 첫 100행을 선택한다. 대상 유보 집합은 pilot source 조건에 따라 달라질 수 있으나, 선택 과정에서 정답·LLM 결과·latency를 사용하지 않는다. source 조건이 달라지면 별도 pilot run으로 기록하며 기존 결과를 덮어쓰지 않는다.

### D. Prompt 계약 — 확정

1. prompt version은 `e9-v1`으로 고정하며, 실행 manifest에 prompt 전문과 그 SHA-256을 기록한다.
2. system instruction은 network-flow feature로부터 `BENIGN`, `ATTACK`, `INDETERMINATE` 중 하나를 이진 검증 결과로 선택하도록 요청한다.
3. 허용된 세 JSON 출력 예와 “정확히 하나의 key만 가진 JSON object”, “설명·Markdown·추가 key 금지”를 system instruction에 명시한다.
4. `INDETERMINATE`는 제공된 feature만으로 방어 가능한 이진 판정을 할 수 없을 때만 사용하도록 지시한다.
5. user prompt에는 `Classify this network flow:`와 `<flow_features>` 경계 안의 렌더링된 flow JSON만 둔다. Layer 1 예측·confidence·정답·평가 전용 정보는 언급하지 않는다.

### E. 평가 계약 — 확정

1. 정답 `binary_label`은 evaluator에서만 사용하며 LLM prompt와 serializer에는 넣지 않는다.
2. 같은 유보 행에 대해 `gate_forced`, `llm_valid_only`, `end_to_end`를 분리한다. `end_to_end`는 유효한 LLM 이진 판정을 사용하고 `INDETERMINATE`·`generation_failure`에는 Gate forced decision을 적용한다.
3. 주 비교는 `gate_forced`와 `end_to_end`이며, Gate 정답/오류에서 final 정답/오류으로의 4가지 전이를 행 수로 기록한다.
4. 각 결과에 error count·error rate·precision·recall·F1·FPR·FNR을 계산하고, `INDETERMINATE` rate·`generation_failure` rate·LLM override rate·latency p50/p95를 별도 기록한다.
5. 100-flow pilot은 실행 가능성 확인용이며, 그 분류 지표 또는 Gate 대비 차이로 성능 우위를 주장하지 않는다. 성능 비교는 사전 지정한 전체 유보 집합에서만 한다.

### F. 결과 로그·manifest 계약 — 확정

1. 실행 manifest에는 E9 experiment ID·실행 시각·git commit, source experiment·split/method·abstention budget·threshold, 실제 선택 `(day, id)` 목록의 SHA-256·행 수, Layer 1 prediction artifact SHA-256, Layer 2 feature schema snapshot SHA-256, input template SHA-256, prompt 전문 SHA-256·`prompt_version`, Ollama·모델 식별값, generation 설정 및 hardware·OS 정보를 기록한다.
2. 요청·응답 JSONL의 각 행에는 evaluator용 `(day, id)`, 입력 JSON SHA-256, raw response, parsed decision, `INDETERMINATE` 여부, `generation_failure` 유형 및 latency를 기록한다.
3. 정답과 Gate 결과는 LLM 요청·응답 로그와 분리된 평가 파일에서만 결합한다. 이 파일에서 `binary_label`, `gate_forced`, `end_to_end`, 오류 여부 및 전이표를 계산한다.
4. `metrics.json`에는 지표·행 수·실패 수·latency 요약 등 수치만 기록하고 해석 문장은 넣지 않는다.
5. 기존 결과 파일이 있는 experiment ID로 재실행하지 않는다. prompt·모델·source budget·selection rule 중 하나라도 달라지면 새 experiment ID를 사용한다.

### G. 분리된 실행 환경 간 전달 계약 — 확정

1. Layer 1과 local LLM은 서로 다른 실행 환경에 둘 수 있다. Layer 1 환경에서 유보 flow를 선택하고 label-free JSONL bundle을 생성해 LLM 환경으로 전달한다.
2. 전송 JSONL의 각 행은 `input_index`와 `payload.flow_features`로 구성한다. `input_index`는 응답 결합용 운반 식별자이며 prompt에는 `payload.flow_features`만 넣는다.
3. 정답·Gate prediction·confidence·원래 `(day, id)`를 포함한 evaluation sidecar는 Layer 1 환경에 남기고 LLM 환경에 전달하지 않는다.
4. LLM 환경의 결과는 `input_index`를 포함해 반환하며, Layer 1 환경에서 evaluation sidecar와 결합한다.
5. 전송 manifest에는 입력 JSONL·schema·원본 예측 산출물의 SHA-256과 선택 조건·행 수를 기록해 환경 간 동일성을 검증한다.

## 3. 범위 밖으로 유지

1. 확률 보정과 calibration 기법.
2. TreeSHAP 및 예측 기여 특징 입력.
3. RAG, CTI, ATT&CK/CVE, evidence attribution.

## 4. 기록 규칙

1. 한 번의 논의에서는 하나의 맥락 묶음만 확정한다.
2. 확정 전 항목은 이 문서의 미결 목록에 남긴다.
3. 확정 실험으로 승격하려면 성공·실패·판정불가 기준을 포함한 별도 `experiments/EXP-XXX-*.md` 스펙이 필요하다.
