CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('client', 'contractor', 'admin')),
    display_name TEXT NOT NULL,
    company_name TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
    email_verified INTEGER NOT NULL DEFAULT 0,
    auth_provider TEXT NOT NULL DEFAULT 'local',
    external_subject TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_requests (
    id INTEGER PRIMARY KEY,
    actor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (length(action) BETWEEN 1 AND 80),
    key_hash TEXT NOT NULL CHECK (length(key_hash) = 64),
    resource_type TEXT NOT NULL CHECK (
        resource_type IN ('job', 'message', 'report', 'job_photo', 'contractor_photo')
    ),
    resource_id INTEGER,
    status TEXT NOT NULL DEFAULT 'processing' CHECK (
        status IN ('processing', 'completed')
    ),
    created_at TEXT NOT NULL,
    completed_at TEXT,
    expires_at TEXT NOT NULL,
    UNIQUE(actor_id, action, key_hash)
);

CREATE INDEX IF NOT EXISTS idx_idempotency_requests_expiry
ON idempotency_requests(status, expires_at);

CREATE TABLE IF NOT EXISTS client_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    organization_name TEXT NOT NULL,
    phone TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS contractor_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    business_name TEXT NOT NULL,
    trades TEXT DEFAULT '',
    service_area TEXT DEFAULT '',
    intro TEXT DEFAULT '',
    insurance_status TEXT DEFAULT '',
    license_number TEXT DEFAULT '',
    years_in_business INTEGER,
    website TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contractor_credentials (
    id INTEGER PRIMARY KEY,
    contractor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    credential_type TEXT NOT NULL CHECK (
        credential_type IN ('trade_license', 'business_registration', 'insurance')
    ),
    jurisdiction TEXT NOT NULL CHECK (
        jurisdiction IN ('DC', 'MD', 'VA', 'FEDERAL', 'OTHER')
    ),
    claimed_identifier TEXT NOT NULL,
    claimed_name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'self_reported' CHECK (
        status IN ('self_reported', 'pending', 'verified', 'expired', 'rejected')
    ),
    source_url TEXT NOT NULL DEFAULT '',
    checked_at TEXT,
    expires_at TEXT,
    reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    review_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(contractor_id, credential_type, jurisdiction, claimed_identifier)
);

CREATE TABLE IF NOT EXISTS contractor_lead_preferences (
    contractor_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    availability_status TEXT NOT NULL DEFAULT 'available' CHECK (
        availability_status IN ('available', 'limited', 'unavailable')
    ),
    available_from TEXT,
    saved_query TEXT NOT NULL DEFAULT '',
    saved_category TEXT NOT NULL DEFAULT '',
    saved_service_group_slug TEXT NOT NULL DEFAULT '',
    saved_service_slug TEXT NOT NULL DEFAULT '',
    saved_sort TEXT NOT NULL DEFAULT 'newest' CHECK (
        saved_sort IN ('newest', 'soonest', 'city')
    ),
    saved_at TEXT,
    lead_alert_preference TEXT NOT NULL DEFAULT 'workdoe' CHECK (
        lead_alert_preference IN ('workdoe', 'email')
    ),
    lead_alert_consent_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_contractor_lead_preferences_family
ON contractor_lead_preferences(saved_service_group_slug, saved_at);

CREATE TABLE IF NOT EXISTS contractor_lead_alert_deliveries (
    id INTEGER PRIMARY KEY,
    contractor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'queued', 'sent', 'failed')
    ),
    created_at TEXT NOT NULL,
    queued_at TEXT,
    sent_at TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(contractor_id, job_id)
);

CREATE INDEX IF NOT EXISTS idx_contractor_lead_alert_deliveries_status
ON contractor_lead_alert_deliveries(status, updated_at);

CREATE TABLE IF NOT EXISTS client_project_templates (
    id INTEGER PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL COLLATE NOCASE,
    source_job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    service_group_slug TEXT,
    service_slug TEXT,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    project_setting TEXT NOT NULL DEFAULT '',
    license_preference INTEGER NOT NULL DEFAULT 0 CHECK (license_preference IN (0, 1)),
    budget_min INTEGER,
    budget_max INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(client_id, name)
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    zip_code TEXT NOT NULL,
    description TEXT NOT NULL,
    desired_date TEXT DEFAULT '',
    license_preference INTEGER NOT NULL DEFAULT 0 CHECK (license_preference IN (0, 1)),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'hidden', 'closed')),
    approx_lat REAL,
    approx_lng REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_photos (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    uploaded_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    is_hidden INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contractor_photos (
    id INTEGER PRIMARY KEY,
    contractor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    is_hidden INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS match_requests (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    contractor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scope_note TEXT NOT NULL,
    price_range TEXT NOT NULL,
    timeline TEXT NOT NULL,
    experience TEXT NOT NULL,
    questions TEXT DEFAULT '',
    availability TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(job_id, contractor_id)
);

CREATE TABLE IF NOT EXISTS service_policy_acknowledgements (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    actor_role TEXT NOT NULL CHECK (actor_role IN ('client', 'contractor')),
    context TEXT NOT NULL CHECK (context IN ('project-post', 'mini-bid')),
    service_slug TEXT NOT NULL REFERENCES service_types(slug),
    policy_version TEXT NOT NULL,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    match_request_id INTEGER REFERENCES match_requests(id) ON DELETE CASCADE,
    acknowledged_at TEXT NOT NULL,
    CHECK (
        (context = 'project-post' AND job_id IS NOT NULL AND match_request_id IS NULL)
        OR
        (context = 'mini-bid' AND job_id IS NOT NULL AND match_request_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_service_policy_ack_user
ON service_policy_acknowledgements(user_id, acknowledged_at DESC);

CREATE INDEX IF NOT EXISTS idx_service_policy_ack_resource
ON service_policy_acknowledgements(context, job_id, match_request_id);

CREATE TABLE IF NOT EXISTS contractor_proposal_templates (
    id INTEGER PRIMARY KEY,
    contractor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL COLLATE NOCASE CHECK (length(name) BETWEEN 1 AND 60),
    source_match_request_id INTEGER REFERENCES match_requests(id) ON DELETE SET NULL,
    scope_note TEXT NOT NULL,
    timeline TEXT NOT NULL,
    experience TEXT NOT NULL,
    questions TEXT NOT NULL DEFAULT '',
    availability TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(contractor_id, name)
);

CREATE TABLE IF NOT EXISTS repeat_provider_invitations (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
    source_job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    source_match_request_id INTEGER REFERENCES match_requests(id) ON DELETE SET NULL,
    client_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contractor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service_slug TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'bid_sent', 'declined', 'withdrawn')
    ),
    created_at TEXT NOT NULL,
    responded_at TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(job_id, contractor_id)
);

CREATE TABLE IF NOT EXISTS match_reviews (
    id INTEGER PRIMARY KEY,
    match_request_id INTEGER NOT NULL REFERENCES match_requests(id) ON DELETE CASCADE,
    reviewer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reviewer_role TEXT NOT NULL CHECK (reviewer_role IN ('client', 'contractor')),
    communication TEXT NOT NULL CHECK (
        communication IN ('met', 'mixed', 'concern', 'not_applicable')
    ),
    scope_accuracy TEXT NOT NULL CHECK (
        scope_accuracy IN ('met', 'mixed', 'concern', 'not_applicable')
    ),
    timeliness TEXT NOT NULL CHECK (
        timeliness IN ('met', 'mixed', 'concern', 'not_applicable')
    ),
    work_outcome TEXT NOT NULL CHECK (
        work_outcome IN ('met', 'mixed', 'concern', 'not_applicable')
    ),
    would_work_again TEXT NOT NULL CHECK (
        would_work_again IN ('yes', 'unsure', 'no')
    ),
    comment TEXT NOT NULL DEFAULT '',
    response TEXT NOT NULL DEFAULT '',
    response_at TEXT,
    is_hidden INTEGER NOT NULL DEFAULT 0 CHECK (is_hidden IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(match_request_id, reviewer_id)
);

CREATE TABLE IF NOT EXISTS match_review_reports (
    id INTEGER PRIMARY KEY,
    review_id INTEGER NOT NULL REFERENCES match_reviews(id) ON DELETE CASCADE,
    reporter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    UNIQUE(review_id, reporter_id)
);

CREATE INDEX IF NOT EXISTS idx_match_reviews_subject
ON match_reviews(subject_id, reviewer_role, is_hidden, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_match_review_reports_status
ON match_review_reports(status, created_at DESC);

CREATE TABLE IF NOT EXISTS threads (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    match_request_id INTEGER NOT NULL UNIQUE REFERENCES match_requests(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contractor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    thread_id INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    is_hidden INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS thread_reads (
    thread_id INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    last_read_message_id INTEGER NOT NULL DEFAULT 0,
    last_read_at TEXT NOT NULL,
    PRIMARY KEY (thread_id, user_id)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY,
    reporter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL CHECK (target_type IN ('job', 'message', 'profile')),
    target_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS login_codes (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('client', 'contractor')),
    display_name TEXT NOT NULL,
    company_name TEXT DEFAULT '',
    intent TEXT NOT NULL CHECK (intent IN ('post-job', 'find-work')),
    selected_job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    code_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS automation_events (
    id INTEGER PRIMARY KEY,
    event_type TEXT NOT NULL,
    target_type TEXT NOT NULL DEFAULT '',
    target_id INTEGER,
    payload_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processed', 'failed')),
    created_at TEXT NOT NULL,
    processed_at TEXT
);

CREATE TABLE IF NOT EXISTS moderation_actions (
    id INTEGER PRIMARY KEY,
    admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_category ON jobs(status, category);
CREATE INDEX IF NOT EXISTS idx_jobs_location ON jobs(state, city, zip_code);
CREATE INDEX IF NOT EXISTS idx_jobs_open_geo
ON jobs(status, approx_lat, approx_lng, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_job_photos_public_job
ON job_photos(job_id, is_hidden);
CREATE INDEX IF NOT EXISTS idx_contractor_photos_public_contractor
ON contractor_photos(contractor_id, is_hidden, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_match_requests_job ON match_requests(job_id, status);
CREATE INDEX IF NOT EXISTS idx_match_requests_contractor ON match_requests(contractor_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_match_requests_one_approved_per_job
ON match_requests(job_id) WHERE status = 'approved';
CREATE INDEX IF NOT EXISTS idx_contractor_proposal_templates_owner
ON contractor_proposal_templates(contractor_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_repeat_provider_invitations_contractor
ON repeat_provider_invitations(contractor_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_repeat_provider_invitations_client
ON repeat_provider_invitations(client_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_threads_parties ON threads(client_id, contractor_id);
CREATE INDEX IF NOT EXISTS idx_threads_client ON threads(client_id, id);
CREATE INDEX IF NOT EXISTS idx_threads_contractor ON threads(contractor_id, id);
CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_thread_unread
ON messages(thread_id, is_hidden, id, sender_id);
CREATE INDEX IF NOT EXISTS idx_thread_reads_user
ON thread_reads(user_id, last_read_message_id DESC);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status, created_at);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user ON password_reset_tokens(user_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_login_codes_email ON login_codes(email, expires_at);
CREATE INDEX IF NOT EXISTS idx_automation_events_type_target ON automation_events(event_type, target_type, target_id, created_at);
CREATE INDEX IF NOT EXISTS idx_contractor_credentials_owner ON contractor_credentials(contractor_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_contractor_credentials_review ON contractor_credentials(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_client_project_templates_owner ON client_project_templates(client_id, updated_at DESC);
