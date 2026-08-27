-- ============================================================================
-- 06_analytics_telemetry.sql
-- Immutable Audit Events & Session Telemetry Schemas with 90d Partitioning
-- ============================================================================

CREATE TABLE IF NOT EXISTS `hr_analytics.audit_events_v1` (
  event_id STRING NOT NULL,
  correlation_id STRING NOT NULL,
  session_id STRING NOT NULL,
  timestamp TIMESTAMP NOT NULL,
  event_type STRING NOT NULL,          -- 'TOOL_CALL', 'WRITE_COMMIT', 'GUARDRAIL_BLOCK', 'AUTH_REVOCATION', 'SAGA_COMPENSATION'
  acting_principal STRING NOT NULL,    -- Authenticated IAM Principal
  derived_employee_id STRING NOT NULL, -- Server-side verified employee ID
  target_system STRING NOT NULL,       -- 'WORKWEEK', 'SERVICEIMMEDIATELY', 'BIGQUERY_KNOWLEDGE'
  tool_name STRING NOT NULL,
  request_payload_sanitized JSON,      -- Sensitive Data Protection (DLP) scrubbed
  response_status_code INT64,
  response_payload_sanitized JSON,
  confirmation_token_id STRING,
  payload_hash STRING,                 -- SHA-256 canonical hash
  guardrail_verdict STRING,            -- 'PASSED', 'BLOCKED_INJECTION', 'SPII_REDACTED', 'OUT_OF_SCOPE'
  execution_latency_ms INT64
)
PARTITION BY DATE(timestamp)
CLUSTER BY derived_employee_id, event_type, correlation_id
OPTIONS (partition_expiration_days = 90);

CREATE TABLE IF NOT EXISTS `hr_analytics.session_telemetry_v1` (
  session_id STRING NOT NULL,
  created_at TIMESTAMP NOT NULL,
  ended_at TIMESTAMP,
  acting_principal STRING NOT NULL,
  derived_employee_id STRING NOT NULL,
  total_turns INT64,
  total_input_tokens INT64,
  total_output_tokens INT64,
  final_status STRING,                 -- 'COMPLETED', 'PARTIAL_RECOVERED', 'HITL_ESCALATED', 'REVOKED'
  user_feedback_score INT64,           -- 1 (Thumb Down) or 5 (Thumb Up)
  user_feedback_comment STRING
)
PARTITION BY DATE(created_at)
CLUSTER BY session_id, final_status
OPTIONS (partition_expiration_days = 90);
