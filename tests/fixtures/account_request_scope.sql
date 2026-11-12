-- Local-only fixture; accounts come from tests/native_worker/seed.sql.
INSERT INTO jobs (id, client_id, title, category, city, state, zip_code, description, created_at, updated_at)
VALUES
    (1, 1, 'Shared project A', 'Window cleaning', 'Arlington', 'VA', '22201', 'Synthetic brief', '2000-01-01', '2000-01-01'),
    (2, 3, 'Unrelated project', 'Window cleaning', 'Arlington', 'VA', '22201', 'Synthetic brief', '2000-01-01', '2000-01-01'),
    (3, 3, 'Shared project B', 'Window cleaning', 'Arlington', 'VA', '22201', 'Synthetic brief', '2000-01-01', '2000-01-01');

INSERT INTO match_requests (
    id, job_id, contractor_id, scope_note, price_range, timeline, experience, availability, status, created_at, updated_at
)
VALUES
    (1, 1, 2, 'Synthetic bid A', '$100', 'One day', 'Fixture only', 'Tomorrow', 'approved', '2000-01-01', '2000-01-01'),
    (2, 2, 4, 'Unrelated bid', '$100', 'One day', 'Fixture only', 'Tomorrow', 'approved', '2000-01-01', '2000-01-01'),
    (3, 3, 2, 'Synthetic bid B', '$100', 'One day', 'Fixture only', 'Tomorrow', 'approved', '2000-01-01', '2000-01-01');

INSERT INTO threads (id, job_id, match_request_id, client_id, contractor_id, created_at)
SELECT bid.id, job.id, bid.id, job.client_id, bid.contractor_id, '2000-01-01'
FROM match_requests AS bid JOIN jobs AS job ON job.id = bid.job_id;

INSERT INTO messages (id, thread_id, sender_id, body, created_at)
SELECT id * 2 - 1, id, client_id, 'Synthetic consumer message', '2000-01-01' FROM threads
UNION ALL
SELECT id * 2, id, contractor_id, 'Synthetic contractor message', '2000-01-01' FROM threads;

INSERT INTO job_photos (
    id, job_id, uploaded_by, original_filename, stored_path, content_type, size_bytes, created_at
)
VALUES (1, 1, 1, 'workdoe-photo.webp', 'jobs/1/account-request-fixture.webp', 'image/webp', 10, '2000-01-01');

INSERT INTO contractor_photos (
    id, contractor_id, original_filename, stored_path, content_type, size_bytes, created_at
)
VALUES (1, 2, 'workdoe-photo.webp', 'contractors/2/account-request-fixture.webp', 'image/webp', 10, '2000-01-01');

INSERT INTO match_completions (match_request_id, created_at, updated_at)
VALUES (1, '2000-01-01', '2000-01-01'), (2, '2000-01-01', '2000-01-01'), (3, '2000-01-01', '2000-01-01');

INSERT INTO reports (id, reporter_id, target_type, target_id, reason, created_at)
VALUES
    (1, 2, 'job', 1, 'Synthetic open project report', '2000-01-01'),
    (2, 2, 'message', 1, 'Synthetic open message report', '2000-01-01'),
    (3, 1, 'profile', 2, 'Synthetic open profile report', '2000-01-01'),
    (4, 3, 'profile', 2, 'Synthetic independent report', '2000-01-01');

INSERT INTO moderation_actions (id, admin_id, action_type, target_type, target_id, notes, created_at)
VALUES (1, 5, 'hide-job', 'job', 1, 'Synthetic evidence note', '2000-01-01');

INSERT INTO automation_events (id, event_type, target_type, target_id, payload_json, status, created_at)
VALUES (1, 'synthetic-account-event', 'user', 1, '{}', 'processed', '2000-01-01');

INSERT INTO login_codes (
    id, email, role, display_name, intent, selected_job_id, code_hash, expires_at, created_at
)
VALUES
    (1, 'client@native.invalid', 'client', 'Fixture consumer', 'post-job', NULL, 'fixture-hash-a', '2000-01-02', '2000-01-01'),
    (2, 'contractor@native.invalid', 'contractor', 'Fixture contractor', 'find-work', 1, 'fixture-hash-b', '2000-01-02', '2000-01-01');

INSERT INTO job_drafts (id, token_hash, title, category, city, state, zip_code, description, expires_at, created_at, updated_at)
VALUES (1, 'fixture-draft-hash', 'Anonymous draft', 'Window cleaning', 'Arlington', 'VA', '22201', 'Synthetic draft', '2000-01-02', '2000-01-01', '2000-01-01');

INSERT INTO job_draft_scope_answers (draft_id, schema_version, question_key, answer_code, created_at, updated_at)
VALUES (1, 1, 'fixture-question', 'fixture-answer', '2000-01-01', '2000-01-01');

INSERT INTO service_policy_acknowledgements (
    id, user_id, actor_role, context, service_slug, policy_version, job_id, match_request_id, acknowledged_at
)
VALUES
    (1, 1, 'client', 'project-post', 'window-cleaning', 'fixture-version', 1, NULL, '2000-01-01'),
    (2, 2, 'contractor', 'mini-bid', 'window-cleaning', 'fixture-version', 1, 1, '2000-01-01');
