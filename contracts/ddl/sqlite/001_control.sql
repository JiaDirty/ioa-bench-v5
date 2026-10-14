PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS experiments(
  experiment_id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL,
  benchmark_version TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs(
  run_id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
  test_id TEXT NOT NULL, case_id TEXT NOT NULL, condition_name TEXT NOT NULL,
  repetition INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL,
  manifest_json TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
  started_at TEXT, ended_at TEXT,
  UNIQUE(experiment_id,test_id,case_id,condition_name,repetition)
);
CREATE TABLE IF NOT EXISTS run_transitions(
  transition_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES runs(run_id),
  from_state TEXT, to_state TEXT NOT NULL, occurred_at TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
  detail_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS scores(
  score_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES runs(run_id),
  metric_name TEXT NOT NULL, metric_version TEXT NOT NULL, value REAL,
  numerator REAL, denominator REAL, unit TEXT, direction TEXT,
  evidence_json TEXT NOT NULL DEFAULT '[]', details_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE(run_id,metric_name,metric_version)
);
CREATE TABLE IF NOT EXISTS artifacts(
  artifact_id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(run_id), kind TEXT NOT NULL,
  path TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS generation_jobs(
  job_id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, dataset_version TEXT NOT NULL,
  test_id TEXT NOT NULL, status TEXT NOT NULL, target_json TEXT NOT NULL,
  config_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
