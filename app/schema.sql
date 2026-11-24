CREATE TABLE IF NOT EXISTS users (
 id BIGINT PRIMARY KEY AUTO_INCREMENT,
 username VARCHAR(80) NOT NULL UNIQUE,
 password_hash VARCHAR(255) NOT NULL,
 role ENUM('admin','operator','viewer') NOT NULL DEFAULT 'viewer',
 disabled TINYINT(1) NOT NULL DEFAULT 0,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash CHAR(64) PRIMARY KEY,
 user_id BIGINT NOT NULL,
 csrf_token VARCHAR(80) NOT NULL,
 expires_at DATETIME(6) NOT NULL,
 FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS login_attempts (
 identity_hash CHAR(64) PRIMARY KEY,
 attempts INT NOT NULL DEFAULT 0,
 window_start DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
);
CREATE TABLE IF NOT EXISTS devices (
 id BIGINT PRIMARY KEY AUTO_INCREMENT,
 name VARCHAR(80) NOT NULL,
 address VARCHAR(45) NOT NULL,
 environment ENUM('demo','real') NOT NULL,
 kind ENUM('server','router','switch','storage') NOT NULL DEFAULT 'server',
 site VARCHAR(100) NOT NULL,
 services_json LONGTEXT NOT NULL,
 notes TEXT NOT NULL,
 parent_id BIGINT NULL,
 exporter_port INT NOT NULL DEFAULT 9100,
 metric_key VARCHAR(80) NOT NULL DEFAULT '',
 status ENUM('unknown','up','warning','down') NOT NULL DEFAULT 'unknown',
 auto_approve TINYINT(1) NOT NULL DEFAULT 0,
 last_checked_at DATETIME(6) NULL,
 latency_ms DOUBLE NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
 archived_at DATETIME(6) NULL,
 UNIQUE KEY device_environment_name (environment,name),
 FOREIGN KEY (parent_id) REFERENCES devices(id)
);
CREATE TABLE IF NOT EXISTS checks (
 id BIGINT PRIMARY KEY AUTO_INCREMENT,
 device_id BIGINT NOT NULL,
 environment ENUM('demo','real') NOT NULL,
 status VARCHAR(20) NOT NULL,
 results_json LONGTEXT NOT NULL,
 duration_ms DOUBLE NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 FOREIGN KEY (device_id) REFERENCES devices(id),
 INDEX checks_device_time (device_id,created_at)
);
CREATE TABLE IF NOT EXISTS jobs (
 id BIGINT PRIMARY KEY AUTO_INCREMENT,
 device_id BIGINT NOT NULL,
 environment ENUM('demo','real') NOT NULL,
 action VARCHAR(40) NOT NULL,
 service VARCHAR(40) NULL,
 status ENUM('awaiting_approval','queued','running','succeeded','failed','cancelled') NOT NULL,
 requested_by BIGINT NOT NULL,
 approved_by BIGINT NULL,
 approved_at DATETIME(6) NULL,
 device_updated_at DATETIME(6) NOT NULL,
 logs TEXT NOT NULL,
 result_json LONGTEXT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 started_at DATETIME(6) NULL,
 finished_at DATETIME(6) NULL,
 FOREIGN KEY (device_id) REFERENCES devices(id),
 FOREIGN KEY (requested_by) REFERENCES users(id),
 FOREIGN KEY (approved_by) REFERENCES users(id),
 INDEX jobs_status_time (status,created_at)
);
CREATE TABLE IF NOT EXISTS incidents (
 id BIGINT PRIMARY KEY AUTO_INCREMENT,
 device_id BIGINT NOT NULL,
 environment ENUM('demo','real') NOT NULL,
 title VARCHAR(160) NOT NULL,
 severity ENUM('info','warning','critical') NOT NULL,
 status ENUM('open','acknowledged','resolved') NOT NULL DEFAULT 'open',
 details TEXT NOT NULL,
 fingerprint VARCHAR(120) NULL UNIQUE,
 assigned_to BIGINT NULL,
 resolution_note TEXT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
 resolved_at DATETIME(6) NULL,
 FOREIGN KEY (device_id) REFERENCES devices(id),
 FOREIGN KEY (assigned_to) REFERENCES users(id),
 INDEX incidents_environment_status (environment,status)
);
CREATE TABLE IF NOT EXISTS audit_events (
 id BIGINT PRIMARY KEY AUTO_INCREMENT,
 actor VARCHAR(80) NOT NULL,
 action VARCHAR(80) NOT NULL,
 environment VARCHAR(12) NOT NULL,
 device_id BIGINT NULL,
 detail VARCHAR(1000) NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 INDEX audit_environment_time (environment,created_at)
);
CREATE TABLE IF NOT EXISTS ai_settings (
 id TINYINT PRIMARY KEY,
 settings_json LONGTEXT NOT NULL,
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
 updated_by BIGINT NULL,
 FOREIGN KEY (updated_by) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS demo_state (
 device_id BIGINT PRIMARY KEY,
 online BOOLEAN NOT NULL DEFAULT 1,
 services_json LONGTEXT NOT NULL,
 disk_percent DOUBLE NOT NULL DEFAULT 30,
 FOREIGN KEY (device_id) REFERENCES devices(id)
);
CREATE TABLE IF NOT EXISTS incident_events (
 id BIGINT PRIMARY KEY AUTO_INCREMENT,
 incident_id BIGINT NOT NULL,
 actor VARCHAR(80) NOT NULL,
 action VARCHAR(40) NOT NULL,
 status VARCHAR(20) NOT NULL,
 note TEXT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS service_state (
 name VARCHAR(40) PRIMARY KEY,
 heartbeat_at DATETIME(6) NULL,
 detail_json TEXT NULL,
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
);
CREATE TABLE IF NOT EXISTS ai_usage (
 day DATE PRIMARY KEY,
 requests INT NOT NULL DEFAULT 0
);
