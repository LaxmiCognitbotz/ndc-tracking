-- Database Migration: SSO & RBAC Tables
-- Target Database: PostgreSQL (ndc_tracking / defaultdb)

CREATE TABLE IF NOT EXISTS ndc_user_access (
  id              SERIAL PRIMARY KEY,
  email           TEXT NOT NULL UNIQUE,
  name            TEXT,                         -- from Azure AD JWT claims
  role            TEXT NOT NULL DEFAULT 'admin',-- 'super_admin' or 'admin'
  status          TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
  approval_token  TEXT UNIQUE,                  -- one-time token for email links
  requested_at    TIMESTAMP DEFAULT NOW(),
  approved_at     TIMESTAMP,
  approved_by     TEXT,                         -- super_admin email who actioned
  reviewed_at     TIMESTAMP,
  reviewed_by     TEXT,
  notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_user_access_email ON ndc_user_access(email);
CREATE INDEX IF NOT EXISTS idx_user_access_token ON ndc_user_access(approval_token);

CREATE TABLE IF NOT EXISTS ndc_auth_audit_logs (
  id              SERIAL PRIMARY KEY,
  event_type      TEXT NOT NULL,
  -- 'LOGIN_SUCCESS', 'LOGIN_BLOCKED_PENDING', 'LOGIN_BLOCKED_REJECTED',
  -- 'FIRST_LOGIN_REQUEST_SENT', 'ACCESS_APPROVED', 'ACCESS_REJECTED', 'SESSION_REVOKED'
  email           TEXT,
  role            TEXT,
  performed_by    TEXT,                         -- who triggered this event (email or 'system')
  ip_address      TEXT,
  created_at      TIMESTAMP DEFAULT NOW(),
  notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_auth_audit_email ON ndc_auth_audit_logs(email);
CREATE INDEX IF NOT EXISTS idx_auth_audit_event ON ndc_auth_audit_logs(event_type);
