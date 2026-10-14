PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS events(
 event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, event_time TEXT NOT NULL,
 stage TEXT, event_type TEXT NOT NULL, actor_agent_id TEXT, target_agent_id TEXT,
 trace_id TEXT, span_id TEXT, parent_span_id TEXT,
 task_id TEXT, message_id TEXT, delegation_id TEXT, claim_id TEXT, action_id TEXT,
 protocol TEXT, protocol_version TEXT, outcome TEXT, error_class TEXT,
 payload_sha256 TEXT, attributes_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_events_run_time ON events(run_id,event_time);
CREATE INDEX IF NOT EXISTS idx_events_trace ON events(trace_id,span_id);
CREATE TABLE IF NOT EXISTS model_calls(
 call_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, agent_id TEXT,
 model_role TEXT NOT NULL, provider TEXT NOT NULL, model_id TEXT NOT NULL,
 prompt_template_id TEXT, prompt_template_version TEXT,
 request_ref TEXT NOT NULL, response_ref TEXT, parameters_json TEXT NOT NULL,
 usage_json TEXT NOT NULL DEFAULT '{}', provider_meta_json TEXT NOT NULL DEFAULT '{}',
 started_at TEXT NOT NULL, ended_at TEXT, attempt INTEGER NOT NULL DEFAULT 1,
 status TEXT NOT NULL, error_class TEXT
);
CREATE TABLE IF NOT EXISTS replay_index(
 run_id TEXT PRIMARY KEY, bundle_path TEXT NOT NULL, bundle_sha256 TEXT NOT NULL,
 completeness_json TEXT NOT NULL, created_at TEXT NOT NULL
);
