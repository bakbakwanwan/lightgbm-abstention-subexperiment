# E9 JSON LLM 검증 — 결정·구현·인계 기록

> 상태: 2026-09-18 기준 설계와 공용 파이프라인 구현 완료, 100-flow 전달 bundle 생성 완료, 별도 LLM 환경의 Ollama 실행 전. 이 문서는 확정 실험 스펙이 아니다.
>
> 목적: 첫 Layer 2 실험에 필요한 결정을 한꺼번에 확정하지 않고, 맥락상 함께 결정할 수 있는 묶음 단위로 합의·기록한다. 현행 Layer 1의 확정 결정과 충돌할 경우 `docs/CURRENT_DECISIONS.md`가 우선한다.

## 1. 이번 기록에서 확정한 범위

1. 첫 Layer 2 실험은 **RAG 없이**, 유보된 flow의 구조화된 JSON 직렬화만 local LLM에 제공하는 LLM-only 검증이다.
2. CTI corpus, MITRE ATT&CK, CVE 및 retrieval은 이 첫 실험의 범위에 넣지 않는다. 이후 별도 실험에서 검토한다.
3. 첫 실험의 주 비교는 같은 유보 flow에 대한 Layer 1 forced decision과 LLM-only JSON verification이다.
4. 실제 운영의 유보 처리량은 가용 `verification_budget`과 당시 confidence 분포에 따라 동적으로 변할 수 있다.
5. 실험의 1%·2%·5%·10% 유보 집합은 운영 유보율을 고정하는 정책이 아니라, 서로 다른 처리 예산 조건을 비교하기 위한 재현 가능한 평가 snapshot이다.
6. 각 LLM 실행 결과에는 그 실행에서 실제 사용한 유보 행 식별자와 선택 규칙을 남긴다. 이를 통해 prompt·모델 변경 시 같은 flow 집합에서 비교한다.

## 2. 확정된 설계 계약

### A. Layer 1 → Layer 2 입력 계약 — 확정

1. 기본 LLM 입력에는 Layer 1의 `p_attack`, `confidence`, `predicted_label`을 넣지 않는다. 이 값들은 평가 및 fallback 전용으로 보존한다.
2. 실제 운영의 유보 행은 동적으로 선택한다. 각 완료된 LLM 실행은 재현성을 위해 실제 사용한 `(day, id)` 목록, budget, threshold 및 source prediction artifact hash를 결과 manifest에 남긴다.
3. 기본 LLM 입력의 관측값은 Layer 1 whitelist의 59개 피처로 한정한다. `day`, `id`, `Label`, `binary_label`, `is_error`, `Attempted Category`는 평가·추적 전용이며 prompt JSON에 넣지 않는다.
4. `abstained`는 모든 E9 입력에서 상수 `true`이므로 prompt JSON에 넣지 않는다. 선택 사실과 관련 메타데이터는 실행 manifest에만 기록한다.
5. Layer 2 전용 schema snapshot은 `configs/llm/e9_input_feature_schema.json`, prompt template은 `configs/llm/e9_prompt_v1.json`으로 구현했으며 export 때 transfer bundle 안으로 복제한다.

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

2. `INDETERMINATE`, parsing failure, timeout의 처리 및 fallback 규칙은 다음과 같이 확정한다.
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
6. 59-feature schema snapshot은 별도 JSON 파일로 LLM 환경에 전달한다. manifest에는 feature 목록을 복제하지 않고 schema 파일의 상대 경로·version·SHA-256만 기록한다.

## 3. 범위 밖으로 유지

1. 확률 보정과 calibration 기법.
2. TreeSHAP 및 예측 기여 특징 입력.
3. RAG, CTI, ATT&CK/CVE, evidence attribution.

## 4. 기록 규칙

1. 한 번의 논의에서는 하나의 맥락 묶음만 확정한다.
2. 확정 전 항목은 이 문서의 미결 목록에 남긴다.
3. 확정 실험으로 승격하려면 성공·실패·판정불가 기준을 포함한 별도 `experiments/EXP-XXX-*.md` 스펙이 필요하다.

## 5. 구현 계획

### 5-1. 범위와 경계

1. 공통 Layer 2 파이프라인은 과학적 실험 ID를 부여하지 않는 재사용 구현으로 둔다.
2. Layer 1 환경은 유보 flow 선택·직렬화·평가를 담당하고, LLM 환경은 label-free 입력 검증·추론·응답 생성을 담당한다.
3. 첫 구현 범위에는 RAG·CTI·ATT&CK/CVE·TreeSHAP·확률 보정을 포함하지 않는다.
4. full E9는 pilot 기술 검증 이후 별도 확정 실험 스펙으로 작성하기 전에는 실행하지 않는다.

### 5-2. 현재 구현 완료

1. Layer 2 전용 59-feature schema snapshot.
2. EXP-007 예측 원자료와 외부 `confidence_threshold`에서 유보 행을 선택하는 loader.
3. 선택 행을 원본 CSV와 `(day, id)`로 재결합하고 label-free JSON으로 변환하는 serializer.
4. LLM 환경용 `llm_inputs.jsonl`, Layer 1 환경용 `evaluation_sidecar.jsonl`, 무결성 manifest 생성.
5. 실제 EXP-007 1% 유보 집합에서 hash 기반 100행 export 검증.
6. 관련 단위 테스트 및 기존 테스트 통과.
7. 전송 bundle validator와 machine-readable validation artifact.
8. `e9-v1` prompt asset, local Ollama HTTP runner, strict response parser, partial-run 보존 및 run manifest/status 기록.
9. Layer 1 evaluator, fallback·전이표·이진 지표·latency 산출 및 평가 연결 manifest.
10. 실제 100행 export bundle의 12개 validation check 통과. local Ollama가 없는 현재 구현 환경에서는 1-flow live model smoke test를 실행하지 않았으며 별도 LLM 환경에서 수행해야 한다.
11. manifest의 전송 허용 목록만 ZIP으로 묶는 transfer packager. 로컬 evaluation sidecar는 제외하고 ZIP SHA-256과 member 목록을 별도 package manifest에 기록한다.

### 5-3. WP1 — 전송 bundle 검증기

**확정된 구현**

1. LLM 호출 전에 manifest와 전송 파일을 검증한다.
2. 파일 SHA-256, JSONL 행 수, `input_index` 유일성·연속성, 각 payload의 feature 수를 검사한다.
3. prompt 금지 필드가 발견되거나 JSON parsing이 실패하면 전체 실행을 시작하지 않는다.
4. 검증 결과를 machine-readable 파일로 남기고 검사별 pass/fail을 기록한다.
5. feature schema snapshot은 별도 JSON 파일로 전송하고, manifest는 상대 경로·version·SHA-256으로 그 파일을 참조한다. feature 목록은 manifest에 복제하지 않는다.
6. 검증 결과 파일명은 `bundle_validation.json`, schema version은 `e9-bundle-validation-v1`으로 한다.
7. 최상위에는 `validation_schema_version`, `passed`, `validated_at`, `manifest_sha256`, `checks`, `summary`를 둔다. 각 check는 `passed`, `observed`, `expected`, `reason`을 기록한다.
8. 필수 검사는 manifest parsing, feature schema SHA-256, input JSONL SHA-256, 행 수, `input_index` 유일성·연속성, feature 수·목록·순서, 금지 필드 부재다.
9. 모든 필수 검사가 통과해야 최상위 `passed=true`다. 실패해도 가능한 범위에서 결과 파일을 생성하며, 하나라도 실패하면 Ollama runner를 시작하지 않는다.
10. 검증 결과에는 절대경로와 실제 flow 값을 넣지 않고 상대경로·hash·count만 기록한다.

**완료 조건**

1. 정상 bundle 통과 테스트.
2. SHA 변조, 행 누락, 중복 index, feature 누락·추가, 금지 필드 삽입 각각의 실패 테스트.

### 5-4. WP2 — Prompt 자산 고정

**확정된 구현**

1. D절의 `e9-v1` system/user prompt를 별도 파일로 둔다.
2. runner는 prompt 파일을 읽고 `payload.flow_features`만 user 입력 경계 안에 삽입한다.
3. prompt 전문 SHA-256을 실행 manifest에 기록한다.
4. prompt 자산은 `e9_prompt_v1.json` 하나로 두며 `prompt_version`, `system_prompt`, `user_prompt_template`, `flow_features_placeholder`를 저장한다.
5. placeholder는 `{{FLOW_FEATURES_JSON}}` 하나만 허용하고 정확히 한 번 존재해야 한다. 범용 template engine을 사용하지 않고 runner가 이 문자열만 치환한다.
6. prompt 파일은 runner 코드에 내장하지 않고 transfer bundle에 포함한다. manifest에는 본문을 복제하지 않고 상대 경로·version·SHA-256만 기록한다.
7. bundle 검증기는 prompt JSON parsing, 필수 필드, version, placeholder 1개 및 SHA-256을 검사한다.
8. runner는 `system_prompt`와 렌더링한 user prompt를 Ollama에 별도 role로 전달한다.

**완료 조건**

1. 렌더링 결과에 Layer 1 판단·정답·운반용 `input_index`가 포함되지 않는 테스트.
2. 같은 payload와 prompt version이 byte-identical prompt를 생성하는 테스트.

### 5-5. WP3 — Ollama runner 및 strict parser

**확정된 구현**

1. bundle 검증 성공 후 `input_index` 순서로 요청하며 concurrency는 1로 유지한다.
2. C절의 모델·generation 설정을 명시적으로 전달한다.
3. 요청당 시도는 한 번이며 timeout 후 자동 재시도하지 않는다.
4. raw response, latency, parsed decision, `INDETERMINATE` 여부, 실패 유형을 `input_index`와 함께 JSONL로 저장한다.
5. `decision` 하나만 가진 JSON object와 세 허용값만 정상 응답으로 인정한다.
6. 부분 실행 결과를 기존 결과 위에 덮어쓰지 않는다.
7. Ollama는 local HTTP `POST http://127.0.0.1:11434/api/chat`으로 호출하며 CLI를 사용하지 않는다.
8. system/user message를 분리하고 `stream=false`, `keep_alive=5m`으로 요청한다. C절의 option과 Modelfile 고정값을 명시적으로 전달한다.
9. `format`에는 `decision` 하나만 허용하고 `BENIGN`·`ATTACK`·`INDETERMINATE` enum 및 `additionalProperties=false`를 지정한 JSON Schema를 전달한다.
10. API structured output과 prompt의 JSON 지시를 함께 사용하되 strict parser를 독립적으로 유지한다.
11. Ollama 응답의 `done`, `done_reason`, duration, prompt/eval count와 `message.content` 원문을 보존한다.
12. 응답 파일명은 `llm_responses.jsonl`로 하며 입력 한 행당 `input_index`가 같은 응답 한 행을 기록한다.
13. 응답 행에는 `run_id`, `input_index`, `status`, `parsed_decision`, `raw_content`, `generation_failure`, `wall_latency_seconds`, `http_status`, `ollama`를 둔다. `ollama`에는 model·created_at·done·done_reason·duration 원값·prompt/eval count를 둔다.
14. `status`는 `completed`·`indeterminate`·`generation_failure` 중 하나다. 앞의 두 상태에서는 failure가 `null`, 실패 상태에서는 decision이 `null`이고 failure object가 필수다.
15. `generation_failure.code`는 `timeout`, `connection_error`, `http_error`, `ollama_error`, `api_response_invalid`, `generation_incomplete`, `empty_response`, `decision_json_invalid`, `decision_schema_invalid`로 제한한다.
16. HTTP status와 model content를 받은 경우 실패하더라도 보존한다. 기록 불가능한 Ollama 필드는 `null`로 두며 failure detail에는 비밀정보·절대경로·전체 prompt를 넣지 않는다.
17. 예측하지 못한 runner 내부 예외는 행 단위 실패로 숨기지 않고 전체 run을 중단한다.
18. 실행 중에는 응답을 `llm_responses.partial.jsonl`에 요청 완료 건마다 즉시 기록하고 flush한다.
19. timeout·`generation_incomplete`·`empty_response`·`decision_json_invalid`·`decision_schema_invalid`는 해당 행의 `generation_failure`로 기록한 뒤 다음 입력을 계속 처리한다.
20. `connection_error`·`http_error`·`ollama_error`·`api_response_invalid`는 현재 행을 기록한 뒤 전체 run을 중단한다. 예측하지 못한 runner 내부 예외도 즉시 중단한다.
21. `runner_status.json`은 `status_schema_version=e9-runner-status-v1`, `run_id`, `run_status`, `expected_rows`, `written_rows`, `last_input_index`, `started_at`, `finished_at`, `reason`을 기록한다. `run_status`는 `running`·`completed`·`incomplete` 중 하나다.
22. 모든 입력 `input_index`에 정확히 하나의 응답 행이 있을 때만 `completed`로 인정한다. 개별 `generation_failure`가 있어도 행 대응이 완전하면 run 자체는 완료다.
23. 정상 완료 시에만 partial 파일을 `llm_responses.jsonl`로 확정한다. 중단 시 partial 파일과 `run_status=incomplete`인 상태 파일을 보존하며 공식 평가 입력으로 사용하지 않는다.
24. 중단된 run은 삭제·덮어쓰기·제자리 재개하지 않는다. 100-flow pilot은 새 run ID에서 `input_index=0`부터 다시 실행한다.
25. full E9의 부분 재개 정책은 pilot 이후 대상 규모와 실행 시간을 근거로 별도 결정한다.
26. LLM 환경은 bundle 검증 통과 후 첫 요청 전에 불변 실행 조건 파일 `run_manifest.json`을 생성한다. 진행 상태와 결과 수치는 이 파일에 쓰지 않고 각각 `runner_status.json`, response JSONL, 평가 산출물에 분리한다.
27. `run_manifest.json`의 schema version은 `e9-run-manifest-v1`이며 최상위에는 `run_manifest_schema_version`, `run_id`, `created_at`, `input_bundle`, `runner`, `ollama`, `generation`, `environment`를 둔다.
28. `input_bundle`에는 원본 bundle manifest SHA-256, input 상대경로·SHA-256·행 수, feature schema 상대경로·version·SHA-256, prompt 상대경로·version·SHA-256을 기록한다. 원본 manifest·prompt 본문·feature 목록은 복제하지 않는다.
29. `runner`에는 `runner_version=e9-ollama-runner-v1`, git commit, dirty worktree 여부, Python version, `uv.lock` SHA-256을 기록한다. `uv.lock`이 없으면 lock hash는 `null`이다.
30. `ollama`에는 version, local API endpoint, model tag·ID, base blob SHA-256, architecture, parameter count, quantization, model context length를 기록한다.
31. `generation`에는 `num_ctx`, `temperature`, `top_p`, `num_predict`, `seed`, `concurrency`, `timeout_seconds`, `stream`, `keep_alive`, `repeat_penalty`, `penalize_newline`, stop token 목록을 기록한다.
32. `environment`에는 확인 가능한 OS·OS version·architecture·CPU·memory·GPU·GPU memory를 기록한다. 확인할 수 없는 값은 추정하지 않고 `null`로 두며 수집 실패만으로 실행을 막지 않는다.
33. SHA-256은 파일 원본 byte 기준 소문자 16진수로 계산한다. manifest에는 인증정보·사용자명·hostname·절대경로를 기록하지 않으며 생성 후 실행 중 수정하지 않는다.
34. 반환 bundle에는 `run_manifest.json`, `runner_status.json`, 그리고 완료 시 `llm_responses.jsonl` 또는 중단 시 `llm_responses.partial.jsonl`을 포함한다.

**완료 조건**

1. fake Ollama 응답을 이용한 정상·`INDETERMINATE`·timeout·연결 실패·schema 위반 테스트.
2. local Ollama 1-flow live smoke test.
3. 입력과 응답의 `input_index`가 정확히 일대일인 검증.

### 5-6. WP4 — Layer 1 환경 evaluator

**확정된 구현**

1. 반환 응답과 로컬 evaluation sidecar를 `input_index`로 일대일 결합한다.
2. `INDETERMINATE`와 `generation_failure`에는 Gate forced decision을 적용한다.
3. E절의 세 결과와 전이표·이진 지표·운영 지표를 산출한다.
4. 수치 artifact와 해석을 분리하며 기존 결과 디렉터리를 덮어쓰지 않는다.
5. evaluator 입력은 export `manifest.json`, `local/evaluation_sidecar.jsonl`, 반환된 `run_manifest.json`, `runner_status.json`, `llm_responses.jsonl`이다. partial response가 있거나 `run_status != completed`이면 공식 평가를 거부한다.
6. 평가 전에 export manifest와 sidecar hash, export manifest와 run manifest의 bundle manifest hash, 모든 `run_id`, 행 수, `input_index` 유일성·연속성 및 sidecar-response 일대일 대응을 검증한다. response status·decision·failure code도 확정 schema와 일치해야 한다.
7. 행 단위 평가 파일명은 `evaluation_records.jsonl`로 한다. 각 행에는 `input_index`, `day`, `id`, `binary_label`, `gate_predicted_label`, `llm_decision`, `llm_predicted_label`, `generation_failure_code`, `fallback_applied`, `fallback_reason`, `final_predicted_label`, `gate_is_error`, `final_is_error`, `transition`, `llm_override`, `wall_latency_seconds`를 둔다.
8. LLM decision은 `BENIGN=0`, `ATTACK=1`, `INDETERMINATE=null`, generation failure=`null`로 변환한다. 유효한 이진 LLM 판정은 최종 판정으로 쓰고, 나머지는 Gate 판정으로 fallback한다.
9. `fallback_reason`은 `indeterminate`·`generation_failure`·`null` 중 하나다. `llm_override=true`는 유효한 LLM 이진 판정이 Gate 판정과 다를 때만 적용하며 fallback은 override가 아니다.
10. `transition`은 `gate_correct_final_correct`, `gate_correct_final_error`, `gate_error_final_correct`, `gate_error_final_error` 중 하나다.
11. 평가 연결 파일은 `evaluation_manifest.json`, schema version은 `e9-evaluation-v1`으로 한다. 평가 시각·`run_id`와 export manifest, sidecar, run manifest, runner status, response, evaluation records 각각의 SHA-256을 기록한다.
12. `metrics.json`은 수치만 담으며 최상위 묶음은 `counts`, `rates`, `gate_forced`, `llm_valid_only`, `end_to_end`, `transitions`, `latency_seconds`로 한다.
13. `counts`에는 전체 행, 유효 LLM 이진 판정, `INDETERMINATE`, generation failure, fallback, override, timeout, schema-valid 응답 수를 둔다. `rates`에는 각각 필요한 rate를 둔다.
14. 세 평가 결과에는 대상 행 수, TP·TN·FP·FN, error count·rate, precision·recall·F1·FPR·FNR을 둔다. `llm_valid_only`는 유효한 `BENIGN`·`ATTACK` 행만 분모로 하므로 전체 결과와 직접 비교하지 않는다.
15. `transitions`에는 네 전이별 행 수를, `latency_seconds`에는 non-null latency 전체의 표본 수·p50·p95를 기록한다. 분모가 0이라 정의할 수 없는 지표는 0으로 치환하지 않고 `null`로 기록한다.

**미결**

1. 없음.

16. pilot `run_id`는 `e9-pilot-YYYYMMDDTHHMMSSZ-xxxxxxxx` 형식으로 Layer 1 export 전에 생성한다. 시각은 UTC, suffix는 UUID에서 얻은 소문자 16진수 8자리이며 정규식은 `^e9-pilot-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$`다.
17. source experiment·method·budget은 `run_id`에 넣지 않고 manifest에 기록한다. 같은 조건의 재실행도 새 `run_id`를 사용하며 LLM 환경은 전달받은 ID를 변경하지 않는다.
18. Layer 1 기준 pilot 저장 위치는 `results/pilots/e9-json-llm/<run_id>/`로 한다. 그 아래 `export/transfer`, `export/local`, `returned`, `evaluation`을 분리한다.
19. `export/transfer`에는 LLM input·feature schema·prompt asset을, `export/local`에는 evaluation sidecar를 둔다. `returned`에는 bundle validation·run manifest·runner status·완료 또는 partial response를 두며 `evaluation`에는 evaluation manifest·records·metrics를 둔다.
20. LLM 환경의 실제 작업 디렉터리와 입력·출력 로컬 경로는 실험 환경에 따라 설정할 수 있어야 하며 코드에 고정하지 않는다. 두 환경의 동일성은 절대경로나 디렉터리 이름이 아니라 `run_id`와 파일 SHA-256으로 검증한다.
21. 중단 run에는 partial response를 보존하고 evaluation을 생성하지 않는다. 기존 run 디렉터리나 반환 파일이 있으면 덮어쓰지 않고 실패시키며 새 `run_id`로 재실행한다.
22. pilot은 공식 `EXP-NNN` 결과와 분리한다. full E9는 별도 확정 스펙 작성 후 `results/EXP-NNN/` 구조를 사용한다.
23. pilot source의 과학적 식별 정보와 실제 파일 위치를 분리한다. source experiment·method·budget은 manifest/config에 기록하고, prediction artifact 경로는 실행 환경별 설정값으로 주입하며 특정 `results/EXP-*` 경로에 고정하지 않는다.
24. 별도 실험 환경의 prediction artifact 배치 위치는 `data/predictions/group_seed42.parquet`로 한다. loader는 이 경로를 기본값으로 가정하지 않고 명시적으로 전달받아야 한다.
25. `data/predictions/README.md`에는 해당 디렉터리가 로컬 artifact staging 영역이라는 점, 파일명의 의미를 출처로 신뢰하지 않는다는 점, source metadata와 SHA-256을 manifest/config에서 확인해야 한다는 운영 안내를 둔다.

**완료 조건**

1. 정상·fallback·누락·중복 응답 결합 테스트.
2. confusion counts와 파생 지표의 독립 재계산 일치 테스트.

### 5-7. WP5 — 100-flow pilot

**확정된 구현**

1. 대상 유보 집합에서 `(day, id)` 안정 hash 순 첫 100행을 사용한다.
2. C절의 기술 성공 기준만 판정하고 분류 성능 우위를 주장하지 않는다.
3. 두 환경에서 입력·응답·manifest hash와 행 수의 일치를 확인한다.
4. source experiment는 `EXP-007`, method는 D-004 주 분석인 `group_seed42`, target abstention rate는 `0.01`로 한다.
5. prediction artifact의 실제 경로는 실행 환경별 설정값이다. 별도 환경에서는 `data/predictions/group_seed42.parquet`에 배치하되 loader 호출 시 그 경로를 명시적으로 전달한다.
6. source experiment·method·target abstention rate·실제로 해석된 confidence threshold와 prediction SHA-256을 manifest에 기록한다. 경로나 파일명만으로 source를 판정하지 않는다.
7. `row_random_seed42`는 낙관적 민감도 분석이므로 기본 pilot source로 사용하지 않는다.

**완료 조건**

1. schema valid rate, timeout rate, OOM/crash 판정 완료.
2. latency p50/p95와 parsing failure rate 기록.
3. 원자료에서 pilot 결과까지 `input_index` 추적 가능.

### 5-8. WP6 — Full E9 확정 스펙

pilot 통과 후에만 다음을 확정한다.

1. 정식 `EXP-NNN` ID와 실험 질문.
2. 실행할 abstention budget과 전체 대상 flow.
3. 과학적 성공·실패·판정불가 기준.
4. 비교 지표의 주·보조 구분과 결과 해석 한계.
5. 실행 자원·시간 상한과 최종 artifact 계약.

### 5-9. 미결 사항 결정 순서

1. pilot 통과 후 full E9 스펙.

## 6. 2026-09-18 실제 생성 상태

### 6-1. 구현 상태

1. 구현 위치는 `src/abstention_experiment/`, 실행 진입점은 `scripts/`, 고정 자산은 `configs/llm/`, 테스트는 `tests/abstention_experiment/`다.
2. 구현된 구성요소는 abstained-flow loader·serializer, transfer bundle validator, prompt renderer, Ollama HTTP runner, strict response parser, transfer packager, Layer 1 evaluator다.
3. 자동 테스트는 31개가 통과했다. 실제 Ollama가 없는 Layer 1 구현 환경에서는 live model 호출을 실행하지 않았다.
4. 실제 EXP-007 prediction과 원본 요일별 CSV로 100행을 재결합·직렬화했으며 pre-transfer 검사 12개가 모두 통과했다.

### 6-2. 생성된 pilot bundle

1. `run_id`: `e9-pilot-20260918T051044Z-fc63bbad`.
2. source: `EXP-007`, `group_seed42`, target abstention rate `0.01`, `confidence_threshold=0.9993377811093735`.
3. source test는 482,382행, threshold 적용 전 pilot 모집단인 유보 집합은 4,816행, stable hash 표본은 100행이다.
4. staging prediction은 `data/predictions/group_seed42.parquet`이며 SHA-256은 `e27f1a5edbd305605923685fe4f9203f9ed1f6c269b6f0169cf2d4d1634898dc`다.
5. Layer 1 보존 root는 `results/pilots/e9-json-llm/e9-pilot-20260918T051044Z-fc63bbad/`다.
6. LLM 환경에 전달할 파일은 그 root의 `llm_transfer_bundle.zip`과 `llm_transfer_bundle.manifest.json`이다.
7. ZIP SHA-256은 `fa237e91494020eb975ae002696f74f7b852cd344322afbd283389fb383c4e1c`다.
8. ZIP에는 `manifest.json`, `transfer/llm_inputs.jsonl`, `transfer/e9_input_feature_schema.json`, `transfer/e9_prompt_v1.json`만 들어 있다.
9. `export/local/evaluation_sidecar.jsonl`은 ZIP에서 제외되어 Layer 1 환경에만 남아 있다.
10. ZIP을 다시 압축 해제한 독립 디렉터리에서도 validation 12개가 모두 통과했다.
11. 이 bundle은 `git_commit=c3c3b2487b6ed6394e044647325e8ef4cd7059f9`, `working_tree_dirty_at_creation=true`로 기록됐다. 따라서 현재 bundle은 기술 pilot 전달용으로 사용하되, 정식 실험 artifact로 승격하지 않는다.

## 7. 별도 LLM 환경 인계 구조

### 7-1. 환경 역할 분리

1. Layer 2 환경은 원래 Layer 1 저장소와 혼동되지 않도록 별도 root를 사용한다.
2. 권장 root 이름은 Windows에서 `C:\Experiments\RUSExperiment-Layer2-E9-Pilot\`, Linux에서 `~/experiments/RUSExperiment-Layer2-E9-Pilot/`이다.
3. 실제 root·입력·출력 경로는 환경별로 설정하며 코드에 고정하지 않는다.
4. 환경 간 동일성은 절대경로가 아니라 `run_id`와 SHA-256으로 판단한다.

### 7-2. 권장 디렉터리

```text
RUSExperiment-Layer2-E9-Pilot/
├── ENVIRONMENT_ROLE.md
├── app/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── scripts/
│   └── src/
├── context/
├── incoming/
│   └── <run_id>/
│       ├── llm_transfer_bundle.zip
│       ├── llm_transfer_bundle.manifest.json
│       └── extracted/
├── outputs/
│   └── <run_id>/
└── logs/
```

1. `incoming/`은 전달 원본이므로 수정하지 않는다.
2. `outputs/<run_id>/`에 `bundle_validation.json`, `run_manifest.json`, `runner_status.json`, 완료 시 `llm_responses.jsonl` 또는 중단 시 `llm_responses.partial.jsonl`을 생성한다.
3. `context/`에는 `AGENTS.md`, `RESEARCH_PLAN_E9_E10.md`, 이 문서, `docs/CURRENT_DECISIONS.md`, `docs/glossary.md`를 둔다.
4. `evaluation_sidecar.jsonl`, prediction parquet, EXP-007 metrics, 원본 CICIDS2017 CSV는 Layer 2 환경에 전달하지 않는다.

## 8. 다음 실행 순서

1. `llm_transfer_bundle.zip`과 package manifest를 별도 LLM 환경의 `incoming/<run_id>/`으로 복사한다.
2. package manifest의 ZIP SHA-256과 실제 ZIP SHA-256을 비교한다.
3. ZIP을 `incoming/<run_id>/extracted/`에 풀고 `scripts/validate_e9_bundle.py`로 다시 검증한다.
4. 검증이 통과한 동일 extracted bundle을 `scripts/run_e9_ollama.py`에 전달한다.
5. `outputs/<run_id>/` 전체를 Layer 1 환경의 `results/pilots/e9-json-llm/<run_id>/returned/`로 돌려준다.
6. Layer 1 환경에서 `scripts/evaluate_e9_run.py`로 local sidecar와 반환 응답을 결합한다.
7. `metrics.json`에서 schema valid rate ≥95%, timeout rate ≤5%, OOM/crash 0을 확인한다.
8. pilot 통과 후에만 full E9의 정식 실험 ID·대상 budget·성공 기준을 별도 스펙으로 확정한다.

## 9. 현재 남은 일

1. 별도 LLM 환경에 app·context·transfer package를 배치한다.
2. 실제 Ollama metadata 검증과 1-flow live smoke test를 수행한다.
3. 같은 `run_id`의 100-flow pilot을 실행하고 반환 artifact를 Layer 1 환경으로 가져온다.
4. evaluator를 실행해 기술 성공 기준을 판정한다.
5. 구현 변경을 commit·push할지 결정한다. 정식 실험을 시작하기 전에는 clean commit에서 bundle을 새 `run_id`로 다시 생성한다.
