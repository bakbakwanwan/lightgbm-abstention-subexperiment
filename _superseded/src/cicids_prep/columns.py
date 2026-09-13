"""원본 CICIDS2017 CSV의 실제 컬럼명 상수.

2026-09-10 data/CICIDS2017_improved_2022ver/*.csv 헤더를 직접 확인해 고정했다.
하드코딩된 문자열을 여러 모듈에 흩어놓지 않기 위해 이 파일에 모은다.
"""

from __future__ import annotations

# 원본 CSV 컬럼 (요일 파일 공통)
COL_ID = "id"
COL_FLOW_ID = "Flow ID"
COL_SRC_IP = "Src IP"
COL_SRC_PORT = "Src Port"
COL_DST_IP = "Dst IP"
COL_DST_PORT = "Dst Port"
COL_PROTOCOL = "Protocol"
COL_TIMESTAMP = "Timestamp"
COL_FLOW_DURATION = "Flow Duration"
COL_LABEL = "Label"
COL_ATTEMPTED_CATEGORY = "Attempted Category"

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

# 이 파이프라인이 새로 부여하는 컬럼
COL_DAY = "day"
COL_ROW_UID = "row_uid"
COL_ATTACK_LABEL = "attack_label"
COL_GROUP_ID = "group_id"
COL_SPLIT = "split"
COL_ORIGINAL_SPLIT = "original_split"
COL_LABEL_CONFLICT_FLAG = "label_conflict_flag"
COL_INVALID_NEG_DURATION_FLAG = "invalid_negative_duration_flag"
COL_REP_TIME = "rep_time"
COL_N_FLOWS_IN_GROUP = "n_flows_in_group"

# 5-tuple + timestamp: 완화기준 중복 검출 키 (stage1_briefing.md 1-2)
RELAXED_DUP_KEY = [COL_SRC_IP, COL_DST_IP, COL_SRC_PORT, COL_DST_PORT, COL_PROTOCOL, COL_TIMESTAMP]

# 요일 병합 후에만 존재하는, "완전일치" 비교에서 제외해야 하는 합성 컬럼
SYNTHETIC_COLS = [COL_DAY, COL_ID, COL_ROW_UID]
