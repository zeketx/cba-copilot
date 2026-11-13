-- Login role for the hosted backend. Run as postgres. Do not put a password here.
-- Set the password in the dashboard, then point DATABASE_URL at this role.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles WHERE rolname = 'cba_copilot_app'
  ) THEN
    CREATE ROLE cba_copilot_app LOGIN
      NOSUPERUSER
      NOCREATEDB
      NOCREATEROLE
      NOREPLICATION;
  END IF;
END
$$;

ALTER ROLE cba_copilot_app WITH
  LOGIN
  NOSUPERUSER
  NOCREATEDB
  NOCREATEROLE
  NOREPLICATION
  BYPASSRLS;

GRANT CONNECT ON DATABASE postgres TO cba_copilot_app;
GRANT USAGE ON SCHEMA public TO cba_copilot_app;

GRANT SELECT ON TABLE source_documents, cba_chunks TO cba_copilot_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
  users,
  chat_threads,
  chat_messages,
  message_citations,
  access_requests
TO cba_copilot_app;
