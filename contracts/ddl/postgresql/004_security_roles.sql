-- IoA-Bench PostgreSQL role contract.
-- Execute equivalent grants separately in each database as an admin.
-- Passwords/secrets MUST be managed externally; this file intentionally creates NO passwords.

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ioabench_control_app') THEN CREATE ROLE ioabench_control_app NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ioabench_worker') THEN CREATE ROLE ioabench_worker NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ioabench_oracle_reader') THEN CREATE ROLE ioabench_oracle_reader NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ioabench_oracle_loader') THEN CREATE ROLE ioabench_oracle_loader NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ioabench_sut_app') THEN CREATE ROLE ioabench_sut_app NOLOGIN; END IF;
END $$;

-- In ioabench_control:
-- GRANT CONNECT ON DATABASE ioabench_control TO ioabench_control_app, ioabench_worker;
-- GRANT USAGE ON SCHEMA ecp TO ioabench_control_app, ioabench_worker;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ecp TO ioabench_control_app;
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA ecp TO ioabench_worker;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ecp TO ioabench_control_app, ioabench_worker;

-- In ioabench_oracle:
-- GRANT CONNECT ON DATABASE ioabench_oracle TO ioabench_oracle_reader, ioabench_oracle_loader;
-- GRANT USAGE ON SCHEMA oracle TO ioabench_oracle_reader, ioabench_oracle_loader;
-- GRANT SELECT ON ALL TABLES IN SCHEMA oracle TO ioabench_oracle_reader;
-- GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA oracle TO ioabench_oracle_loader;
-- SUT roles MUST NOT receive CONNECT to ioabench_oracle.
-- REVOKE CONNECT ON DATABASE ioabench_oracle FROM PUBLIC, ioabench_sut_app;

-- In ioabench_sut:
-- GRANT CONNECT ON DATABASE ioabench_sut TO ioabench_sut_app, ioabench_worker;
-- GRANT USAGE ON SCHEMA sut TO ioabench_sut_app, ioabench_worker;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA sut TO ioabench_sut_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA sut TO ioabench_worker;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA sut TO ioabench_sut_app, ioabench_worker;
