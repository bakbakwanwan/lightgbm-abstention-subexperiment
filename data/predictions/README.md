# Prediction artifact staging

이 디렉터리는 서로 다른 실험 환경 사이에서 Layer 1 prediction artifact를 배치하는 로컬 staging 영역이다.

pilot에서 사용할 prediction 파일은 `group_seed42.parquet`라는 이름으로 이 디렉터리에 배치한다. 파일 자체는 Git으로 추적하지 않는다.

파일명과 로컬 경로는 artifact의 출처를 증명하지 않는다. loader에는 prediction 경로를 명시적으로 전달하고, source experiment·method·abstention budget과 confidence threshold는 실행 config 및 manifest에서 확인해야 한다. 실행 전에는 prediction 파일의 SHA-256을 계산하여 manifest에 기록한다.

현재 E9 pilot의 확정 계약과 필요한 필드는 [`tasks/e9_json_llm_verification_decisions.md`](../../tasks/e9_json_llm_verification_decisions.md)를 따른다.
