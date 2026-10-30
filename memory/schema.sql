PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    preferred_name TEXT,
    comfort_style TEXT DEFAULT 'warm, loyal, motivational, not fake',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    message TEXT NOT NULL,
    emotion_tag TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Retry metadata only. Message and event payloads are re-read from their source
-- rows when sent, so clearing local conversation history also removes its queue.
CREATE TABLE IF NOT EXISTS cloud_sync_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_type TEXT NOT NULL CHECK(record_type IN ('conversation', 'sensor_event', 'conversation_delete')),
    local_id INTEGER NOT NULL,
    device_id TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at REAL NOT NULL DEFAULT 0,
    UNIQUE(record_type, local_id, device_id)
);

CREATE TABLE IF NOT EXISTS memory_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    fact_key TEXT NOT NULL,
    fact_value TEXT NOT NULL,
    confidence REAL DEFAULT 0.7,
    source TEXT DEFAULT 'conversation',
    last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, fact_key),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Forgetting an inferred summary also prevents automatic extraction from saving it again.
CREATE TABLE IF NOT EXISTS forgotten_memory_facts (
    user_id INTEGER NOT NULL,
    fact_key TEXT NOT NULL,
    forgotten_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(user_id, fact_key),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS companion_preferences (
    user_id INTEGER PRIMARY KEY,
    checkins_enabled INTEGER NOT NULL DEFAULT 0 CHECK (checkins_enabled IN (0, 1)),
    quiet_start TEXT NOT NULL DEFAULT '22:00',
    quiet_end TEXT NOT NULL DEFAULT '08:00',
    checkin_interval_hours INTEGER NOT NULL DEFAULT 24 CHECK (checkin_interval_hours BETWEEN 4 AND 168),
    last_checkin_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    event_summary TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    source TEXT DEFAULT 'system',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS mood_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    detected_mood TEXT NOT NULL,
    mood_reason TEXT,
    confidence REAL DEFAULT 0.5,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS routine_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    routine_key TEXT NOT NULL,
    routine_value TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, routine_key),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS routine_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    local_time TEXT NOT NULL,
    days_of_week TEXT NOT NULL DEFAULT '1,2,3,4,5,6,7',
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    last_delivered_on TEXT,
    dismissed_on TEXT,
    acknowledged_on TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS forgotten_memory_routines (
    user_id INTEGER NOT NULL,
    routine_key TEXT NOT NULL,
    forgotten_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(user_id, routine_key),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS safety_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT DEFAULT 'low',
    action_taken TEXT,
    resolved INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS emergency_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    relation TEXT,
    priority INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS response_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    response_text TEXT NOT NULL,
    rating TEXT NOT NULL,
    feedback_text TEXT,
    situation TEXT,
    tone TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS device_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    event_summary TEXT NOT NULL,
    source TEXT DEFAULT 'unknown',
    room TEXT,
    severity TEXT DEFAULT 'low',
    confidence REAL DEFAULT 0.5,
    requires_action INTEGER DEFAULT 0,
    action_status TEXT DEFAULT 'none',
    metadata_json TEXT,
    external_event_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS sensor_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    node_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    room TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT,
    disabled INTEGER NOT NULL DEFAULT 0 CHECK (disabled IN (0, 1)),
    UNIQUE(user_id, node_id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS action_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    action_summary TEXT NOT NULL,
    target TEXT,
    status TEXT DEFAULT 'planned',
    source_event_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (source_event_id) REFERENCES device_events(id)
);

CREATE TABLE IF NOT EXISTS known_people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    relation TEXT,
    notes TEXT,
    trust_level TEXT DEFAULT 'known',
    consent_to_remember INTEGER DEFAULT 0,
    face_profile_status TEXT DEFAULT 'not_enrolled',
    allowed_rooms TEXT,
    emergency_contact INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS person_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    person_id INTEGER,
    event_type TEXT NOT NULL,
    event_summary TEXT NOT NULL,
    source TEXT DEFAULT 'manual',
    room TEXT,
    confidence REAL DEFAULT 0.5,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (person_id) REFERENCES known_people(id)
);

CREATE TABLE IF NOT EXISTS escalation_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT DEFAULT 'medium',
    first_action TEXT NOT NULL,
    second_action TEXT,
    final_action TEXT,
    wait_seconds_before_escalation INTEGER DEFAULT 30,
    requires_user_confirmation INTEGER DEFAULT 1,
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS escalation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    source_event_id INTEGER,
    event_type TEXT NOT NULL,
    severity TEXT DEFAULT 'medium',
    escalation_stage TEXT NOT NULL,
    action_summary TEXT NOT NULL,
    status TEXT DEFAULT 'planned',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (source_event_id) REFERENCES device_events(id)
);

CREATE TABLE IF NOT EXISTS confirmation_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    source_event_id INTEGER,
    confirmation_type TEXT NOT NULL,
    prompt TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    response_text TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    responded_at TEXT,
    expires_at TEXT,
    metadata_json TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (source_event_id) REFERENCES device_events(id)
);

CREATE INDEX IF NOT EXISTS idx_confirmation_requests_user_status
    ON confirmation_requests (user_id, status);

CREATE INDEX IF NOT EXISTS idx_confirmation_requests_event
    ON confirmation_requests (source_event_id);

CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    source_event_id INTEGER,
    incident_type TEXT NOT NULL,
    title TEXT NOT NULL,
    room TEXT,
    severity TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    summary TEXT,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT,
    metadata_json TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (source_event_id) REFERENCES device_events(id)
);

CREATE TABLE IF NOT EXISTS incident_timeline_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    source_type TEXT,
    source_id INTEGER,
    title TEXT NOT NULL,
    summary TEXT,
    status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT,
    FOREIGN KEY (incident_id) REFERENCES incidents(id)
);

CREATE INDEX IF NOT EXISTS idx_incidents_user_status
    ON incidents (user_id, status);

CREATE INDEX IF NOT EXISTS idx_incidents_source_event
    ON incidents (source_event_id);

CREATE INDEX IF NOT EXISTS idx_incident_timeline_incident
    ON incident_timeline_items (incident_id);

CREATE TABLE IF NOT EXISTS service_heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    service_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'online',
    pid INTEGER,
    last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT,
    UNIQUE(user_id, service_name),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_service_heartbeats_user_service
    ON service_heartbeats (user_id, service_name);

-- Opt-in expiry; existing installations retain all notes until explicitly changed.
CREATE TABLE IF NOT EXISTS observation_retention (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    days INTEGER NOT NULL DEFAULT 0 CHECK(days IN (0, 1, 7, 30, 90, 365))
);
-- Conversation expiry is separate and opt-in; saved facts and notes are unaffected.
CREATE TABLE IF NOT EXISTS conversation_retention (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    days INTEGER NOT NULL DEFAULT 0 CHECK(days IN (0, 1, 7, 30, 90, 365))
);
-- Person notes are a separate consented-memory category with their own opt-in expiry.
CREATE TABLE IF NOT EXISTS person_memory_retention (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    days INTEGER NOT NULL DEFAULT 0 CHECK(days IN (0, 1, 7, 30, 90, 365))
);
CREATE INDEX IF NOT EXISTS idx_observations_user_created ON observations(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_user_created ON conversation_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_person_events_user_created
    ON person_events(user_id, created_at);

-- Short-lived explicit room invitations. No transcript/audio/location history.
CREATE TABLE IF NOT EXISTS room_sessions (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    session_id TEXT NOT NULL UNIQUE,
    node_id TEXT NOT NULL,
    generation INTEGER NOT NULL,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS room_reply_claims (
    user_id INTEGER NOT NULL REFERENCES users(id),
    session_id TEXT NOT NULL REFERENCES room_sessions(session_id) ON DELETE CASCADE,
    turn_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    generation INTEGER NOT NULL,
    PRIMARY KEY(session_id, turn_id)
);
