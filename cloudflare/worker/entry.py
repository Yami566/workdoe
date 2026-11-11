from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlsplit

from admin_moderation import (
    AdminModerationError,
    admin_moderation_response,
    admin_target_query,
    admin_update_statement,
    can_admin_moderate,
    parse_admin_moderation_path,
)
from app_shell import (
    account_security_html,
    admin_dashboard_html,
    app_login_url,
    app_shell_headers,
    client_dashboard_html,
    client_job_detail_html,
    client_profile_html,
    client_request_inbox_html,
    contractor_dashboard_html,
    contractor_job_detail_html,
    contractor_profile_html,
    dashboard_access_html,
    dashboard_path_for_user,
    is_app_shell_route,
    is_public_contractor_profile_route,
    job_form_html,
    lead_board_html,
    message_thread_detail_html,
    message_threads_html,
    parse_app_client_job_edit_id,
    parse_app_client_job_id,
    parse_app_contractor_id,
    parse_app_job_id,
    parse_app_thread_id,
    privacy_page_html,
    public_contractor_profile_html,
    public_job_draft_html,
    public_robots_txt,
    public_security_txt,
    public_sitemap_xml,
    recovery_workspace_html,
    safety_page_html,
    terms_page_html,
    unavailable_form_html,
)
from clerk_identity import CLERK_RESTRICTION_FLAGS
from clerk_onboarding import (
    MAX_ONBOARDING_BODY_BYTES,
    OnboardingError,
    claims_with_verified_clerk_email,
    onboarding_payload,
    onboarding_profile,
)
from clerk_proxy import (
    ClerkProxyError,
    clerk_proxy_origin_allowed,
    clerk_proxy_request_plan,
    is_clerk_proxy_path,
    verified_clerk_package,
)
from clerk_sessions import (
    SessionVerificationError,
    authorized_parties_from_env,
    cached_clerk_jwks,
    extract_clerk_session_token,
    fetch_clerk_jwks,
    verify_clerk_session_token,
)
from clerk_webhooks import (
    SvixVerificationError,
    clerk_user_sync_payload,
    verify_svix_signature,
)
from client_jobs import (
    CLIENT_JOB_LIMIT,
    can_view_client_jobs,
    client_jobs_payload,
    normalize_client_job_view,
)
from client_profiles import (
    MAX_CLIENT_PROFILE_BODY_BYTES,
    MAX_SAVED_LOCATION_BODY_BYTES,
    SAVED_LOCATION_LIMIT,
    ClientProfileError,
    SavedLocationError,
    can_update_client_profile,
    client_profile_payload,
    client_profile_response,
    parse_saved_location_delete_path,
    saved_location_payload,
    saved_location_response,
)
from client_project_templates import (
    PROJECT_TEMPLATE_LIMIT,
    ProjectTemplateError,
    parse_project_template_delete_path,
    project_template_job_form,
    project_template_request_payload,
    project_template_response,
)
from client_requests import (
    CLIENT_REQUEST_LIMIT,
    ClientRequestError,
    can_view_client_job_requests,
    client_job_requests_payload,
    normalize_client_request_view,
    parse_client_job_requests_path,
)
from content_privacy import (
    PUBLIC_PROJECT_PRIVACY_LOOKAHEAD,
    contains_disallowed_personal_data,
    public_project_page,
)
from contractor_bids import (
    CONTRACTOR_BID_LIMIT,
    can_view_contractor_bids,
    contractor_bids_payload,
    normalize_contractor_bid_view,
)
from contractor_credentials import (
    MAX_CONTRACTOR_CREDENTIAL_BODY_BYTES,
    ContractorCredentialError,
    contractor_credential_claim_payload,
    contractor_credential_review_payload,
    credential_response,
    parse_contractor_credential_remove_path,
    public_credential_responses,
)
from contractor_leads import (
    can_view_contractor_leads,
    contractor_lead_filters_from_query,
    contractor_lead_order_clause,
    contractor_leads_payload,
    normalize_contractor_lead_view,
    parse_contractor_lead_limit,
)
from contractor_preferences import (
    ContractorPreferenceError,
    availability_payload,
    contractor_preferences_response,
    saved_lead_view_payload,
    saved_lead_view_url,
)
from contractor_profiles import (
    MAX_CONTRACTOR_PROFILE_BODY_BYTES,
    ContractorProfileError,
    can_update_contractor_profile,
    contractor_profile_payload,
    contractor_profile_response,
)
from contractor_proposal_templates import (
    PROPOSAL_TEMPLATE_LIMIT,
    PROPOSAL_TEMPLATE_NAME_MAX_LENGTH,
    ProposalTemplateError,
    parse_proposal_template_delete_path,
    proposal_template_bid_form,
    proposal_template_request_payload,
    proposal_template_response,
    proposal_template_values,
)
from contractor_public_profiles import (
    ContractorPublicProfileError,
    can_view_contractor_website,
    can_view_public_contractor_profile,
    contractor_choice_context,
    parse_public_contractor_id,
    public_contractor_profile_payload,
)
from demo_projects import guest_project_rows
from email_code_auth import (
    AUTH_PROVIDER as EMAIL_CODE_AUTH_PROVIDER,
)
from email_code_auth import (
    CHALLENGE_TTL_SECONDS,
    MAX_CODE_ATTEMPTS,
    EmailCodeAuthError,
    challenge_token,
    clear_session_cookie,
    fixed_account_role,
    generate_code,
    hash_code,
    hash_identifier,
    normalize_code,
    normalize_email,
    role_for_intent,
    safe_next_path,
    session_cookie,
    session_from_cookie,
    session_token,
    tokens_match,
    valid_email,
    verified_token,
)
from email_code_auth import (
    compact_spaces as compact_auth_text,
)
from email_code_auth import (
    normalize_intent as normalize_auth_intent,
)
from email_delivery import lead_alert_candidates_query, marketplace_email_delivery_query
from email_payloads import (
    EmailPayloadError,
    build_email_message,
    email_audit_metadata,
    email_send_result_summary,
)
from entry_shell import (
    ENTRY_JOB_LIMIT,
    ENTRY_ROUTES,
    build_entry_shell_html,
    clerk_development_frontend_api_url,
    entry_job_filters,
    is_production_clerk_publishable_key,
    missing_page_html,
    selected_job_id,
    shell_headers,
    unavailable_entry_html,
    unavailable_job_draft_html,
)
from idempotency import (
    IdempotencyError,
    idempotency_action,
    idempotency_key_hash,
    idempotency_resource_type,
    new_idempotency_key,
    normalize_idempotency_key,
)
from job_details import (
    JobDetailError,
    can_view_job_detail,
    job_detail_payload,
    parse_job_detail_id,
    viewer_kind,
)
from job_drafts import (
    JOB_DRAFT_TTL_SECONDS,
    JobDraftReadError,
    clear_job_draft_cookie,
    generate_job_draft_token,
    job_draft_cookie,
    job_draft_token_from_cookie,
    job_draft_token_hash,
)
from job_posts import (
    DEFAULT_BID_LIMIT,
    JOB_CATEGORIES,
    JOB_LOCATION_PRIVACY_NOTICE,
    MAX_JOB_POST_BODY_BYTES,
    JobPostError,
    bid_window,
    budget_database_value,
    can_update_job,
    cleaned_job_payload,
    default_bidding_closes_at,
    extended_bidding_closes_at,
    job_post_payload,
    parse_job_update_id,
    validate_job_payload,
)
from job_status import (
    MAX_OUTCOME_BODY_BYTES,
    JobStatusError,
    can_submit_lead_quality_feedback,
    can_update_job_status,
    job_status_response,
    parse_job_quality_feedback_path,
    parse_job_status_path,
    validate_lead_quality_payload,
    validate_project_close_payload,
)
from json_values import (
    JsonDataError,
    normalize_json_value,
    parse_json_value,
    read_json_response_bytes,
    read_json_stream_bytes,
)
from map_tiles import AREA_MAP_ASSET, map_tile_configuration
from market_fit import (
    infer_service_slugs_from_trades,
    infer_zone_slugs_from_area,
    job_zone_slug,
    normalize_service_slugs,
    normalize_zone_slugs,
)
from match_completions import (
    MatchCompletionError,
    completion_response,
    parse_match_completion_path,
    validate_completion_confirmation,
)
from match_decisions import (
    APPROVAL_THREAD_MESSAGE,
    MatchDecisionError,
    can_decide_match_request,
    d1_change_count,
    match_decision_response,
    parse_match_decision_path,
)
from match_requests import (
    MAX_MATCH_REQUEST_BODY_BYTES,
    MatchRequestError,
    match_request_payload,
    parse_match_request_job_id,
)
from match_reviews import (
    MAX_MATCH_REVIEW_BODY_BYTES,
    MatchReviewError,
    parse_match_review_action_path,
    parse_match_review_create_path,
    review_response,
    review_subject_id,
    validate_review_eligibility,
    validate_review_payload,
    validate_review_report,
    validate_review_response,
)
from media_access import (
    PRIVATE_MEDIA_NOTICE,
    MediaAccessError,
    can_view_contractor_photo,
    can_view_job_photo,
    inline_content_disposition,
    media_scope_from_path,
    safe_media_key,
)
from media_uploads import (
    ALLOWED_IMAGE_MIME,
    MAX_UPLOAD_BYTES,
    SANITIZED_IMAGE_EXTENSION,
    MediaUploadError,
    build_r2_upload_key,
    can_upload_contractor_photo,
    can_upload_job_photo,
    form_file_value,
    media_metadata_delete_statement,
    media_review_payload,
    media_upload_quota_error,
    media_upload_scope_from_path,
    sanitize_uploaded_image,
    sanitized_upload_details,
    upload_http_metadata,
    uploaded_file_details,
    validate_uploaded_file_signature,
    validated_media_review_payload,
)
from message_history import (
    message_history_page,
    message_window_query,
    parse_message_through,
)
from message_threads import (
    MAX_MESSAGE_BODY_BYTES,
    MessageThreadError,
    can_send_thread_message,
    can_view_thread,
    message_body_payload,
    message_threads_listing_payload,
    parse_thread_id,
    thread_detail_payload,
)
from moderation_reports import (
    MAX_REPORT_BODY_BYTES,
    ModerationReportError,
    can_create_report,
    report_payload,
    report_response,
    report_target_query,
)
from pilot_metrics import (
    MARKETPLACE_OUTCOMES_SQL,
    REPEAT_INVITATION_OUTCOMES_SQL,
    pilot_cell_metrics,
)
from project_access import (
    PRIVATE_MEDIA_EMBEDDING_HEADERS,
    contractor_can_view_project,
    private_media_embedding_blocked,
)
from public_job_query import (
    PUBLIC_DISCOVERY_API_METHODS,
    PublicJobQueryError,
    build_public_open_jobs_query,
    literal_project_search,
    next_public_cursor,
    parse_public_cursor,
    parse_public_viewport,
    public_query_envelope_rejection,
    public_query_telemetry,
)
from public_jobs import (
    first_query_value,
    normalize_public_target,
    parse_public_limit,
    public_job_filters_from_query,
    public_job_order_clause,
    public_jobs_payload,
)
from repeat_provider_invitations import (
    RepeatProviderInvitationError,
    parse_invitation_action_path,
    positive_int,
    repeat_invitation_response,
    validate_invitation_action,
    validate_repeat_invitation_service,
    validate_repeat_invitation_source,
)
from request_security import (
    WORKDOE_REQUEST_HEADER,
    authenticated_write_rate_limit_key,
    authenticated_write_rate_limit_required,
    parse_url_record_id,
    same_origin_api_write_allowed,
    same_origin_form_write_allowed,
)
from service_activation import (
    ACTIVATION_NOT_OPEN_MESSAGE,
    activation_is_live,
    enabled_flag,
)
from service_policy import service_policy, service_policy_error
from service_scope import (
    SCOPE_SCHEMA_VERSION,
    scope_answer_field_names,
    scope_answer_projection,
)
from service_taxonomy import (
    GROUP_BY_SLUG,
    SERVICE_BY_SLUG,
    service_label,
    service_selection,
)
from staging_origin import (
    is_staging_environment,
    staging_hostname,
    staging_request_allowed,
)
from turnstile import (
    TURNSTILE_VERIFY_URL,
    TurnstileError,
    remote_ip_from_headers,
    siteverify_payload,
    turnstile_result_allowed,
    turnstile_token_from_payload,
)
from workers import Response, WorkerEntrypoint, fetch

try:
    from js import JSON as JS_JSON
    from js import Object as JS_OBJECT
    from pyodide.ffi import jsnull as JS_NULL
    from pyodide.ffi import to_js as PYODIDE_TO_JS
except ImportError:  # pragma: no cover - available inside the Workers runtime
    JS_JSON = None
    JS_OBJECT = None
    JS_NULL = None
    PYODIDE_TO_JS = None


EXPIRE_CODES_CRON = "*/15 * * * *"
STALE_MATCH_REMINDERS_CRON = "0 14 * * *"
MODERATION_DIGEST_CRON = "0 13 * * 1-5"
MAX_AUTH_BODY_BYTES = 8 * 1024
MAX_REQUEST_JSON_BODY_CHUNKS = 128
REQUEST_JSON_BODY_TIMEOUT_SECONDS = 10
MAX_CLERK_WEBHOOK_BODY_BYTES = 256 * 1024
MAX_CLERK_WEBHOOK_BODY_CHUNKS = 128
CLERK_WEBHOOK_BODY_TIMEOUT_SECONDS = 5
CLERK_LOGOUT_TIMEOUT_SECONDS = 5
MAX_DRAFT_FORM_FIELDS = 128
MAX_DRAFT_FORM_CHUNKS = 128
DRAFT_FORM_TIMEOUT_SECONDS = 10
MAX_PROVIDER_JSON_BODY_BYTES = 256 * 1024
MAX_PROVIDER_JSON_BODY_CHUNKS = 128
TURNSTILE_VERIFY_TIMEOUT_SECONDS = 5
MAX_CLERK_USER_BODY_BYTES = 256 * 1024
MAX_CLERK_USER_BODY_CHUNKS = 128
CLERK_USER_LOOKUP_TIMEOUT_SECONDS = 5
CLERK_PROXY_RESPONSE_TIMEOUT_SECONDS = 8
AUTH_REQUEST_WINDOW_MINUTES = 15
AUTH_REQUESTS_PER_EMAIL = 5
AUTH_REQUESTS_PER_IP = 20
PUBLIC_HTTPS_HOSTS = {"workdoe.com", "www.workdoe.com"}
HSTS_HEADER = "max-age=31536000; includeSubDomains"
RECOVERY_RETRY_SECONDS = 900
RECOVERY_SAFE_ROUTES = frozenset({
    "/health", "/healthz", "/safety", "/privacy", "/terms",
    "/robots.txt", "/sitemap.xml", "/.well-known/security.txt",
})
WRITE_PAUSE_PUBLIC_ROUTES = RECOVERY_SAFE_ROUTES | {"/", "/api/jobs/open"}
PUBLIC_DISCOVERY_ROUTES = (ENTRY_ROUTES - {"/post-project"}) | {"/api/jobs/open"}
PUBLIC_DISCOVERY_RETRY_SECONDS = "60"
MAX_QUEUE_JSON_BODY_BYTES = 32 * 1024
OPTIONAL_MARKETPLACE_EMAIL_EVENTS = frozenset({
    "stale-match-reminder",
    "repeat-provider-invitation",
    "contractor-lead-alert-fanout",
    "contractor-new-lead",
})
STATIC_ASSET_PATHS = {
    AREA_MAP_ASSET,
    "/clerk-account.js",
    "/clerk-entry.js",
    "/deer.svg",
    "/email-code-entry.js",
    "/field-doe.webp",
    "/map.js",
    "/project-composer.js",
    "/site-dialogs.js",
    "/site.webmanifest",
    "/styles.css",
    "/workdoe-share.png",
    "/worker-actions.js",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def json_response(
    payload: dict, status: int = 200, headers: dict | None = None, *, set_cookies: tuple[str, ...] = (),
) -> Response:
    response_headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Strict-Transport-Security": HSTS_HEADER,
    }
    response_headers.update(headers or {})
    return Response(
        json.dumps(payload),
        status=status,
        headers=[*response_headers.items(), *(("Set-Cookie", cookie) for cookie in set_cookies)]
        if set_cookies else response_headers,
    )


def rows_from(result) -> list[dict]:
    if isinstance(result, dict):
        rows = result.get("results") or result.get("result", {}).get("results") or []
    else:
        rows = getattr(result, "results", None) or []
    converter = getattr(rows, "to_py", None)
    if callable(converter):
        # D1 records are flat; shared Python presenters must not receive FFI nulls.
        return [
            {key: None if value is JS_NULL else value for key, value in row.items()}
            for row in converter(depth=2)
        ]
    return rows


def db_statement(env, sql: str, params):
    statement = env.DB.prepare(sql)
    if params:
        d1_params = tuple(JS_NULL if value is None else value for value in params)
        statement = statement.bind(*d1_params)
    return statement


async def db_run(env, sql: str, *params):
    return await db_statement(env, sql, params).run()


async def db_batch(env, commands):
    statements = [db_statement(env, sql, params) for sql, params in commands]
    return await env.DB.batch(statements)


async def begin_idempotent_request(
    env,
    actor_id: int,
    action: str,
    resource_type: str,
    raw_key,
) -> dict:
    normalized_action = idempotency_action(action)
    normalized_resource = idempotency_resource_type(resource_type)
    key = normalize_idempotency_key(raw_key) or new_idempotency_key()
    key_hash = idempotency_key_hash(key)
    timestamp = datetime.now(timezone.utc)
    created_at = timestamp.isoformat(timespec="seconds")
    expires_at = (timestamp + timedelta(hours=24)).isoformat(timespec="seconds")
    await db_run(env, "DELETE FROM idempotency_requests WHERE expires_at < ?", created_at)
    reserved = await db_run(
        env,
        """
        INSERT OR IGNORE INTO idempotency_requests
            (actor_id, action, key_hash, resource_type, resource_id,
             status, created_at, completed_at, expires_at)
        VALUES (?, ?, ?, ?, NULL, 'processing', ?, NULL, ?)
        """,
        int(actor_id),
        normalized_action,
        key_hash,
        normalized_resource,
        created_at,
        expires_at,
    )
    if d1_change_count(reserved) == 1:
        return {
            "state": "reserved",
            "action": normalized_action,
            "key_hash": key_hash,
            "resource_type": normalized_resource,
            "resource_id": None,
        }
    record = first_row(
        await db_run(
            env,
            """
            SELECT action, key_hash, resource_type, resource_id, status
            FROM idempotency_requests
            WHERE actor_id = ? AND action = ? AND key_hash = ?
            LIMIT 1
            """,
            int(actor_id),
            normalized_action,
            key_hash,
        )
    )
    if not record:
        raise RuntimeError("Idempotent request reservation failed.")
    return {
        "state": "replay" if row_value(record, "status") == "completed" else "processing",
        "action": normalized_action,
        "key_hash": key_hash,
        "resource_type": row_value(record, "resource_type"),
        "resource_id": row_value(record, "resource_id"),
    }


async def complete_idempotent_request(
    env,
    actor_id: int,
    request_state: dict,
    resource_id: int,
) -> None:
    result = await db_run(
        env,
        """
        UPDATE idempotency_requests
        SET resource_id = ?, status = 'completed', completed_at = ?
        WHERE actor_id = ? AND action = ? AND key_hash = ?
          AND resource_type = ? AND status = 'processing'
        """,
        int(resource_id),
        utc_now(),
        int(actor_id),
        request_state["action"],
        request_state["key_hash"],
        request_state["resource_type"],
    )
    if d1_change_count(result) != 1:
        raise RuntimeError("Idempotent request completion failed.")


async def cancel_idempotent_request(env, actor_id: int, request_state: dict) -> None:
    if not request_state or request_state.get("state") != "reserved":
        return
    await db_run(
        env,
        """
        DELETE FROM idempotency_requests
        WHERE actor_id = ? AND action = ? AND key_hash = ?
          AND resource_type = ? AND status = 'processing'
        """,
        int(actor_id),
        request_state["action"],
        request_state["key_hash"],
        request_state["resource_type"],
    )


def idempotency_conflict_response(request_state: dict) -> Response | None:
    if request_state.get("state") != "processing":
        return None
    return json_response(
        {"ok": False, "error": "That request is still being processed. Try again shortly."},
        status=409,
        headers={"Cache-Control": "no-store", "Retry-After": "2"},
    )


def request_idempotency_value(request, payload=None):
    value = None
    if isinstance(payload, dict) or payload is not None and hasattr(payload, "get"):
        value = payload.get("idempotency_key")
    if value:
        return value
    headers = getattr(request, "headers", None)
    return headers.get("Idempotency-Key") if headers and hasattr(headers, "get") else ""


async def load_job_scope_answers(env, job_id: int) -> dict[str, str]:
    result = await db_run(
        env,
        "SELECT question_key, answer_code FROM job_scope_answers WHERE job_id = ?",
        job_id,
    )
    return {
        str(row_value(row, "question_key", "")): str(
            row_value(row, "answer_code", "")
        )
        for row in rows_from(result)
        if row_value(row, "question_key", "")
    }


async def commit_job_edit(env, job_id: int, actor_id: int, job: dict, service_zone_slug: str) -> bool:
    timestamp = utc_now()
    policy = service_policy(job["service_slug"])
    if policy["acknowledgement_required"] and job["service_policy_acknowledgement"] != policy["version"]:
        raise ValueError("The service policy acknowledgement is not current.")
    answers = {
        answer["question_key"]: answer["answer_code"]
        for answer in scope_answer_projection(job["service_slug"], job.get("scope_answers", {}))
    }
    # All dependent writes repeat the same access gate inside one D1 transaction.
    access_key = (job_id, actor_id)
    commands = [
        (
            """
            UPDATE jobs
            SET title = ?, category = ?, service_group_slug = ?, service_slug = ?,
                service_zone_slug = ?, project_setting = ?, license_preference = ?,
                city = ?, state = ?, zip_code = ?, description = ?, desired_date = ?,
                budget_min = ?, budget_max = ?, approx_lat = ?, approx_lng = ?, updated_at = ?
            WHERE id = ? AND client_id = ? AND status != 'hidden'
              AND EXISTS (
                  SELECT 1 FROM users
                  WHERE users.id = jobs.client_id AND users.role = 'client' AND users.status = 'active'
              )
            """,
            (
                job["title"], job["category"], job["service_group_slug"], job["service_slug"],
                service_zone_slug, job["project_setting"], int(job["license_preference"] == "1"),
                job["city"], job["state"], job["zip_code"], job["description"], job["desired_date"],
                budget_database_value(job["budget_min"]), budget_database_value(job["budget_max"]),
                job["approx_lat"], job["approx_lng"], timestamp, *access_key,
            ),
        ),
        (
            """
            DELETE FROM job_scope_answers
            WHERE job_id IN (
                SELECT jobs.id FROM jobs JOIN users ON users.id = jobs.client_id
                WHERE jobs.id = ? AND jobs.client_id = ? AND jobs.status != 'hidden'
                  AND users.role = 'client' AND users.status = 'active'
            )
            """,
            access_key,
        ),
    ]
    if answers:
        commands.append((
            """
            INSERT INTO job_scope_answers
                (job_id, schema_version, question_key, answer_code, created_at, updated_at)
            SELECT jobs.id, ?, answer.key, answer.value, ?, ?
            FROM jobs JOIN users ON users.id = jobs.client_id CROSS JOIN json_each(?) AS answer
            WHERE jobs.id = ? AND jobs.client_id = ? AND jobs.status != 'hidden'
              AND users.role = 'client' AND users.status = 'active'
            """,
            (SCOPE_SCHEMA_VERSION, timestamp, timestamp, json.dumps(answers), *access_key),
        ))
    if policy["acknowledgement_required"]:
        commands.append((
            """
            INSERT INTO service_policy_acknowledgements
                (user_id, actor_role, context, service_slug, policy_version, job_id, acknowledged_at)
            SELECT users.id, 'client', 'project-post', ?, ?, jobs.id, ?
            FROM jobs JOIN users ON users.id = jobs.client_id
            WHERE jobs.id = ? AND jobs.client_id = ? AND jobs.status != 'hidden'
              AND users.role = 'client' AND users.status = 'active'
            """,
            (job["service_slug"], policy["version"], timestamp, *access_key),
        ))
    commands.append((
        """
        INSERT INTO automation_events (event_type, target_type, target_id, payload_json, status, created_at)
        SELECT 'job-updated', 'job', jobs.id,
               json_object('client_id', users.id, 'category', ?), 'processed', ?
        FROM jobs JOIN users ON users.id = jobs.client_id
        WHERE jobs.id = ? AND jobs.client_id = ? AND jobs.status != 'hidden'
          AND users.role = 'client' AND users.status = 'active'
        """,
        (job["category"], timestamp, *access_key),
    ))
    results = await db_batch(env, commands)
    if (
        len(results) != len(commands) or any(row_value(result, "success") is not True for result in results)
        or d1_change_count(results[0]) not in {0, 1}
        or d1_change_count(results[-1]) != d1_change_count(results[0])
    ):
        raise ValueError("Unexpected D1 project edit batch result.")
    return d1_change_count(results[0]) == 1


def embedded_dialog_request(request) -> bool:
    params = parse_qs(urlparse(request.url).query)
    return first_query_value(params, "embed") == "1"


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def enforce_service_activation(env) -> bool:
    return enabled_flag(getattr(env, "WORKDOE_ENFORCE_SERVICE_ACTIVATION", ""))


def media_uploads_enabled(env) -> bool:
    """Keep public uploads off unless the reviewed sanitizer is explicitly enabled."""
    return enabled_flag(getattr(env, "WORKDOE_MEDIA_UPLOADS_ENABLED", ""))


def marketplace_email_enabled(env) -> bool:
    return not is_staging_environment(env) and enabled_flag(
        getattr(env, "WORKDOE_MARKETPLACE_EMAIL_ENABLED", ""),
    )


async def service_activation_record(env, service_slug: str, zone_slug: str):
    if not service_slug or not zone_slug:
        return None
    result = await db_run(
        env,
        """
        SELECT service_zone_activations.*,
               (
                   SELECT COUNT(*)
                   FROM users
                   WHERE users.role = 'contractor'
                     AND users.status = 'active'
                     AND EXISTS (
                         SELECT 1 FROM contractor_service_capabilities
                         WHERE contractor_service_capabilities.contractor_id = users.id
                           AND contractor_service_capabilities.service_slug = ?
                     )
                     AND EXISTS (
                         SELECT 1 FROM contractor_service_zones
                         WHERE contractor_service_zones.contractor_id = users.id
                           AND contractor_service_zones.zone_slug = ?
                     )
               ) AS eligible_contractors
        FROM service_zone_activations
        JOIN service_types
          ON service_types.slug = service_zone_activations.service_slug
         AND service_types.active = 1
        JOIN service_zones
          ON service_zones.slug = service_zone_activations.zone_slug
         AND service_zones.active = 1
        WHERE service_zone_activations.service_slug = ?
          AND service_zone_activations.zone_slug = ?
        LIMIT 1
        """,
        service_slug,
        zone_slug,
        service_slug,
        zone_slug,
    )
    return first_row(result)


def live_service_activation_sql() -> str:
    return """
        AND EXISTS (
            SELECT 1
            FROM service_zone_activations AS activation
            JOIN service_types
              ON service_types.slug = activation.service_slug
             AND service_types.active = 1
            JOIN service_zones
              ON service_zones.slug = activation.zone_slug
             AND service_zones.active = 1
            WHERE activation.service_slug = jobs.service_slug
              AND activation.zone_slug = jobs.service_zone_slug
              AND activation.status = 'active'
              AND activation.allowed_scope != ''
              AND activation.excluded_scope != ''
              AND activation.requirements_summary != ''
              AND activation.approved_at IS NOT NULL
              AND activation.reviewed_at IS NOT NULL
              AND (
                  activation.expires_at IS NULL
                  OR datetime(activation.expires_at) > datetime('now')
              )
              AND (
                  SELECT COUNT(*)
                  FROM users AS eligible_users
                  WHERE eligible_users.role = 'contractor'
                    AND eligible_users.status = 'active'
                    AND EXISTS (
                        SELECT 1 FROM contractor_service_capabilities
                        WHERE contractor_service_capabilities.contractor_id = eligible_users.id
                          AND contractor_service_capabilities.service_slug = jobs.service_slug
                    )
                    AND EXISTS (
                        SELECT 1 FROM contractor_service_zones
                        WHERE contractor_service_zones.contractor_id = eligible_users.id
                          AND contractor_service_zones.zone_slug = jobs.service_zone_slug
                    )
              ) >= activation.minimum_eligible_contractors
        )
    """


def percentage_rate(numerator, denominator) -> int:
    try:
        numerator_value = int(numerator or 0)
        denominator_value = int(denominator or 0)
    except (TypeError, ValueError):
        return 0
    if denominator_value <= 0:
        return 0
    return round((numerator_value / denominator_value) * 100)


def javascript_object(value: dict):
    if PYODIDE_TO_JS is None or JS_OBJECT is None:
        return value
    return PYODIDE_TO_JS(value, dict_converter=JS_OBJECT.fromEntries)


async def public_discovery_limit_status(env) -> int | None:
    limiter = getattr(env, "PUBLIC_DISCOVERY_RATE_LIMITER", None)
    if limiter is None:
        limiter = getattr(env, "WRITE_RATE_LIMITER", None)
    if limiter is None:
        environment = str(getattr(env, "WORKDOE_ENV", "production") or "production").strip().lower()
        return None if environment in {"local", "development", "test"} else 503
    try:
        # Keep public reads separate from write/JWKS keys without identifying visitors.
        result = await limiter.limit(javascript_object({"key": "public-discovery"}))
        allowed = row_value(result, "success")
    except Exception:  # noqa: BLE001 - Cloudflare binding errors may be JS-backed.
        return 503
    if allowed is True:
        return None
    return 429 if allowed is False else 503


def public_discovery_unavailable(method: str, status: int, *, api: bool = False, sign_in: bool = False) -> Response:
    headers = shell_headers("", map_tile_url="")
    headers["Retry-After"] = PUBLIC_DISCOVERY_RETRY_SECONDS
    if api:
        headers["Content-Type"] = "application/json; charset=utf-8"
        message = (
            "Too many project requests. Please try again shortly."
            if status == 429 else "Public jobs are temporarily unavailable."
        )
        body = "" if method == "HEAD" else json.dumps({"ok": False, "error": message})
    else:
        body = "" if method == "HEAD" else unavailable_entry_html(sign_in=sign_in, busy=status == 429)
    return Response(body, status=status, headers=headers)


async def authenticated_write_rate_limit_response(env, user):
    return await worker_write_rate_limit_response(env, authenticated_write_rate_limit_key(row_value(user, "id")))


async def budgeted_clerk_jwks(env, secret_key: str) -> dict:
    limiter = getattr(env, "WRITE_RATE_LIMITER", None)
    if limiter is not None:
        try:
            # Never derive a limiter key from an unverified token or visitor identifier.
            result = await limiter.limit(javascript_object({"key": "clerk-jwks-lookup"}))
            allowed = row_value(result, "success")
        except Exception as exc:
            raise SessionVerificationError("Clerk signing key lookup is temporarily unavailable.") from exc
        if allowed is not True:
            raise SessionVerificationError("Clerk signing key lookup is temporarily unavailable.")
    elif str(getattr(env, "WORKDOE_ENV", "production") or "production").lower() == "production":
        raise SessionVerificationError("Clerk signing key lookup is temporarily unavailable.")
    return await fetch_clerk_jwks(secret_key)


def job_draft_unavailable_response(method: str, *, signed_in: bool = False) -> Response:
    return Response(
        "" if method == "HEAD" else unavailable_job_draft_html(signed_in=signed_in),
        status=503,
        headers={
            **shell_headers("", map_tile_url=""),
            "Referrer-Policy": "no-referrer",
            "Retry-After": "5",
        },
    )


async def worker_write_rate_limit_response(env, key: str):
    limiter = getattr(env, "WRITE_RATE_LIMITER", None)
    environment = str(
        getattr(env, "WORKDOE_ENV", "production") or "production"
    ).lower()
    if limiter is None:
        if environment != "production":
            return None
        return json_response(
            {"ok": False, "error": "Write protection is temporarily unavailable."},
            status=503,
            headers={"Cache-Control": "no-store"},
        )
    try:
        result = await limiter.limit(
            javascript_object({"key": key})
        )
    except Exception as exc:  # noqa: BLE001 - Worker bindings may raise JS-backed errors.
        print(
            json.dumps(
                {
                    "event": "write-rate-limit-check-failed",
                    "error_type": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return json_response(
            {"ok": False, "error": "Write protection is temporarily unavailable."},
            status=503,
            headers={"Cache-Control": "no-store"},
        )
    if bool(row_value(result, "success", False)):
        return None
    return json_response(
        {"ok": False, "error": "Too many changes. Please wait a minute and try again."},
        status=429,
        headers={"Cache-Control": "no-store", "Retry-After": "60"},
    )


def request_header(request, name: str) -> str:
    getter = getattr(request.headers, "get", None)
    if callable(getter):
        value = getter(name)
        if value is not None:
            return str(value)
    return ""


def parse_request_content_length(request) -> int:
    value = request_header(request, "Content-Length")
    if not value:
        return 0
    try:
        return int(value)
    except ValueError:
        return -1


async def request_json_object(request, max_bytes: int = MAX_ONBOARDING_BODY_BYTES) -> dict:
    content_type = request_header(request, "Content-Type").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise OnboardingError("Request body must use application/json.")
    content_length = parse_request_content_length(request)
    if content_length <= 0:
        raise OnboardingError("Request body must include Content-Length.")
    if content_length > max_bytes:
        raise OnboardingError("Request body is too large.")
    try:
        raw_body = await asyncio.wait_for(
            read_json_stream_bytes(
                request.body, max_bytes=content_length, max_chunks=MAX_REQUEST_JSON_BODY_CHUNKS,
                label="Request body",
            ),
            timeout=REQUEST_JSON_BODY_TIMEOUT_SECONDS,
        )
        if len(raw_body) != content_length:
            raise JsonDataError("Request body length does not match Content-Length.")
        data = parse_json_value(raw_body)
    except TimeoutError as exc:
        raise OnboardingError("Request body timed out. Please try again.") from exc
    except JsonDataError as exc:
        raise OnboardingError("Request body must be valid JSON.") from exc
    if not isinstance(data, dict):
        raise OnboardingError("Request body must be a JSON object.")
    return data


async def response_json_object(response, max_bytes: int = MAX_PROVIDER_JSON_BODY_BYTES) -> dict:
    content_length = request_header(response, "Content-Length")
    if content_length:
        try:
            declared = int(content_length)
        except ValueError as exc:
            raise JsonDataError("Provider response length is invalid.") from exc
        if declared < 0 or declared > max_bytes:
            raise JsonDataError("Provider response is too large.")
    raw_body = await read_json_response_bytes(
        response, max_bytes=max_bytes, max_chunks=MAX_PROVIDER_JSON_BODY_CHUNKS,
    )
    value = parse_json_value(raw_body, max_depth=16)
    if not isinstance(value, dict):
        raise JsonDataError("Provider response must be a JSON object.")
    return value


async def fetch_clerk_user(subject: str, secret_key: str, *, transport=None) -> dict:
    options = {}
    try:
        from js import AbortSignal
    except ImportError:  # pragma: no cover - the JS API is only available inside Workers.
        pass
    else:
        options["signal"] = AbortSignal.timeout(int(CLERK_USER_LOOKUP_TIMEOUT_SECONDS * 1000))

    async def exchange():
        response = await (transport or fetch)(
            f"https://api.clerk.com/v1/users/{subject}", method="GET", redirect="manual",
            headers={"Accept": "application/json", "Authorization": f"Bearer {secret_key}"},
            **options,
        )
        raw = await read_json_response_bytes(
            response, max_bytes=MAX_CLERK_USER_BODY_BYTES, max_chunks=MAX_CLERK_USER_BODY_CHUNKS,
        )
        user = parse_json_value(raw, max_depth=16)
        if not isinstance(user, dict):
            raise JsonDataError("Clerk response must be a JSON object.")
        return user

    return await asyncio.wait_for(exchange(), timeout=CLERK_USER_LOOKUP_TIMEOUT_SECONDS)


async def request_form_data(request, max_bytes: int):
    content_type_header = request_header(request, "Content-Type")
    content_type = content_type_header.split(";", 1)[0].strip().lower()
    if content_type not in {
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    }:
        raise OnboardingError("Request body must use form encoding.")
    content_length = parse_request_content_length(request)
    if content_length <= 0:
        raise OnboardingError("Request body must include Content-Length.")
    if content_length > max_bytes:
        raise OnboardingError("Request body is too large.")
    try:
        raw_body = await asyncio.wait_for(
            read_json_stream_bytes(
                request.body, max_bytes=content_length, max_chunks=MAX_DRAFT_FORM_CHUNKS, label="Request body",
            ),
            timeout=DRAFT_FORM_TIMEOUT_SECONDS,
        )
        if len(raw_body) != content_length:
            raise ValueError("Request body length does not match Content-Length.")
        text = raw_body.decode("utf-8", errors="strict")
        if content_type == "multipart/form-data":
            return await parse_draft_multipart(text, content_type_header)
        form: dict[str, str] = {}
        for key, value in parse_qsl(text, keep_blank_values=True, errors="strict", max_num_fields=MAX_DRAFT_FORM_FIELDS):
            form.setdefault(key, value)
        return form
    except Exception as exc:
        raise OnboardingError("Request form could not be read.") from exc


async def parse_draft_multipart(text: str, content_type: str):
    from js import Response as JSResponse

    # Reuse the runtime parser on the already bounded, UTF-8-validated text.
    response = JSResponse.new(text, javascript_object({"headers": {"Content-Type": content_type}}))
    return await response.formData()


async def record_event(
    env,
    event_type: str,
    target_type: str = "",
    target_id: int | None = None,
    payload: dict | None = None,
    status: str = "queued",
) -> None:
    await db_run(
        env,
        """
        INSERT INTO automation_events
            (event_type, target_type, target_id, payload_json, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        event_type,
        target_type,
        target_id,
        json.dumps(payload or {}, sort_keys=True),
        status,
        utc_now(),
    )


async def record_event_best_effort(
    env,
    event_type: str,
    target_type: str = "",
    target_id: int | None = None,
    payload: dict | None = None,
    status: str = "queued",
) -> bool:
    try:
        await record_event(
            env,
            event_type,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
            status=status,
        )
        return True
    except Exception as exc:  # noqa: BLE001 - Worker bindings may raise JS-backed errors.
        print(
            json.dumps(
                {
                    "event": "automation-event-write-failed-after-delivery",
                    "event_type": event_type,
                    "error_type": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return False


async def linked_workdoe_user(env, clerk_subject: str):
    lookup = await db_run(
        env,
        """
        SELECT id, email, role, display_name, company_name, status
        FROM users
        WHERE auth_provider = 'clerk'
          AND external_subject = ?
        LIMIT 1
        """,
        clerk_subject,
    )
    rows = rows_from(lookup)
    return rows[0] if rows else None


def native_email_code_enabled(env) -> bool:
    return (
        getattr(env, "WORKDOE_AUTH_PROVIDER", "") == EMAIL_CODE_AUTH_PROVIDER
        and not is_staging_environment(env)
    )


def staging_clerk_origin(env) -> str:
    if (
        getattr(env, "WORKDOE_AUTH_PROVIDER", "") != "clerk"
        or not str(getattr(env, "CLERK_SECRET_KEY", "") or "").startswith("sk_test_")
        or getattr(env, "CLERK_JWT_KEY", "")
    ):
        return ""
    try:
        return clerk_development_frontend_api_url(getattr(env, "CLERK_PUBLISHABLE_KEY", ""))
    except ValueError:
        return ""


def clerk_production_configuration_ready(env) -> bool:
    if is_staging_environment(env):
        return bool(staging_clerk_origin(env))
    if native_email_code_enabled(env):
        return True
    environment = str(getattr(env, "WORKDOE_ENV", "production") or "production").lower()
    if environment != "production":
        return True
    return is_production_clerk_publishable_key(
        getattr(env, "CLERK_PUBLISHABLE_KEY", "")
    )


async def workdoe_user_by_id(env, user_id: int):
    lookup = await db_run(
        env,
        """
        SELECT id, email, role, display_name, company_name, status
        FROM users
        WHERE id = ?
        LIMIT 1
        """,
        user_id,
    )
    return first_row(lookup)


async def workdoe_user_by_id_from_email(env, email: str):
    lookup = await db_run(
        env,
        """
        SELECT id, email, role, display_name, company_name, status
        FROM users
        WHERE email = ?
        LIMIT 1
        """,
        email,
    )
    return first_row(lookup)


async def ensure_role_profile(env, user, created_at: str) -> None:
    user_id = row_value(user, "id")
    profile_name = (
        row_value(user, "company_name", "")
        or row_value(user, "display_name", "")
        or "Workdoe user"
    )
    if row_value(user, "role") == "client":
        await db_run(
            env,
            """
            INSERT OR IGNORE INTO client_profiles (user_id, organization_name, phone)
            VALUES (?, ?, '')
            """,
            user_id,
            profile_name,
        )
    elif row_value(user, "role") == "contractor":
        await db_run(
            env,
            """
            INSERT OR IGNORE INTO contractor_profiles
                (user_id, business_name, trades, service_area, intro,
                 insurance_status, license_number, years_in_business,
                 website, phone, updated_at)
            VALUES (?, ?, '', 'DMV area', '', '', '', NULL, '', '', ?)
            """,
            user_id,
            profile_name,
            created_at,
        )


async def provision_clerk_account(env, subject: str, payload: dict, created_at: str):
    results = await db_batch(env, (
        (
            """
            INSERT INTO users
                (email, password_hash, role, display_name, company_name,
                 status, email_verified, auth_provider, external_subject, created_at)
            VALUES (?, 'clerk-managed', ?, ?, ?, 'active', 1, 'clerk', ?, ?)
            ON CONFLICT DO NOTHING
            """,
            (payload["email"], payload["role"], payload["display_name"], payload["company_name"], subject, created_at),
        ),
        # Audit the new identity once; changes() refers to the immediately preceding insert.
        (
            """
            INSERT INTO automation_events
                (event_type, target_type, target_id, payload_json, status, created_at)
            SELECT 'clerk-onboarding-linked', 'user', id, ?, 'processed', ?
            FROM users
            WHERE auth_provider = 'clerk' AND external_subject = ? AND changes() = 1
            """,
            (json.dumps({"role": payload["role"], "created": True}, sort_keys=True), created_at, subject),
        ),
        (
            """
            INSERT INTO client_profiles (user_id, organization_name, phone)
            SELECT id, COALESCE(NULLIF(company_name, ''), NULLIF(display_name, ''), 'Workdoe user'), ''
            FROM users
            WHERE auth_provider = 'clerk' AND external_subject = ? AND status = 'active' AND role = 'client'
            ON CONFLICT(user_id) DO NOTHING
            """,
            (subject,),
        ),
        (
            """
            INSERT INTO contractor_profiles
                (user_id, business_name, trades, service_area, intro,
                 insurance_status, license_number, years_in_business, website, phone, updated_at)
            SELECT id, COALESCE(NULLIF(company_name, ''), NULLIF(display_name, ''), 'Workdoe user'),
                   '', 'DMV area', '', '', '', NULL, '', '', ?
            FROM users
            WHERE auth_provider = 'clerk' AND external_subject = ? AND status = 'active' AND role = 'contractor'
            ON CONFLICT(user_id) DO NOTHING
            """,
            (created_at, subject),
        ),
        (
            """
            SELECT id, role, display_name, company_name, status
            FROM users
            WHERE auth_provider = 'clerk' AND external_subject = ?
            LIMIT 1
            """,
            (subject,),
        ),
    ))
    if len(results) != 5 or any(row_value(result, "success") is not True for result in results):
        raise ValueError("Unsuccessful D1 Clerk provisioning batch.")
    return first_row(results[4]), d1_change_count(results[0]) == 1


def workdoe_user_json(user) -> dict:
    return {
        "id": row_value(user, "id"),
        "role": row_value(user, "role"),
        "display_name": row_value(user, "display_name"),
        "company_name": row_value(user, "company_name", ""),
        "status": row_value(user, "status"),
    }


def auth_redirect_for_user(user, requested_path: str | None) -> str:
    fallback = dashboard_path_for_user(user)
    requested = safe_next_path(requested_path, fallback=fallback)
    requested_route = urlparse(requested).path
    role = row_value(user, "role")
    if requested_route == "/dashboard":
        return fallback
    if role == "client" and (
        requested_route == "/jobs/new" or requested_route.startswith(("/client/", "/messages/"))
    ):
        return requested
    if role == "contractor" and (
        requested_route == "/leads" or requested_route.startswith(("/jobs/", "/contractor/", "/messages/"))
    ):
        return requested
    if role == "admin" and requested_route.startswith("/admin"):
        return requested
    return fallback


def first_row(result):
    rows = rows_from(result)
    return rows[0] if rows else None


def public_https_redirect_url(request_url: str) -> str:
    parsed = urlparse(request_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "http" or host not in PUBLIC_HTTPS_HOSTS:
        return ""
    return parsed._replace(scheme="https", netloc=host).geturl()


def is_static_asset_path(path: str) -> bool:
    return path in STATIC_ASSET_PATHS or path.startswith("/vendor/")


def workspace_mode(env) -> str:
    # A staging rehearsal starts sealed unless an operator explicitly opens it.
    default_mode = "sealed" if is_staging_environment(env) else "normal"
    value = getattr(env, "WORKDOE_WRITE_MODE", default_mode)
    return value if value in ("normal", "paused") else "sealed"


def workspace_tile_configuration(env) -> tuple[str, str]:
    mode = getattr(env, "WORKDOE_MAP_MODE", None)
    if is_staging_environment(env):
        # Staging can qualify the local area asset, never a third-party tile provider.
        return map_tile_configuration(map_mode="area" if mode == "area" else "list")
    demo_default = None if getattr(env, "WORKDOE_ENV", "production") == "local" else ""
    return map_tile_configuration(
        getattr(env, "WORKDOE_MAP_TILE_URL", demo_default),
        getattr(env, "WORKDOE_MAP_TILE_ATTRIBUTION", demo_default),
        map_mode=mode,
    )


def recovery_request_allowed(mode: str, method: str, path: str) -> bool:
    if mode == "paused" and method == "POST" and path in {"/logout", "/api/auth/logout"}:
        return True
    safe_routes = RECOVERY_SAFE_ROUTES if mode == "sealed" else WRITE_PAUSE_PUBLIC_ROUTES
    return method in {"GET", "HEAD"} and (path in safe_routes or is_static_asset_path(path))


def recovery_mode_header(mode: str) -> dict[str, str]:
    return {} if mode == "normal" else {"X-Workdoe-Mode": "sealed" if mode == "sealed" else "read-only"}


def recovery_response(mode: str, method: str, path: str) -> Response:
    headers = {
        "Cache-Control": "no-store",
        "Referrer-Policy": "no-referrer",
        "Retry-After": str(RECOVERY_RETRY_SECONDS),
        **recovery_mode_header(mode),
    }
    sealed = mode == "sealed"
    if method != "HEAD" and (path.startswith("/api/") or path == "/clerk/webhook" or is_clerk_proxy_path(path)):
        error = "Workdoe is temporarily unavailable." if sealed else "Workdoe is temporarily read-only."
        return json_response({"ok": False, "error": error}, status=503, headers=headers)
    return Response(
        "" if method == "HEAD" else recovery_workspace_html(sealed=sealed),
        status=503,
        headers={**app_shell_headers(include_dialog_forms=False), **headers},
    )


def reject_public_discovery_request(method: str, path: str, query: str) -> Response | None:
    api = path == "/api/jobs/open"
    read_request = method in {"GET", "HEAD"}
    rejection = public_query_envelope_rejection(query) if read_request else None
    if rejection is None and (read_request or not api):
        return None
    headers = {
        "Content-Type": "application/json; charset=utf-8" if api else "text/plain; charset=utf-8",
        "Cache-Control": "no-store",
        "Referrer-Policy": "no-referrer",
        "Strict-Transport-Security": HSTS_HEADER,
        "X-Content-Type-Options": "nosniff",
    }
    if rejection is None:
        headers["Allow"] = ", ".join(PUBLIC_DISCOVERY_API_METHODS)
        if method == "OPTIONS":
            return Response("", status=200, headers=headers)
        return json_response({"ok": False, "error": "Method not allowed."}, status=405, headers=headers)
    status, message = rejection
    if method == "HEAD":
        body = ""
    else:
        body = json.dumps({"ok": False, "error": message}) if api else message
    return Response(body, status=status, headers=headers)


def requests_missing_page_document(request, path: str) -> bool:
    segments = path.strip("/").split("/")
    if segments[0] in {"api", "media", "static", "vendor", "clerk", "__clerk", ".well-known"} or "." in segments[-1]:
        return False
    return (
        request.method in {"GET", "HEAD"}
        and request_header(request, "Sec-Fetch-Mode") in {"", "navigate"}
        and request_header(request, "Sec-Fetch-Dest") in {"", "document"}
        and "text/html" in {value.strip().lower() for value in request_header(request, "Accept").split(",")}
    )


def private_media_response(body, *, status: int, headers: dict[str, str] | None = None) -> Response:
    return Response(
        body,
        status=status,
        headers={"Cache-Control": "no-store", **PRIVATE_MEDIA_EMBEDDING_HEADERS, **(headers or {})},
    )


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        staging = is_staging_environment(self.env)
        if staging and not staging_request_allowed(
            request.url,
            getattr(self.env, "WORKDOE_PUBLIC_URL", None),
            getattr(self.env, "WORKDOE_DOMAIN", None),
        ):
            return Response(
                "" if request.method == "HEAD" else "Not found.",
                status=404,
                headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
            )
        redirect_url = public_https_redirect_url(request.url)
        if redirect_url:
            return Response(
                "",
                status=308,
                headers={
                    "Location": redirect_url,
                    "Cache-Control": "no-store",
                    "Referrer-Policy": "no-referrer",
                },
            )

        parsed_request = urlparse(request.url)
        path = parsed_request.path
        raw_path = urlsplit(request.url).path
        mode = workspace_mode(self.env)
        if mode != "normal" and (
            path != raw_path or not recovery_request_allowed(mode, request.method, path)
        ):
            return recovery_response(mode, request.method, path)

        if staging and (is_clerk_proxy_path(path) or path in {
            "/clerk/webhook", "/api/auth/code/request", "/api/auth/code/verify",
        }):
            return Response(
                "" if request.method == "HEAD" else '{"ok": false, "error": "Not found."}',
                status=404,
                headers={
                    "Cache-Control": "no-store",
                    "Content-Type": "application/json; charset=utf-8",
                    "Strict-Transport-Security": HSTS_HEADER,
                    "X-Content-Type-Options": "nosniff",
                },
            )

        # urlparse strips final-segment parameters that an exact-path edge rule still sees.
        if path in PUBLIC_DISCOVERY_ROUTES and path != raw_path:
            return Response(
                "" if request.method == "HEAD" else json.dumps({"ok": False, "error": "Not found."}),
                status=404,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Cache-Control": "no-store",
                    "Referrer-Policy": "no-referrer",
                    "Strict-Transport-Security": HSTS_HEADER,
                    "X-Content-Type-Options": "nosniff",
                },
            )

        if path in {"/", "/api/jobs/open"}:
            rejected = reject_public_discovery_request(request.method, path, parsed_request.query)
            if rejected is not None:
                return rejected

        if not same_origin_api_write_allowed(
            request.method,
            path,
            request_header(request, WORKDOE_REQUEST_HEADER),
        ):
            return json_response(
                {"ok": False, "error": "Same-origin request required."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )

        if (
            hasattr(self.env, "DB")
            and authenticated_write_rate_limit_required(request.method, path)
        ):
            rate_limit_user = await self.optional_workdoe_user(request)
            if rate_limit_user:
                rate_limit_response = await authenticated_write_rate_limit_response(
                    self.env,
                    rate_limit_user,
                )
                if rate_limit_response is not None:
                    return rate_limit_response

        if path.startswith("/static/"):
            asset_path = path.removeprefix("/static")
            cacheable = (
                request.method in {"GET", "HEAD"}
                and is_static_asset_path(asset_path)
                and not (parsed_request.query or parsed_request.params)
            )
            return Response(
                "",
                status=308,
                headers={
                    "Location": parsed_request._replace(path=asset_path).geturl(),
                    "Cache-Control": "public, max-age=86400" if cacheable else "no-store",
                    "Referrer-Policy": "no-referrer",
                    "Strict-Transport-Security": HSTS_HEADER,
                },
            )

        if path in {"/health", "/healthz"}:
            return json_response(
                {
                    "ok": True,
                    "service": "workdoe-cloudflare-worker",
                    "domain": getattr(self.env, "WORKDOE_DOMAIN", "workdoe.com"),
                    "auth_provider": getattr(
                        self.env,
                        "WORKDOE_AUTH_PROVIDER",
                        EMAIL_CODE_AUTH_PROVIDER,
                    ),
                    "login_mode": getattr(
                        self.env,
                        "WORKDOE_LOGIN_MODE",
                        "same_domain_email_code",
                    ),
                    "bindings": {
                        "d1": hasattr(self.env, "DB"),
                        "email_sender": hasattr(self.env, "EMAIL"),
                        "email_queue": hasattr(self.env, "EMAIL_QUEUE"),
                        "media_queue": hasattr(self.env, "MEDIA_QUEUE"),
                        "r2_media": hasattr(self.env, "MEDIA"),
                        "write_rate_limiter": hasattr(self.env, "WRITE_RATE_LIMITER"),
                    },
                },
                headers={"Cache-Control": "no-store", **recovery_mode_header(mode)},
            )

        if path == "/post-project":
            return await self.public_job_draft(request)

        if path in ENTRY_ROUTES:
            return await self.entry_shell(request, path)

        if is_clerk_proxy_path(path) and not native_email_code_enabled(self.env):
            return await self.clerk_frontend_api_proxy(request)

        if is_public_contractor_profile_route(path):
            return await self.contractor_profile_page(request, path)

        if path == "/safety":
            return await self.safety_page(request)

        if path in {"/privacy", "/terms"}:
            return await self.public_trust_page(request, path)

        if path in {"/robots.txt", "/sitemap.xml", "/.well-known/security.txt"}:
            return await self.public_discovery_file(request, path)

        if is_app_shell_route(path):
            return await self.app_shell(request, path)

        if path == "/api/jobs/open":
            return await self.public_open_jobs(request)

        if path == "/api/client/jobs":
            return await self.client_jobs(request)

        if path == "/api/client/profile":
            return await self.client_profile_api(request)

        if path == "/api/client/locations" or (
            path.startswith("/api/client/locations/") and path.endswith("/delete")
        ):
            return await self.client_saved_locations_api(request, path)

        if path == "/api/client/templates" or (
            path.startswith("/api/client/templates/") and path.endswith("/delete")
        ):
            return await self.client_project_templates_api(request, path)

        if path.startswith("/api/client/jobs/") and path.endswith("/requests"):
            return await self.client_job_requests(request, path)

        if path == "/api/contractor/leads":
            return await self.contractor_leads(request)

        if path == "/api/contractor/bids":
            return await self.contractor_bids(request)

        if path == "/api/contractor/proposal-templates" or (
            path.startswith("/api/contractor/proposal-templates/")
            and path.endswith("/delete")
        ):
            return await self.contractor_proposal_templates_api(request, path)

        if path == "/api/jobs":
            return await self.create_job(request)

        if path.startswith("/api/jobs/") and path.endswith("/update"):
            return await self.update_job(request, path)

        if path == "/api/contractor/profile":
            return await self.contractor_profile_api(request)

        if path in {
            "/api/contractor/preferences",
            "/api/contractor/preferences/availability",
            "/api/contractor/preferences/lead-view",
        }:
            return await self.contractor_preferences_api(request, path)

        if path == "/api/contractor/credentials" or (
            path.startswith("/api/contractor/credentials/")
            and path.endswith("/remove")
        ):
            return await self.contractor_credentials_api(request, path)

        if path.startswith("/api/contractors/"):
            return await self.public_contractor_profile(request, path)

        if path == "/api/reports":
            return await self.create_report(request)

        if path.startswith("/api/repeat-invitations/"):
            return await self.respond_repeat_invitation(request, path)

        if path.startswith("/api/reviews/"):
            return await self.match_review_action(request, path)

        if path.startswith("/api/admin/"):
            return await self.admin_moderation_action(request, path)

        if path.startswith("/api/jobs/") and path.endswith("/request"):
            return await self.create_match_request(request, path)

        if path.startswith("/api/jobs/") and path.endswith("/extend-bids"):
            return await self.extend_job_bids(request, path)

        if path.startswith("/api/jobs/") and path.endswith("/quality-feedback"):
            return await self.submit_job_quality_feedback(request, path)

        if path.startswith("/api/jobs/") and (
            path.endswith(("/close", "/reopen"))
        ):
            return await self.update_job_status(request, path)

        if path.startswith("/api/jobs/"):
            return await self.job_detail(request, path)

        if path.startswith("/api/match-requests/") and path.endswith("/complete"):
            return await self.confirm_match_completion(request, path)

        if path.startswith("/api/match-requests/") and path.endswith("/review"):
            return await self.create_match_review(request, path)

        if path.startswith("/api/match-requests/"):
            return await self.decide_match_request(request, path)

        if path == "/api/messages/threads" or path.startswith("/api/messages/threads/"):
            return await self.message_threads_api(request, path)

        if path == "/api/auth/session":
            return await self.auth_session(request)

        if path == "/api/auth/code/request":
            return await self.request_auth_code(request)

        if path == "/api/auth/code/verify":
            return await self.verify_auth_code(request)

        if path == "/api/auth/logout":
            return await self.auth_logout(request)

        if path == "/logout":
            return await self.auth_logout(request)

        if path == "/api/auth/onboard":
            return await self.auth_onboard(request)

        if path.startswith(("/media/jobs/", "/media/contractors/")):
            return await self.private_media(request, path)

        if path.startswith(("/api/media/jobs/", "/api/media/contractors/")):
            return await self.upload_private_media(request, path)

        if path == "/clerk/webhook":
            return await self.handle_clerk_webhook(request)

        if is_static_asset_path(path) and hasattr(self.env, "ASSETS"):
            return await self.env.ASSETS.fetch(request)

        if requests_missing_page_document(request, path):
            return Response(
                "" if request.method == "HEAD" else missing_page_html(),
                status=404,
                headers={**app_shell_headers(include_dialog_forms=False), "Referrer-Policy": "no-referrer"},
            )

        return json_response(
            {"ok": False, "error": "Not found."},
            status=404,
            headers={"Cache-Control": "no-store"},
        )

    async def clerk_frontend_api_proxy(self, request):
        origin = request.headers.get("Origin")
        if not clerk_proxy_origin_allowed(
            request.url,
            None if origin is None else str(origin),
            allow_loopback=getattr(self.env, "WORKDOE_ENV", "production") == "local",
        ):
            headers = {"Cache-Control": "no-store"}
            if request.method == "HEAD":
                return Response("", status=403, headers={**headers, "Strict-Transport-Security": HSTS_HEADER})
            return json_response({"ok": False, "error": "Sign-in request origin is not allowed."}, 403, headers)
        if not clerk_production_configuration_ready(self.env):
            return json_response(
                {"ok": False, "error": "Sign-in is temporarily unavailable."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            plan = clerk_proxy_request_plan(
                request.url,
                request.headers,
                secret_key=getattr(self.env, "CLERK_SECRET_KEY", ""),
                method=request.method,
                proxy_url=getattr(
                    self.env,
                    "CLERK_PROXY_URL",
                    getattr(self.env, "CLERK_FRONTEND_API_URL", ""),
                ),
                fapi_url=getattr(self.env, "CLERK_FAPI", ""),
                public_url=getattr(self.env, "WORKDOE_PUBLIC_URL", "https://workdoe.com"),
            )
        except ClerkProxyError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=exc.status,
                headers={"Cache-Control": "no-store"},
            )

        fetch_options = {
            "method": request.method,
            "headers": plan["headers"],
            "redirect": "manual",
        }
        if request.method not in {"GET", "HEAD"}:
            fetch_options["body"] = request.body
        try:
            from js import AbortController
        except ImportError:
            controller = None
        else:
            controller = AbortController.new()
            fetch_options["signal"] = controller.signal
        async def exchange():
            upstream = await fetch(plan["url"], **fetch_options)
            if not plan["package_path"]:
                return upstream
            body, headers = await verified_clerk_package(plan["package_path"], upstream, method=request.method)
            return Response(body, headers={**headers, "Strict-Transport-Security": HSTS_HEADER})

        try:
            # Auth bodies remain streamed; public package bodies must verify within the same deadline.
            return await asyncio.wait_for(exchange(), CLERK_PROXY_RESPONSE_TIMEOUT_SECONDS)
        except TimeoutError:
            if controller is not None:
                controller.abort()
            reason, status = "timeout", 504
        except asyncio.CancelledError:
            if controller is not None:
                controller.abort()
            raise
        except ClerkProxyError as exc:
            if controller is not None:
                controller.abort()
            reason, status = "package-response", exc.status
        except Exception:  # noqa: BLE001 - Worker fetch may raise JS-backed transport errors.
            if controller is not None:
                controller.abort()
            reason, status = "transport", 502
        print(json.dumps({"event": "clerk-proxy-upstream-failed", "reason": reason}))
        headers = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"}
        if request.method == "HEAD":
            return Response("", status=status, headers={**headers, "Strict-Transport-Security": HSTS_HEADER})
        return json_response({"ok": False, "error": "Sign-in is temporarily unavailable."}, status, headers)

    async def entry_shell(self, request, path: str):
        if request.method not in {"GET", "HEAD"}:
            return json_response(
                {"ok": False, "error": "Entry pages accept GET only."},
                status=405,
                headers={"Allow": "GET, HEAD"},
            )

        params = parse_qs(urlparse(request.url).query)
        account_entry = path != "/"
        if account_entry and not clerk_production_configuration_ready(self.env):
            return public_discovery_unavailable(request.method, 503, sign_in=True)
        embedded = account_entry and first_query_value(params, "embed") == "1"
        project_id = selected_job_id(params) if embedded and request.method == "GET" else ""
        filters = entry_job_filters(params)
        try:
            viewport = None if embedded else parse_public_viewport(params)
        except PublicJobQueryError:
            viewport = None
        rows = []
        page_snapshot = None
        discovery_status = None
        if hasattr(self.env, "DB") and (not embedded or project_id.isdecimal()):
            discovery_status = await public_discovery_limit_status(self.env)
            if discovery_status is None:
                try:
                    rows, _, truncated = await read_public_project_page(
                        self.env, filters, viewport, limit=ENTRY_JOB_LIMIT, source="page",
                    )
                    page_snapshot = {"viewport": viewport, "truncated": truncated}
                except Exception:  # noqa: BLE001 - D1 failures cross the Worker binding boundary.
                    discovery_status = 503
        if discovery_status and not account_entry:
            return public_discovery_unavailable(request.method, discovery_status)
        if not discovery_status and page_snapshot is None:
            rows = guest_project_rows(rows, filters, limit=ENTRY_JOB_LIMIT, viewport=viewport)
        auth_provider = getattr(
            self.env,
            "WORKDOE_AUTH_PROVIDER",
            EMAIL_CODE_AUTH_PROVIDER,
        )
        staging = is_staging_environment(self.env)
        if staging:
            auth_provider = "clerk"
        native_auth = auth_provider == EMAIL_CODE_AUTH_PROVIDER
        clerk_frontend_api_url = (
            ""
            if native_auth
            else getattr(
                self.env,
                "CLERK_FRONTEND_API_URL",
                "https://workdoe.com/__clerk",
            )
        )
        clerk_publishable_key = getattr(self.env, "CLERK_PUBLISHABLE_KEY", "")
        if staging:
            clerk_frontend_api_url = "/__clerk"
            if not staging_clerk_origin(self.env):
                clerk_publishable_key = ""
        map_tile_url, map_tile_attribution = ("", "") if discovery_status else workspace_tile_configuration(self.env)
        html = build_entry_shell_html(
            path,
            params,
            rows,
            clerk_publishable_key,
            clerk_frontend_api_url,
            auth_provider=auth_provider,
            turnstile_site_key=getattr(self.env, "WORKDOE_TURNSTILE_SITE_KEY", ""),
            map_tile_url=map_tile_url,
            map_tile_attribution=map_tile_attribution,
            map_mode="area" if map_tile_url == AREA_MAP_ASSET else None,
            marketplace_unavailable=bool(discovery_status),
            page_snapshot=page_snapshot,
            access_protected_map=staging,
        )
        body = "" if request.method == "HEAD" else html
        return Response(
            body,
            status=200,
            headers=shell_headers(
                clerk_frontend_api_url,
                include_turnstile=native_auth
                and path in {"/start", "/create-account", "/post-project", "/login"}
                and bool(getattr(self.env, "WORKDOE_TURNSTILE_SITE_KEY", "")),
                clerk_publishable_key=clerk_publishable_key,
                map_tile_url=map_tile_url if first_query_value(params, "embed") != "1" else "",
            ),
        )

    async def public_job_draft(self, request):
        if request.method not in {"GET", "HEAD", "POST"}:
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET, HEAD, POST", "Cache-Control": "no-store"},
            )
        if request.method == "POST" and not same_origin_form_write_allowed(
            request.url,
            origin=request_header(request, "Origin"),
            referer=request_header(request, "Referer"),
            fetch_site=request_header(request, "Sec-Fetch-Site"),
        ):
            return Response(
                unavailable_form_html(), status=403, headers=app_shell_headers(include_dialog_forms=False),
            )
        if not hasattr(self.env, "DB"):
            return Response(
                "Workdoe data storage is not configured.",
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if user and row_value(user, "role") != "client":
            return Response(
                "Consumer accounts post projects. This account keeps its contractor role.",
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        params = parse_qs(urlparse(request.url).query)
        requested_family = first_query_value(params, "family")
        if requested_family not in GROUP_BY_SLUG:
            requested_family = ""
        requested_service = first_query_value(params, "service")
        selected_service = SERVICE_BY_SLUG.get(requested_service)
        if not selected_service or requested_family and selected_service["group_slug"] != requested_family:
            requested_service = ""
        elif not requested_family:
            requested_family = selected_service["group_slug"]
        if user and request.method in {"GET", "HEAD"}:
            location = "/jobs/new"
            requested_selection = {
                key: value
                for key, value in {
                    "family": requested_family,
                    "service": requested_service,
                }.items()
                if value
            }
            if requested_selection:
                location += "?" + urlencode(requested_selection)
            return Response(
                "",
                status=303,
                headers={"Location": location, "Cache-Control": "no-store"},
            )

        try:
            draft = None if request.method == "POST" else await job_draft_for_request(self.env, request)
        except JobDraftReadError:
            return job_draft_unavailable_response(request.method)
        form = job_draft_form(draft)
        if not draft and requested_family:
            form["service_group_slug"] = requested_family
        if not draft and requested_service:
            form.update(service_selection(requested_service, requested_family))
        errors: list[str] = []
        save_failure_status = None
        retry_after = None
        if request.method == "POST":
            try:
                form_data = await request_form_data(
                    request,
                    max_bytes=MAX_JOB_POST_BODY_BYTES,
                )
            except OnboardingError as exc:
                errors.append(str(exc))
            else:
                payload = {
                    key: str(form_data.get(key) or "")
                    for key in (
                        "title",
                        "category",
                        "service_group_slug",
                        "service_slug",
                        "project_setting",
                        "license_preference",
                        "service_policy_acknowledgement",
                        "desired_date",
                        "city",
                        "state",
                        "zip_code",
                        "budget_min",
                        "budget_max",
                        "description",
                        "cf-turnstile-response",
                    ) + scope_answer_field_names()
                }
                form = cleaned_job_payload(payload)
                errors = validate_job_payload(form)
                if not errors:
                    try:
                        await verify_turnstile_for_request(
                            self.env,
                            request,
                            payload,
                            action="job-draft",
                        )
                    except TurnstileError as exc:
                        errors.append(str(exc))
                if not errors:
                    # Guests share a per-location draft budget without an IP-based key.
                    limit_key = (
                        authenticated_write_rate_limit_key(row_value(user, "id"))
                        if user else "workdoe-guest-project-draft"
                    )
                    limit_response = await worker_write_rate_limit_response(self.env, limit_key)
                    if limit_response is not None:
                        save_failure_status = limit_response.status
                        if save_failure_status == 429:
                            retry_after = "60"
                            errors.append("Too many draft saves. Wait a minute and try again.")
                        else:
                            retry_after = "5"
                            errors.append("Draft saving is temporarily unavailable. Please try again.")
                if not errors and enforce_service_activation(self.env):
                    zone_slug = job_zone_slug(form["city"], form["state"], form["zip_code"])
                    activation = await service_activation_record(
                        self.env, form["service_slug"], zone_slug
                    )
                    if not activation_is_live(activation):
                        errors.append(ACTIVATION_NOT_OPEN_MESSAGE)
                if not errors:
                    try:
                        token = await save_job_draft_record(self.env, request, form)
                    except Exception:  # noqa: BLE001 - D1 failures cross the Worker binding boundary.
                        save_failure_status = 503
                        retry_after = "5"
                        errors.append("We could not confirm your draft was saved. Please try again.")
                    else:
                        return Response(
                            "",
                            status=303,
                            headers={
                                "Location": (
                                    "/jobs/new"
                                    if user
                                    else "/create-account?intent=post-job&draft=saved"
                                ),
                                "Set-Cookie": job_draft_cookie(token),
                                "Cache-Control": "no-store",
                            },
                        )

        embedded = embedded_dialog_request(request)
        html = public_job_draft_html(
            form,
            errors,
            getattr(self.env, "WORKDOE_TURNSTILE_SITE_KEY", ""),
            embedded=embedded,
            save_unavailable=save_failure_status is not None,
        )
        headers = app_shell_headers(
            include_turnstile=bool(getattr(self.env, "WORKDOE_TURNSTILE_SITE_KEY", "")),
        )
        if retry_after:
            headers["Retry-After"] = retry_after
        return Response(
            "" if request.method == "HEAD" else html,
            status=save_failure_status or (400 if errors else 200),
            headers=headers,
        )

    async def safety_page(self, request):
        if request.method not in {"GET", "HEAD"}:
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET, HEAD", "Cache-Control": "no-store"},
            )
        html = safety_page_html()
        return Response(
            "" if request.method == "HEAD" else html,
            status=200,
            headers=app_shell_headers(),
        )

    async def public_trust_page(self, request, path: str):
        if request.method not in {"GET", "HEAD"}:
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET, HEAD", "Cache-Control": "no-store"},
            )
        renderer = privacy_page_html if path == "/privacy" else terms_page_html
        return Response(
            "" if request.method == "HEAD" else renderer(),
            status=200,
            headers=app_shell_headers(),
        )

    async def public_discovery_file(self, request, path: str):
        if request.method not in {"GET", "HEAD"}:
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET, HEAD", "Cache-Control": "no-store"},
            )
        body, content_type = {
            "/robots.txt": (public_robots_txt(), "text/plain; charset=utf-8"),
            "/sitemap.xml": (public_sitemap_xml(), "application/xml; charset=utf-8"),
            "/.well-known/security.txt": (
                public_security_txt(),
                "text/plain; charset=utf-8",
            ),
        }[path]
        return Response(
            "" if request.method == "HEAD" else body,
            status=200,
            headers={
                "Cache-Control": "public, max-age=3600",
                "Content-Type": content_type,
                "X-Content-Type-Options": "nosniff",
            },
        )

    async def app_shell(self, request, path: str):
        if request.method not in {"GET", "HEAD"}:
            return json_response(
                {"ok": False, "error": "App pages accept GET only."},
                status=405,
                headers={"Allow": "GET, HEAD"},
            )
        if not hasattr(self.env, "DB"):
            return Response(
                "Workdoe data storage is not configured.",
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            parsed_url = urlparse(request.url)
            next_path = path + (f"?{parsed_url.query}" if parsed_url.query else "")
            return Response(
                "",
                status=302,
                headers={"Location": app_login_url(next_path), "Cache-Control": "no-store"},
            )
        if row_value(user, "status") != "active":
            return Response(
                "This Workdoe account is not active.",
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        if path == "/dashboard":
            return Response(
                "",
                status=302,
                headers={
                    "Location": dashboard_path_for_user(user),
                    "Cache-Control": "no-store",
                },
            )

        role = row_value(user, "role")
        expected_role = {
            "/client/dashboard": "client",
            "/contractor/dashboard": "contractor",
        }.get(path)
        if expected_role and role != expected_role:
            return Response(
                "" if request.method == "HEAD" else dashboard_access_html(user, expected_role),
                status=403,
                headers=app_shell_headers(),
            )

        params = parse_qs(urlparse(request.url).query)
        embedded = embedded_dialog_request(request)
        html = ""
        include_map = False
        map_tile_url = ""
        include_turnstile = False
        include_clerk = False
        if (
            role in {"client", "contractor"}
            and not path.startswith("/messages/")
        ):
            user = user_with_unread_message_count(
                user,
                await unread_message_count_for_user(
                    self.env,
                    row_value(user, "id"),
                    role,
                ),
            )

        if path == "/client/dashboard" and role == "client":
            view = normalize_client_job_view(first_query_value(params, "view"))
            rows = await client_jobs_for_user(self.env, row_value(user, "id"))
            html = client_dashboard_html(user, client_jobs_payload(rows, view))
        elif path == "/account" and role in {"client", "contractor", "admin"}:
            auth_provider = getattr(self.env, "WORKDOE_AUTH_PROVIDER", "clerk")
            clerk_publishable_key = getattr(self.env, "CLERK_PUBLISHABLE_KEY", "")
            clerk_frontend_api_url = getattr(
                self.env,
                "CLERK_FRONTEND_API_URL",
                "https://workdoe.com/__clerk",
            )
            include_clerk = bool(
                auth_provider == "clerk"
                and str(clerk_publishable_key or "").strip()
                and str(clerk_frontend_api_url or "").strip()
            )
            html = account_security_html(
                user,
                clerk_publishable_key=clerk_publishable_key,
                clerk_frontend_api_url=clerk_frontend_api_url,
                auth_provider=auth_provider,
            )
        elif path == "/client/profile" and role == "client":
            profile = await ensure_client_profile(self.env, user, utc_now())
            locations = await client_saved_locations_for_user(
                self.env,
                row_value(user, "id"),
            )
            templates = await client_project_templates_for_user(
                self.env,
                row_value(user, "id"),
            )
            source_jobs = await client_template_source_jobs_for_user(
                self.env,
                row_value(user, "id"),
            )
            html = client_profile_html(
                user,
                client_profile_response(profile),
                [saved_location_response(location) for location in locations],
                [project_template_response(item) for item in templates],
                source_jobs,
                parse_url_record_id(first_query_value(params, "source_job")),
                email_available=marketplace_email_enabled(self.env),
            )
        elif path == "/client/requests" and role == "client":
            rows = await client_jobs_for_user(self.env, row_value(user, "id"))
            html = client_request_inbox_html(user, client_jobs_payload(rows, "review"))
        elif path == "/contractor/dashboard" and role == "contractor":
            view = normalize_contractor_bid_view(first_query_value(params, "bids"))
            rows = await contractor_bids_for_user(self.env, row_value(user, "id"))
            public_credentials = public_credential_responses(
                await contractor_credentials_for_user(
                    self.env,
                    row_value(user, "id"),
                )
            )
            dashboard_payload = contractor_bids_payload(
                rows,
                view,
                len(public_credentials),
                sum(
                    1
                    for credential in public_credentials
                    if credential.get("credential_type") == "trade_license"
                ),
            )
            profile = await contractor_profile_for_user(
                self.env,
                row_value(user, "id"),
            )
            dashboard_payload["profile"] = contractor_profile_response(profile or {})
            dashboard_payload["repeat_invitations"] = await contractor_repeat_invitations(
                self.env,
                row_value(user, "id"),
            )
            dashboard_payload["reviews_by_request"] = await match_reviews_for_request_ids(
                self.env,
                [int(row_value(item, "id", 0) or 0) for item in rows],
            )
            dashboard_payload["proposal_templates"] = [
                proposal_template_response(item)
                for item in await contractor_proposal_templates_for_user(
                    self.env, row_value(user, "id")
                )
            ]
            dashboard_payload["proposal_template_limit"] = PROPOSAL_TEMPLATE_LIMIT
            html = contractor_dashboard_html(user, dashboard_payload)
        elif path == "/leads" and role == "contractor":
            filters = contractor_lead_filters_from_query(params)
            view = normalize_contractor_lead_view(first_query_value(params, "view"))
            limit = parse_contractor_lead_limit(first_query_value(params, "limit"))
            rows = await contractor_leads_for_user(
                self.env,
                row_value(user, "id"),
                filters,
                limit,
            )
            market_fit = await contractor_market_fit_for_user(
                self.env,
                row_value(user, "id"),
            )
            lead_payload = contractor_leads_payload(rows, filters, view, **market_fit)
            preferences_row = await contractor_preferences_for_user(
                self.env,
                row_value(user, "id"),
            )
            lead_payload["preferences"] = contractor_preferences_response(preferences_row)
            lead_payload["saved_lead_view_url"] = saved_lead_view_url(preferences_row)
            map_tile_url, map_tile_attribution = workspace_tile_configuration(self.env)
            html = lead_board_html(
                user,
                lead_payload,
                map_tile_url=map_tile_url,
                map_tile_attribution=map_tile_attribution,
                map_mode="area" if map_tile_url == AREA_MAP_ASSET else None,
                email_available=marketplace_email_enabled(self.env),
                access_protected_map=is_staging_environment(self.env),
            )
            include_map = bool(map_tile_url)
        elif path == "/jobs/new" and role == "client":
            include_turnstile = bool(getattr(self.env, "WORKDOE_TURNSTILE_SITE_KEY", ""))
            try:
                draft = await job_draft_for_request(self.env, request)
            except JobDraftReadError:
                return job_draft_unavailable_response(request.method, signed_in=True)
            repeat_job = None
            repeat_invitation = None
            project_template = None
            saved_location = None
            repeat_id = parse_url_record_id(first_query_value(params, "repeat"))
            if not draft and repeat_id:
                candidate = await job_for_detail(self.env, repeat_id)
                if can_update_job(user, candidate):
                    repeat_job = dict(candidate)
                    repeat_job["desired_date"] = ""
            invite_id = parse_url_record_id(first_query_value(params, "invite"))
            if not draft and repeat_job and invite_id:
                source = await repeat_invitation_source_record(
                    self.env,
                    row_value(user, "id"),
                    repeat_id,
                    invite_id,
                )
                try:
                    repeat_invitation = validate_repeat_invitation_source(user, source)
                except RepeatProviderInvitationError as exc:
                    return Response(
                        str(exc),
                        status=exc.status,
                        headers={"Cache-Control": "no-store"},
                    )
            template_id = parse_url_record_id(first_query_value(params, "template"))
            if not draft and not repeat_job and template_id:
                project_template = await client_project_template_for_user(
                    self.env,
                    row_value(user, "id"),
                    template_id,
                )
                if not project_template:
                    return Response(
                        "Project template not found.",
                        status=404,
                        headers={"Cache-Control": "no-store"},
                    )
            location_id = parse_url_record_id(first_query_value(params, "location"))
            if not draft and not repeat_job and location_id:
                saved_location = await client_saved_location_for_user(
                    self.env,
                    row_value(user, "id"),
                    location_id,
                )
            saved_locations = await client_saved_locations_for_user(
                self.env,
                row_value(user, "id"),
            )
            new_job_source = draft or repeat_job
            if repeat_job and isinstance(repeat_job, dict):
                repeat_job["scope_answers"] = await load_job_scope_answers(
                    self.env, int(row_value(repeat_job, "id", 0) or 0)
                )
            if not new_job_source and project_template:
                new_job_source = project_template_job_form(project_template)
                if saved_location:
                    new_job_source.update(
                        {
                            "city": row_value(saved_location, "city", ""),
                            "state": row_value(saved_location, "state", "DC"),
                            "zip_code": row_value(saved_location, "zip_code", ""),
                        }
                    )
            if not new_job_source:
                new_job_source = saved_location
            family_value = first_query_value(params, "family")
            service_value = first_query_value(params, "service")
            selected_service = SERVICE_BY_SLUG.get(service_value)
            if selected_service and not family_value:
                family_value = selected_service["group_slug"]
            elif selected_service and selected_service["group_slug"] != family_value:
                selected_service = None
            if (
                not draft
                and not repeat_job
                and not project_template
                and family_value in GROUP_BY_SLUG
            ):
                new_job_source = {
                    "service_group_slug": family_value,
                    "city": row_value(saved_location, "city", ""),
                    "state": row_value(saved_location, "state", "DC"),
                    "zip_code": row_value(saved_location, "zip_code", ""),
                }
                if selected_service:
                    new_job_source.update(
                        service_selection(service_value, family_value)
                    )
            html = job_form_html(
                user,
                getattr(self.env, "WORKDOE_TURNSTILE_SITE_KEY", ""),
                job=new_job_source,
                embedded=embedded,
                media_uploads_enabled=media_uploads_enabled(self.env),
                saved_locations=[
                    saved_location_response(location) for location in saved_locations
                ],
                repeat_invitation=repeat_invitation,
            )
        elif path.endswith("/edit") and path.startswith("/client/jobs/") and role == "client":
            job_id = parse_app_client_job_edit_id(path)
            job = await job_for_detail(self.env, job_id)
            if not can_update_job(user, job):
                return Response("Job not found", status=404, headers={"Cache-Control": "no-store"})
            if isinstance(job, dict):
                job["scope_answers"] = await load_job_scope_answers(self.env, job_id)
            include_turnstile = bool(getattr(self.env, "WORKDOE_TURNSTILE_SITE_KEY", ""))
            html = job_form_html(
                user,
                getattr(self.env, "WORKDOE_TURNSTILE_SITE_KEY", ""),
                job=job,
                mode="edit",
                media_uploads_enabled=media_uploads_enabled(self.env),
            )
        elif path.startswith("/client/jobs/") and role in {"client", "admin"}:
            job_id = parse_app_client_job_id(path)
            job = await job_for_detail(self.env, job_id)
            if not can_view_client_job_requests(user, job):
                return Response("Job not found", status=404, headers={"Cache-Control": "no-store"})
            include_hidden = row_value(user, "role") == "admin" or row_value(user, "id") == row_value(job, "client_id")
            photos = await job_photos_for_detail(self.env, job_id, include_hidden=include_hidden)
            view = normalize_client_request_view(
                first_query_value(params, "bids") or first_query_value(params, "view")
            )
            credential_filter = first_query_value(params, "credentials")
            rows = await client_requests_for_job(self.env, job_id)
            scope_answers = scope_answer_projection(
                row_value(job, "service_slug", ""),
                await load_job_scope_answers(self.env, job_id),
            )
            detail_payload = job_detail_payload(
                user,
                job,
                photos,
                scope_answer_count=len(scope_answers),
            )
            detail_payload["scope_answers"] = scope_answers
            invitation = await repeat_invitation_for_job(self.env, job_id)
            if invitation:
                detail_payload["repeat_invitation"] = repeat_invitation_response(
                    invitation
                )
            requests_payload = client_job_requests_payload(
                job,
                rows,
                view,
                credential_filter,
            )
            requests_payload["reviews_by_request"] = await match_reviews_for_request_ids(
                self.env,
                [int(row_value(item, "id", 0) or 0) for item in rows],
            )
            html = client_job_detail_html(
                user,
                detail_payload,
                requests_payload,
                media_uploads_enabled=media_uploads_enabled(self.env),
            )
        elif path.startswith("/jobs/") and role in {"contractor", "admin"}:
            job_id = parse_app_job_id(path)
            job = await job_for_detail(
                self.env, job_id, contractor_id=row_value(user, "id") if role == "contractor" else None,
            )
            if not can_view_job_detail(user, job):
                return Response("Lead not found", status=404, headers={"Cache-Control": "no-store"})
            existing_request = None
            lead_feedback = None
            if row_value(user, "role") == "contractor":
                existing_request = await contractor_request_for_job(
                    self.env,
                    job_id,
                    row_value(user, "id"),
                )
                if enforce_service_activation(self.env) and not existing_request:
                    activation = await service_activation_record(
                        self.env,
                        row_value(job, "service_slug", ""),
                        row_value(job, "service_zone_slug", ""),
                    )
                    if not activation_is_live(activation):
                        return Response(
                            "Lead not found",
                            status=404,
                            headers={"Cache-Control": "no-store"},
                        )
                lead_feedback = await contractor_lead_feedback_for_job(
                    self.env,
                    job_id,
                    row_value(user, "id"),
                )
            photos = await detail_photos_for_viewer(self.env, user, job, existing_request)
            scope_answers = scope_answer_projection(
                row_value(job, "service_slug", ""),
                await load_job_scope_answers(self.env, job_id),
            )
            payload = job_detail_payload(
                user,
                job,
                photos,
                existing_request,
                scope_answer_count=len(scope_answers),
            )
            payload["scope_answers"] = scope_answers
            if row_value(user, "role") == "contractor":
                invitation = await repeat_invitation_for_job(
                    self.env,
                    job_id,
                    contractor_id=row_value(user, "id"),
                )
                if invitation:
                    payload["repeat_invitation"] = repeat_invitation_response(
                        invitation
                    )
                proposal_templates = await contractor_proposal_templates_for_user(
                    self.env, row_value(user, "id")
                )
                payload["proposal_templates"] = [
                    proposal_template_response(item) for item in proposal_templates
                ]
                payload["proposal_template_limit"] = PROPOSAL_TEMPLATE_LIMIT
                payload["proposal_template_name_max"] = (
                    PROPOSAL_TEMPLATE_NAME_MAX_LENGTH
                )
                selected_template_raw = first_query_value(
                    params, "proposal_template"
                )
                if selected_template_raw and not existing_request:
                    selected_template_id = parse_url_record_id(selected_template_raw)
                    if not selected_template_id:
                        return Response(
                            "Proposal template not found",
                            status=404,
                            headers={"Cache-Control": "no-store"},
                        )
                    selected_template = await contractor_proposal_template_for_user(
                        self.env,
                        row_value(user, "id"),
                        selected_template_id,
                    )
                    if not selected_template:
                        return Response(
                            "Proposal template not found",
                            status=404,
                            headers={"Cache-Control": "no-store"},
                        )
                    payload["selected_proposal_template"] = (
                        proposal_template_response(selected_template)
                    )
                    payload["bid_form"] = proposal_template_bid_form(
                        selected_template
                    )
            if lead_feedback:
                payload["lead_feedback"] = {
                    "reason_code": row_value(lead_feedback, "reason_code", "") or "",
                    "note": row_value(lead_feedback, "note", "") or "",
                    "updated_at": row_value(lead_feedback, "updated_at", "") or "",
                }
            include_turnstile = bool(getattr(self.env, "WORKDOE_TURNSTILE_SITE_KEY", ""))
            html = contractor_job_detail_html(
                user,
                payload,
                getattr(self.env, "WORKDOE_TURNSTILE_SITE_KEY", ""),
                embedded=embedded,
            )
        elif path == "/contractor/profile" and role == "contractor":
            profile = await ensure_contractor_profile(self.env, user, utc_now())
            market_fit = await contractor_market_fit_for_user(
                self.env,
                row_value(user, "id"),
                profile,
            )
            photos = await visible_contractor_profile_photos(
                self.env,
                row_value(user, "id"),
            )
            credentials = await contractor_credentials_for_user(
                self.env,
                row_value(user, "id"),
            )
            preferences = contractor_preferences_response(
                await contractor_preferences_for_user(
                    self.env,
                    row_value(user, "id"),
                )
            )
            html = contractor_profile_html(
                user,
                contractor_profile_response(profile, **market_fit),
                photos,
                [
                    credential_response(item, include_private=True)
                    for item in credentials
                ],
                preferences,
                media_uploads_enabled=media_uploads_enabled(self.env),
            )
        elif path == "/messages" and role in {"client", "contractor"}:
            rows = await message_threads_for_user(
                self.env,
                row_value(user, "id"),
            )
            payload = message_threads_listing_payload(
                rows,
                first_query_value(params, "view"),
                row_value(user, "id"),
            )
            html = message_threads_html(
                user,
                payload,
            )
        elif path.startswith("/messages/") and role in {"client", "contractor", "admin"}:
            thread_id = parse_app_thread_id(path)
            thread = await thread_for_messages(self.env, thread_id)
            if not can_view_thread(user, thread):
                return Response(
                    "Message thread not found.",
                    status=404,
                    headers={"Cache-Control": "no-store"},
                )
            try:
                history_params = parse_qs(urlparse(request.url).query, keep_blank_values=True)
                through = parse_message_through(history_params.get("through", []))
            except ValueError as exc:
                return Response(str(exc), status=400, headers={"Cache-Control": "no-store"})
            messages, next_through = await messages_for_thread(
                self.env,
                thread_id,
                through,
                include_hidden=row_value(user, "role") == "admin",
            )
            if request.method != "HEAD" and row_value(user, "role") != "admin" and through is None:
                await mark_message_thread_read(
                    self.env,
                    thread_id,
                    row_value(user, "id"),
                    positive_int(row_value(messages[-1], "id")) if messages else 0,
                    row_value(messages[-1], "created_at")
                    if messages
                    else row_value(thread, "created_at"),
                )
            thread_payload = thread_detail_payload(thread, messages, include_moderation_evidence=role == "admin")
            thread_payload["history"] = {"through": through, "next_through": next_through}
            message_site_key = ""
            if role in {"client", "contractor"}:
                inbox_payload = message_threads_listing_payload(
                    await message_threads_for_user(
                        self.env,
                        row_value(user, "id"),
                    ),
                    viewer_id=row_value(user, "id"),
                )
                thread_payload["inbox_threads"] = inbox_payload["threads"]
                user = user_with_unread_message_count(
                    user,
                    inbox_payload["stats"]["unread"],
                )
                message_site_key = getattr(
                    self.env,
                    "WORKDOE_TURNSTILE_SITE_KEY",
                    "",
                )
                include_turnstile = bool(message_site_key)
            html = message_thread_detail_html(
                user,
                thread_payload,
                can_reply=can_send_thread_message(user, thread),
                site_key=message_site_key,
            )
        elif path == "/admin" and role == "admin":
            html = admin_dashboard_html(user, await admin_dashboard_payload(self.env))
        else:
            return Response("Not found", status=404, headers={"Cache-Control": "no-store"})

        body = "" if request.method == "HEAD" else html
        return Response(
            body,
            status=200,
            headers=app_shell_headers(
                include_map=include_map,
                map_tile_url=map_tile_url,
                include_turnstile=include_turnstile,
                include_clerk=include_clerk,
                clerk_publishable_key=getattr(
                    self.env,
                    "CLERK_PUBLISHABLE_KEY",
                    "",
                ),
                clerk_frontend_api_url=getattr(
                    self.env,
                    "CLERK_FRONTEND_API_URL",
                    "https://workdoe.com/__clerk",
                ),
            ),
        )

    async def contractor_profile_page(self, request, path: str):
        if request.method not in {"GET", "HEAD"}:
            return json_response(
                {"ok": False, "error": "Contractor profile pages accept GET only."},
                status=405,
                headers={"Allow": "GET, HEAD"},
            )
        if not hasattr(self.env, "DB"):
            return Response(
                "Workdoe data storage is not configured.",
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        contractor_id = parse_app_contractor_id(path)
        user = await self.optional_workdoe_user(request)
        params = parse_qs(urlparse(request.url).query)
        requested_job_id = parse_url_record_id(first_query_value(params, "job_id"))
        contractor = await public_contractor_for_profile(self.env, contractor_id)
        if not can_view_public_contractor_profile(user, contractor):
            return Response(
                "Contractor profile not found.",
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        photos = (
            await visible_contractor_profile_photos(self.env, contractor_id)
            if user and row_value(user, "status") == "active"
            else []
        )
        credentials = await contractor_credentials_for_user(self.env, contractor_id)
        market_fit = await contractor_market_fit_for_user(
            self.env,
            contractor_id,
            contractor,
        )
        has_bid_relationship = await contractor_has_client_bid_relationship(
            self.env,
            contractor_id,
            user,
        )
        website_visible = can_view_contractor_website(
            user,
            contractor_id,
            has_bid_relationship,
        )
        payload = public_contractor_profile_payload(
            contractor,
            photos,
            user,
            market_fit=market_fit,
            website_visible=website_visible,
            credentials=credentials,
            availability=contractor,
        )
        relationship = (
            await client_contractor_choice_for_profile(
                self.env,
                contractor_id,
                requested_job_id,
                user,
            )
            if requested_job_id
            else None
        )
        payload["contractor"]["choice_context"] = contractor_choice_context(
            user,
            contractor_id,
            relationship,
        )
        payload["contractor"]["completed_work_reviews"] = (
            await visible_contractor_match_reviews(self.env, contractor_id)
            if website_visible
            else []
        )
        body = "" if request.method == "HEAD" else public_contractor_profile_html(user, payload)
        return Response(
            body,
            status=200,
            headers=app_shell_headers(),
        )

    async def public_open_jobs(self, request):
        if not hasattr(self.env, "DB"):
            return public_discovery_unavailable(request.method, 503, api=True)

        params = parse_qs(urlparse(request.url).query)
        limit = parse_public_limit(first_query_value(params, "limit"))
        filters = public_job_filters_from_query(params)
        target = normalize_public_target(first_query_value(params, "target"))
        try:
            viewport = parse_public_viewport(params)
            cursor_offset = parse_public_cursor(first_query_value(params, "cursor"))
        except PublicJobQueryError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        limited = await public_discovery_limit_status(self.env)
        if limited is not None:
            return public_discovery_unavailable(request.method, limited, api=True)
        try:
            rows, next_cursor, truncated = await read_public_project_page(
                self.env, filters, viewport, limit=limit, cursor_offset=cursor_offset, source="api",
            )
        except Exception:  # noqa: BLE001 - D1 failures cross the Worker binding boundary.
            return public_discovery_unavailable(request.method, 503, api=True)

        return json_response(
            public_jobs_payload(
                rows,
                filters=filters,
                target=target,
                view="all",
                viewport=viewport,
                next_cursor=next_cursor,
                truncated=truncated,
            ),
            headers={"Cache-Control": "no-store"},
        )

    async def client_jobs(self, request):
        if request.method != "GET":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before client jobs can load."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        if not can_view_client_jobs(user):
            return json_response(
                {"ok": False, "error": "Only active client accounts can view client jobs."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        params = parse_qs(urlparse(request.url).query)
        view = normalize_client_job_view(first_query_value(params, "view"))
        rows = await client_jobs_for_user(self.env, row_value(user, "id"))
        return json_response(
            client_jobs_payload(rows, view),
            headers={"Cache-Control": "no-store"},
        )

    async def client_job_requests(self, request, path: str):
        if request.method != "GET":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before client bid review can load."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            job_id = parse_client_job_requests_path(path)
        except ClientRequestError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        job = await client_job_for_requests(self.env, job_id)
        if not job:
            return json_response(
                {"ok": False, "error": "Job not found."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        if not can_view_client_job_requests(user, job):
            return json_response(
                {"ok": False, "error": "Only the owning client can review mini bids for this job."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        params = parse_qs(urlparse(request.url).query)
        view = normalize_client_request_view(
            first_query_value(params, "bids") or first_query_value(params, "view")
        )
        credential_filter = first_query_value(params, "credentials")
        rows = await client_requests_for_job(self.env, job_id)
        return json_response(
            client_job_requests_payload(job, rows, view, credential_filter),
            headers={"Cache-Control": "no-store"},
        )

    async def contractor_leads(self, request):
        if request.method != "GET":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before contractor leads can load."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        if not can_view_contractor_leads(user):
            return json_response(
                {"ok": False, "error": "Only active contractor accounts can view leads."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        params = parse_qs(urlparse(request.url).query)
        limit = parse_contractor_lead_limit(first_query_value(params, "limit"))
        filters = contractor_lead_filters_from_query(params)
        view = normalize_contractor_lead_view(first_query_value(params, "view"))
        rows = await contractor_leads_for_user(self.env, row_value(user, "id"), filters, limit)
        market_fit = await contractor_market_fit_for_user(
            self.env,
            row_value(user, "id"),
        )
        payload = contractor_leads_payload(
            rows,
            filters=filters,
            view=view,
            **market_fit,
        )
        preferences_row = await contractor_preferences_for_user(
            self.env,
            row_value(user, "id"),
        )
        payload["preferences"] = contractor_preferences_response(preferences_row)
        payload["saved_lead_view_url"] = saved_lead_view_url(preferences_row)
        return json_response(
            payload,
            headers={"Cache-Control": "no-store"},
        )

    async def contractor_preferences_api(self, request, path: str):
        allowed_methods = {"GET"} if path == "/api/contractor/preferences" else {"POST"}
        if request.method not in allowed_methods:
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": ", ".join(sorted(allowed_methods)), "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before preferences can load."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not can_view_contractor_leads(user):
            return json_response(
                {"ok": False, "error": "Only active contractor accounts can update work preferences."},
                status=403 if user else 401,
                headers={"Cache-Control": "no-store"},
            )
        contractor_id = row_value(user, "id")
        if request.method == "GET":
            row = await contractor_preferences_for_user(self.env, contractor_id)
            return json_response(
                {"ok": True, "preferences": contractor_preferences_response(row)},
                headers={"Cache-Control": "no-store"},
            )
        try:
            body = await request_json_object(request, max_bytes=4096)
            if path.endswith("/availability"):
                values = availability_payload(body)
                await upsert_contractor_availability(
                    self.env,
                    contractor_id,
                    values,
                    utc_now(),
                )
                event_type = "contractor-availability-updated"
            else:
                values = saved_lead_view_payload(
                    body,
                    categories=JOB_CATEGORIES,
                    sorts={"newest", "soonest", "city"},
                    families=GROUP_BY_SLUG,
                )
                await upsert_contractor_saved_lead_view(
                    self.env,
                    contractor_id,
                    values,
                    utc_now(),
                )
                event_type = "contractor-lead-view-saved"
        except OnboardingError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        except ContractorPreferenceError as exc:
            return json_response(
                {"ok": False, "errors": exc.errors, "field_errors": exc.field_errors},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        await record_event(
            self.env,
            event_type,
            target_type="user",
            target_id=contractor_id,
            payload={"fields": sorted(values)},
            status="processed",
        )
        row = await contractor_preferences_for_user(self.env, contractor_id)
        return json_response(
            {
                "ok": True,
                "preferences": contractor_preferences_response(row),
                "url": "/contractor/profile#work-availability"
                if path.endswith("/availability")
                else saved_lead_view_url(row),
            },
            headers={"Cache-Control": "no-store"},
        )

    async def contractor_bids(self, request):
        if request.method != "GET":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before contractor bids can load."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        if not can_view_contractor_bids(user):
            return json_response(
                {"ok": False, "error": "Only active contractor accounts can view mini bids."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        params = parse_qs(urlparse(request.url).query)
        view = normalize_contractor_bid_view(
            first_query_value(params, "bids") or first_query_value(params, "view")
        )
        contractor_id = row_value(user, "id")
        rows = await contractor_bids_for_user(self.env, contractor_id)
        public_credentials = public_credential_responses(
            await contractor_credentials_for_user(self.env, contractor_id)
        )
        return json_response(
            contractor_bids_payload(
                rows,
                view,
                len(public_credentials),
                sum(
                    1
                    for credential in public_credentials
                    if credential.get("credential_type") == "trade_license"
                ),
            ),
            headers={"Cache-Control": "no-store"},
        )

    async def create_job(self, request):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before jobs can be posted."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        if row_value(user, "status") != "active":
            return json_response(
                {"ok": False, "error": "This account is not active."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        if row_value(user, "role") not in {"client", "admin"}:
            return json_response(
                {"ok": False, "error": "Only client accounts can post jobs."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        try:
            body = await request_json_object(request, max_bytes=MAX_JOB_POST_BODY_BYTES)
            await verify_turnstile_for_request(self.env, request, body, action="job-post")
            job = job_post_payload(body)
        except (OnboardingError, TurnstileError) as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        except JobPostError as exc:
            return json_response(
                {"ok": False, "errors": exc.errors, "field_errors": exc.field_errors},
                status=400,
                headers={"Cache-Control": "no-store"},
            )

        repeat_source = None
        source_job_id = positive_int(body.get("repeat_source_job_id"))
        source_match_request_id = positive_int(body.get("repeat_match_request_id"))
        if source_job_id or source_match_request_id:
            if not source_job_id or not source_match_request_id:
                return json_response(
                    {"ok": False, "error": "The repeat invitation source is incomplete."},
                    status=400,
                    headers={"Cache-Control": "no-store"},
                )
            source = await repeat_invitation_source_record(
                self.env,
                row_value(user, "id"),
                source_job_id,
                source_match_request_id,
            )
            try:
                repeat_source = validate_repeat_invitation_source(user, source)
                validate_repeat_invitation_service(repeat_source, job["service_slug"])
            except RepeatProviderInvitationError as exc:
                return json_response(
                    {"ok": False, "error": str(exc)},
                    status=exc.status,
                    headers={"Cache-Control": "no-store"},
                )

        service_zone_slug = job_zone_slug(job["city"], job["state"], job["zip_code"])
        if enforce_service_activation(self.env):
            activation = await service_activation_record(
                self.env, job["service_slug"], service_zone_slug
            )
            if not activation_is_live(activation):
                return json_response(
                    {"ok": False, "error": ACTIVATION_NOT_OPEN_MESSAGE},
                    status=409,
                    headers={"Cache-Control": "no-store"},
                )

        try:
            request_state = await begin_idempotent_request(
                self.env,
                row_value(user, "id"),
                "job-create",
                "job",
                request_idempotency_value(request, body),
            )
        except IdempotencyError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        conflict = idempotency_conflict_response(request_state)
        if conflict:
            return conflict
        if request_state["state"] == "replay":
            replay_job_id = positive_int(request_state.get("resource_id"))
            if request_state.get("resource_type") != "job" or not replay_job_id:
                return json_response(
                    {"ok": False, "error": "The original project request is unavailable."},
                    status=409,
                    headers={"Cache-Control": "no-store"},
                )
            return json_response(
                {
                    "ok": True,
                    "job_id": replay_job_id,
                    "url": f"/client/jobs/{replay_job_id}",
                    "location_privacy": JOB_LOCATION_PRIVACY_NOTICE,
                    "repeat_provider_invited": bool(repeat_source),
                    "replayed": True,
                },
                headers={"Cache-Control": "no-store"},
            )

        actor_id = row_value(user, "id")
        draft_token = job_draft_token_from_cookie(request.headers.get("Cookie"))
        draft_hash = (
            job_draft_token_hash(draft_token, getattr(self.env, "WORKDOE_SECRET_KEY", ""))
            if draft_token else ""
        )
        try:
            job_id = await publish_job(
                self.env, actor_id, request_state, job, service_zone_slug, repeat_source, draft_hash
            )
        except Exception:  # noqa: BLE001 - D1 binding failures can be JS-backed.
            print(json.dumps({"event": "d1-project-publication-failed"}))
            job_id = None
        if not job_id:
            try:
                await cancel_idempotent_request(self.env, actor_id, request_state)
            except Exception:  # noqa: BLE001 - D1 may be unavailable for cleanup.
                print(json.dumps({"event": "d1-project-reservation-cleanup-failed"}))
            return json_response(
                {"ok": False, "error": "Could not confirm your project was posted. Check Projects before retrying."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        if repeat_source:
            try:
                await queue_repeat_provider_invitation_email(
                    self.env, repeat_source["contractor_id"], job_id,
                    job["title"], job["city"], job["state"],
                )
            except Exception:  # noqa: BLE001 - Optional notification cannot undo publication.
                print(json.dumps({"event": "repeat-provider-notification-failed"}))
        await queue_contractor_lead_alert_fanout(self.env, job_id)
        return json_response(
            {
                "ok": True,
                "job_id": job_id,
                "url": f"/client/jobs/{job_id}",
                "location_privacy": JOB_LOCATION_PRIVACY_NOTICE,
                "repeat_provider_invited": bool(repeat_source),
                "replayed": False,
            },
            status=201,
            headers={
                "Cache-Control": "no-store",
                "Set-Cookie": clear_job_draft_cookie(),
            },
        )

    async def update_job(self, request, path: str):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before jobs can be updated."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            job_id = parse_job_update_id(path)
        except JobPostError:
            return json_response(
                {"ok": False, "error": "Unsupported job update route."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        existing_job = await job_for_detail(self.env, job_id)
        if not can_update_job(user, existing_job):
            return json_response(
                {"ok": False, "error": "Only the owning client can edit this project."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        try:
            body = await request_json_object(request, max_bytes=MAX_JOB_POST_BODY_BYTES)
            await verify_turnstile_for_request(self.env, request, body, action="job-post")
            existing_selection = service_selection(
                row_value(existing_job, "service_slug", ""),
                row_value(existing_job, "service_group_slug", ""),
                row_value(existing_job, "category", ""),
            )
            body["category"] = existing_selection["category"]
            body["service_group_slug"] = existing_selection["service_group_slug"]
            body["service_slug"] = existing_selection["service_slug"]
            job = job_post_payload(body, preserved_desired_date=row_value(existing_job, "desired_date"))
        except (OnboardingError, TurnstileError) as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        except JobPostError as exc:
            return json_response(
                {"ok": False, "errors": exc.errors, "field_errors": exc.field_errors},
                status=400,
                headers={"Cache-Control": "no-store"},
            )

        service_zone_slug = job_zone_slug(job["city"], job["state"], job["zip_code"])
        if enforce_service_activation(self.env):
            activation = await service_activation_record(
                self.env, job["service_slug"], service_zone_slug
            )
            if not activation_is_live(activation):
                return json_response(
                    {"ok": False, "error": ACTIVATION_NOT_OPEN_MESSAGE},
                    status=409,
                    headers={"Cache-Control": "no-store"},
                )

        try:
            saved = await commit_job_edit(self.env, job_id, row_value(user, "id"), job, service_zone_slug)
        except Exception:  # noqa: BLE001 - D1 can fail through the native SDK boundary.
            print(json.dumps({"event": "d1-project-edit-failed"}))
            return json_response(
                {"ok": False, "error": "Could not confirm your changes were saved. Keep this form open and check Projects before retrying."},
                status=503,
                headers={"Cache-Control": "no-store", "Retry-After": "5"},
            )
        if not saved:
            return json_response(
                {"ok": False, "error": "Project access changed. Review Projects before trying again."},
                status=409,
                headers={"Cache-Control": "no-store"},
            )
        return json_response(
            {"ok": True, "job_id": job_id, "url": f"/client/jobs/{job_id}"},
            headers={"Cache-Control": "no-store"},
        )

    async def create_match_request(self, request, path: str):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before bids can be sent."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            job_id = parse_match_request_job_id(path)
        except MatchRequestError:
            return json_response(
                {"ok": False, "error": "Unsupported match request route."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        if row_value(user, "status") != "active":
            return json_response(
                {"ok": False, "error": "This account is not active."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        if row_value(user, "role") != "contractor":
            return json_response(
                {"ok": False, "error": "Only contractor accounts can send mini bids."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )

        lookup = await db_run(
            self.env,
            """
            SELECT jobs.id, jobs.status, jobs.service_slug, jobs.service_zone_slug
            FROM jobs
            JOIN users AS clients
              ON clients.id = jobs.client_id
             AND clients.status = 'active'
            WHERE jobs.id = ?
            LIMIT 1
            """,
            job_id,
        )
        job = first_row(lookup)
        if not job or row_value(job, "status") != "open":
            return json_response(
                {"ok": False, "error": "This lead is not available."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        if enforce_service_activation(self.env):
            activation = await service_activation_record(
                self.env,
                row_value(job, "service_slug", ""),
                row_value(job, "service_zone_slug", ""),
            )
            if not activation_is_live(activation):
                return json_response(
                    {"ok": False, "error": ACTIVATION_NOT_OPEN_MESSAGE},
                    status=409,
                    headers={"Cache-Control": "no-store"},
                )
        duplicate = await db_run(
            self.env,
            """
            SELECT id
            FROM match_requests
            WHERE job_id = ?
              AND contractor_id = ?
            LIMIT 1
            """,
            job_id,
            row_value(user, "id"),
        )
        if first_row(duplicate):
            return json_response(
                {"ok": False, "error": "You already requested a match for this job."},
                status=409,
                headers={"Cache-Control": "no-store"},
            )

        try:
            body = await request_json_object(request, max_bytes=MAX_MATCH_REQUEST_BODY_BYTES)
            await verify_turnstile_for_request(self.env, request, body, action="match-request")
            bid = match_request_payload(body)
            policy_error = service_policy_error(
                row_value(job, "service_slug", ""),
                bid["service_policy_acknowledgement"],
            )
            if policy_error:
                raise MatchRequestError([policy_error])
        except (OnboardingError, TurnstileError) as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        except MatchRequestError as exc:
            return json_response(
                {"ok": False, "errors": exc.errors, "field_errors": exc.field_errors},
                status=400,
                headers={"Cache-Control": "no-store"},
            )

        created_at = utc_now()
        try:
            request_id = await save_match_request(
                self.env, job, row_value(user, "id"), bid, created_at
            )
        except Exception:  # noqa: BLE001 - D1 binding failures can be JS-backed.
            print(json.dumps({"event": "d1-bid-save-failed"}))
            return json_response(
                {"ok": False, "error": "Could not confirm your mini bid was sent. Check Your bids before retrying."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        if not request_id:
            duplicate = await db_run(
                self.env,
                """
                SELECT id
                FROM match_requests
                WHERE job_id = ?
                  AND contractor_id = ?
                LIMIT 1
                """,
                job_id,
                row_value(user, "id"),
            )
            if first_row(duplicate):
                return json_response(
                    {"ok": False, "error": "You already requested a match for this job."},
                    status=409,
                    headers={"Cache-Control": "no-store"},
                )
            latest = await job_for_detail(self.env, job_id)
            if latest and row_value(latest, "status") == "open":
                if row_value(latest, "has_approved_match"):
                    return json_response(
                        {"ok": False, "error": "This project has already chosen a contractor."},
                        status=409,
                        headers={"Cache-Control": "no-store"},
                    )
                bidding = bid_window(latest, now=created_at)
                if bidding["is_full"]:
                    return json_response(
                        {"ok": False, "error": "This project has received its full set of mini bids."},
                        status=409,
                        headers={"Cache-Control": "no-store"},
                    )
                if bidding["is_expired"]:
                    return json_response(
                        {"ok": False, "error": "Bidding has closed for this project."},
                        status=409,
                        headers={"Cache-Control": "no-store"},
                    )
            return json_response(
                {"ok": False, "error": "This lead is not available."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        return json_response(
            {
                "ok": True,
                "request_id": request_id,
                "status": "pending",
                "url": f"/jobs/{job_id}",
            },
            status=201,
            headers={"Cache-Control": "no-store"},
        )

    async def respond_repeat_invitation(self, request, path: str):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            invitation_id, action = parse_invitation_action_path(path)
        except RepeatProviderInvitationError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=exc.status,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        invitation = await repeat_invitation_by_id(self.env, invitation_id)
        try:
            validate_invitation_action(user, invitation, action)
        except RepeatProviderInvitationError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=exc.status,
                headers={"Cache-Control": "no-store"},
            )

        updated_at = utc_now()
        if action == "decline":
            next_status = "declined"
            changed = await db_run(
                self.env,
                """
                UPDATE repeat_provider_invitations
                SET status = ?, responded_at = ?, updated_at = ?
                WHERE id = ? AND status = 'pending' AND contractor_id = ?
                """,
                next_status,
                updated_at,
                updated_at,
                invitation_id,
                row_value(user, "id"),
            )
        else:
            next_status = "withdrawn"
            changed = await db_run(
                self.env,
                """
                UPDATE repeat_provider_invitations
                SET status = ?, responded_at = ?, updated_at = ?
                WHERE id = ? AND status = 'pending' AND client_id = ?
                """,
                next_status,
                updated_at,
                updated_at,
                invitation_id,
                row_value(user, "id"),
            )
        if d1_change_count(changed) != 1:
            return json_response(
                {"ok": False, "error": "This invitation has already been answered."},
                status=409,
                headers={"Cache-Control": "no-store"},
            )
        await record_event(
            self.env,
            f"repeat-provider-invitation-{next_status}",
            target_type="job",
            target_id=row_value(invitation, "job_id"),
            payload={
                "invitation_id": invitation_id,
                "contractor_id": row_value(invitation, "contractor_id"),
            },
            status="processed",
        )
        return json_response(
            {
                "ok": True,
                "invitation_id": invitation_id,
                "status": next_status,
                "url": (
                    "/contractor/dashboard"
                    if action == "decline"
                    else f"/client/jobs/{row_value(invitation, 'job_id')}"
                ),
            },
            headers={"Cache-Control": "no-store"},
        )

    async def extend_job_bids(self, request, path: str):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before bidding can be extended."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        parts = [part for part in path.removeprefix("/api/jobs/").split("/") if part]
        job_id = parse_url_record_id(parts[0]) if len(parts) == 2 else 0
        if not job_id or parts[1] != "extend-bids":
            return json_response(
                {"ok": False, "error": "Unsupported bid extension route."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        job = await job_for_detail(self.env, job_id)
        if not job:
            return json_response(
                {"ok": False, "error": "Job not found."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        if (
            row_value(user, "status") != "active"
            or row_value(user, "role") != "client"
            or row_value(user, "id") != row_value(job, "client_id")
        ):
            return json_response(
                {"ok": False, "error": "Only the owning client can extend bidding."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        bidding = bid_window(job)
        if row_value(job, "status") != "open":
            error = "Only open projects can extend bidding."
        elif bidding["is_full"]:
            error = "This project has received its full set of mini bids."
        elif not bidding["is_expired"]:
            error = "Bidding is still open for this project."
        else:
            error = ""
        if error:
            return json_response(
                {"ok": False, "error": error},
                status=409,
                headers={"Cache-Control": "no-store"},
            )
        updated_at = utc_now()
        extended_at = extended_bidding_closes_at(
            row_value(job, "bidding_closes_at"),
            updated_at,
        )
        result = await db_run(
            self.env,
            """
            UPDATE jobs
            SET bidding_closes_at = ?, updated_at = ?
            WHERE id = ?
              AND client_id = ?
              AND status = 'open'
              AND (SELECT COUNT(*) FROM match_requests WHERE job_id = jobs.id) < bid_limit
            """,
            extended_at,
            updated_at,
            job_id,
            row_value(user, "id"),
        )
        if d1_change_count(result) != 1:
            return json_response(
                {"ok": False, "error": "The bid window could not be extended."},
                status=409,
                headers={"Cache-Control": "no-store"},
            )
        await record_event(
            self.env,
            "job-bidding-extended",
            target_type="job",
            target_id=job_id,
            payload={
                "client_id": row_value(user, "id"),
                "bidding_closes_at": extended_at,
            },
            status="processed",
        )
        return json_response(
            {
                "ok": True,
                "job_id": job_id,
                "bidding_closes_at": extended_at,
                "message": "Bidding extended by 7 days.",
                "url": f"/client/jobs/{job_id}",
            },
            headers={"Cache-Control": "no-store"},
        )

    async def client_profile_api(self, request):
        if request.method not in {"GET", "POST"}:
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET, POST", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before profiles can load."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        if not can_update_client_profile(user):
            return json_response(
                {"ok": False, "error": "Only active consumer accounts can update this profile."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )

        if request.method == "GET":
            profile = await ensure_client_profile(self.env, user, utc_now())
            locations = await client_saved_locations_for_user(
                self.env,
                row_value(user, "id"),
            )
            return json_response(
                {
                    "ok": True,
                    "profile": client_profile_response(profile),
                    "saved_locations": [
                        saved_location_response(location) for location in locations
                    ],
                    "url": "/client/profile",
                },
                headers={"Cache-Control": "no-store"},
            )

        try:
            body = await request_json_object(
                request,
                max_bytes=MAX_CLIENT_PROFILE_BODY_BYTES,
            )
            profile = client_profile_payload(body)
        except OnboardingError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        except ClientProfileError as exc:
            return json_response(
                {"ok": False, "errors": exc.errors, "field_errors": exc.field_errors},
                status=400,
                headers={"Cache-Control": "no-store"},
            )

        updated_at = utc_now()
        await upsert_client_profile(
            self.env,
            row_value(user, "id"),
            profile,
            updated_at,
        )
        saved = await client_profile_for_user(self.env, row_value(user, "id"))
        await record_event(
            self.env,
            "client-profile-updated",
            target_type="user",
            target_id=row_value(user, "id"),
            payload={"fields": sorted(profile)},
            status="processed",
        )
        return json_response(
            {
                "ok": True,
                "profile": client_profile_response(saved or profile),
                "url": "/client/profile",
            },
            headers={"Cache-Control": "no-store"},
        )

    async def client_saved_locations_api(self, request, path: str):
        allowed_methods = {"GET", "POST"} if path == "/api/client/locations" else {"POST"}
        if request.method not in allowed_methods:
            return Response(
                "Method not allowed",
                status=405,
                headers={
                    "Allow": ", ".join(sorted(allowed_methods)),
                    "Cache-Control": "no-store",
                },
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before project areas can load."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not can_update_client_profile(user):
            status = 401 if not user else 403
            return json_response(
                {"ok": False, "error": "An active consumer account is required."},
                status=status,
                headers={"Cache-Control": "no-store"},
            )
        client_id = row_value(user, "id")
        await ensure_client_profile(self.env, user, utc_now())

        if request.method == "GET":
            locations = await client_saved_locations_for_user(self.env, client_id)
            return json_response(
                {
                    "ok": True,
                    "saved_locations": [
                        saved_location_response(location) for location in locations
                    ],
                },
                headers={"Cache-Control": "no-store"},
            )

        if path.endswith("/delete"):
            try:
                location_id = parse_saved_location_delete_path(path)
            except SavedLocationError as exc:
                return json_response(
                    {"ok": False, "errors": exc.errors},
                    status=404,
                    headers={"Cache-Control": "no-store"},
                )
            result = await db_run(
                self.env,
                "DELETE FROM client_saved_locations WHERE id = ? AND client_id = ?",
                location_id,
                client_id,
            )
            if d1_change_count(result) != 1:
                return json_response(
                    {"ok": False, "error": "Saved project area not found."},
                    status=404,
                    headers={"Cache-Control": "no-store"},
                )
            await record_event(
                self.env,
                "client-saved-location-deleted",
                target_type="client_saved_location",
                target_id=location_id,
                payload={"client_id": client_id},
                status="processed",
            )
            return json_response(
                {"ok": True, "url": "/client/profile#saved-project-areas"},
                headers={"Cache-Control": "no-store"},
            )

        try:
            body = await request_json_object(
                request,
                max_bytes=MAX_SAVED_LOCATION_BODY_BYTES,
            )
            location = saved_location_payload(body)
        except OnboardingError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        except SavedLocationError as exc:
            return json_response(
                {"ok": False, "errors": exc.errors, "field_errors": exc.field_errors},
                status=400,
                headers={"Cache-Control": "no-store"},
            )

        timestamp = utc_now()
        result = await db_run(
            self.env,
            """
            INSERT INTO client_saved_locations
                (client_id, label, city, state, zip_code, created_at, updated_at)
            SELECT ?, ?, ?, ?, ?, ?, ?
            WHERE (
                SELECT COUNT(*) FROM client_saved_locations WHERE client_id = ?
            ) < ?
              AND NOT EXISTS (
                SELECT 1 FROM client_saved_locations
                WHERE client_id = ? AND label = ? COLLATE NOCASE
              )
            """,
            client_id,
            location["label"],
            location["city"],
            location["state"],
            location["zip_code"],
            timestamp,
            timestamp,
            client_id,
            SAVED_LOCATION_LIMIT,
            client_id,
            location["label"],
        )
        location_id = last_insert_id(result)
        if d1_change_count(result) != 1 or not location_id:
            count_result = await db_run(
                self.env,
                "SELECT COUNT(*) AS count FROM client_saved_locations WHERE client_id = ?",
                client_id,
            )
            count = int(row_value(first_row(count_result), "count", 0) or 0)
            if count >= SAVED_LOCATION_LIMIT:
                message = f"Keep up to {SAVED_LOCATION_LIMIT} saved project areas in this workspace."
                field_errors = {}
            else:
                message = "Use a different name for this saved project area."
                field_errors = {"label": [message]}
            return json_response(
                {"ok": False, "errors": [message], "field_errors": field_errors},
                status=409,
                headers={"Cache-Control": "no-store"},
            )
        await record_event(
            self.env,
            "client-saved-location-created",
            target_type="client_saved_location",
            target_id=location_id,
            payload={"client_id": client_id},
            status="processed",
        )
        return json_response(
            {
                "ok": True,
                "id": location_id,
                "saved_location": {"id": location_id, **location},
                "url": "/client/profile#saved-project-areas",
            },
            status=201,
            headers={"Cache-Control": "no-store"},
        )

    async def client_project_templates_api(self, request, path: str):
        allowed_methods = {"GET", "POST"} if path == "/api/client/templates" else {"POST"}
        if request.method not in allowed_methods:
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": ", ".join(sorted(allowed_methods)), "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before project templates can load."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not can_update_client_profile(user):
            return json_response(
                {"ok": False, "error": "An active consumer account is required."},
                status=401 if not user else 403,
                headers={"Cache-Control": "no-store"},
            )
        client_id = row_value(user, "id")
        await ensure_client_profile(self.env, user, utc_now())
        if request.method == "GET":
            rows = await client_project_templates_for_user(self.env, client_id)
            return json_response(
                {
                    "ok": True,
                    "project_templates": [project_template_response(item) for item in rows],
                },
                headers={"Cache-Control": "no-store"},
            )
        if path.endswith("/delete"):
            try:
                template_id = parse_project_template_delete_path(path)
            except ProjectTemplateError as exc:
                return json_response(
                    {"ok": False, "errors": exc.errors},
                    status=404,
                    headers={"Cache-Control": "no-store"},
                )
            result = await db_run(
                self.env,
                "DELETE FROM client_project_templates WHERE id = ? AND client_id = ?",
                template_id,
                client_id,
            )
            if d1_change_count(result) != 1:
                return json_response(
                    {"ok": False, "error": "Project template not found."},
                    status=404,
                    headers={"Cache-Control": "no-store"},
                )
            await record_event(
                self.env,
                "client-project-template-deleted",
                target_type="client_project_template",
                target_id=template_id,
                payload={"client_id": client_id},
                status="processed",
            )
            return json_response(
                {"ok": True, "url": "/client/profile#project-templates"},
                headers={"Cache-Control": "no-store"},
            )
        try:
            body = await request_json_object(request, max_bytes=4096)
            values = project_template_request_payload(body)
        except OnboardingError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        except ProjectTemplateError as exc:
            return json_response(
                {"ok": False, "errors": exc.errors, "field_errors": exc.field_errors},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        timestamp = utc_now()
        result = await db_run(
            self.env,
            """
            INSERT INTO client_project_templates
                (client_id, name, source_job_id, service_group_slug,
                 service_slug, category, title, description, project_setting,
                 license_preference, budget_min, budget_max, created_at, updated_at)
            SELECT ?, ?, jobs.id, jobs.service_group_slug, jobs.service_slug,
                   jobs.category, jobs.title, jobs.description,
                   jobs.project_setting, jobs.license_preference,
                   jobs.budget_min, jobs.budget_max, ?, ?
            FROM jobs
            WHERE jobs.id = ? AND jobs.client_id = ?
              AND (SELECT COUNT(*) FROM client_project_templates WHERE client_id = ?) < ?
              AND NOT EXISTS (
                  SELECT 1 FROM client_project_templates
                  WHERE client_id = ? AND name = ? COLLATE NOCASE
              )
            """,
            client_id,
            values["name"],
            timestamp,
            timestamp,
            values["source_job_id"],
            client_id,
            client_id,
            PROJECT_TEMPLATE_LIMIT,
            client_id,
            values["name"],
        )
        template_id = last_insert_id(result)
        if d1_change_count(result) != 1 or not template_id:
            source = await client_job_for_template(
                self.env,
                client_id,
                values["source_job_id"],
            )
            count = len(await client_project_templates_for_user(self.env, client_id))
            if not source:
                message = "Choose one of your projects."
                field_errors = {"source_job_id": [message]}
            elif count >= PROJECT_TEMPLATE_LIMIT:
                message = f"Keep up to {PROJECT_TEMPLATE_LIMIT} reusable project templates."
                field_errors = {}
            else:
                message = "Use a different name for this project template."
                field_errors = {"name": [message]}
            return json_response(
                {"ok": False, "errors": [message], "field_errors": field_errors},
                status=409,
                headers={"Cache-Control": "no-store"},
            )
        saved = await client_project_template_for_user(self.env, client_id, template_id)
        await record_event(
            self.env,
            "client-project-template-created",
            target_type="client_project_template",
            target_id=template_id,
            payload={"client_id": client_id, "source_job_id": values["source_job_id"]},
            status="processed",
        )
        return json_response(
            {
                "ok": True,
                "id": template_id,
                "project_template": project_template_response(saved),
                "url": "/client/profile#project-templates",
            },
            status=201,
            headers={"Cache-Control": "no-store"},
        )

    async def contractor_proposal_templates_api(self, request, path: str):
        allowed_methods = (
            {"GET", "POST"}
            if path == "/api/contractor/proposal-templates"
            else {"POST"}
        )
        if request.method not in allowed_methods:
            return Response(
                "Method not allowed",
                status=405,
                headers={
                    "Allow": ", ".join(sorted(allowed_methods)),
                    "Cache-Control": "no-store",
                },
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {
                    "ok": False,
                    "error": "D1 binding is required before proposal templates can load.",
                },
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not can_update_contractor_profile(user):
            return json_response(
                {
                    "ok": False,
                    "error": "An active contractor account is required.",
                },
                status=401 if not user else 403,
                headers={"Cache-Control": "no-store"},
            )
        contractor_id = int(row_value(user, "id", 0) or 0)
        if request.method == "GET":
            rows = await contractor_proposal_templates_for_user(
                self.env, contractor_id
            )
            return json_response(
                {
                    "ok": True,
                    "proposal_templates": [
                        proposal_template_response(item) for item in rows
                    ],
                },
                headers={"Cache-Control": "no-store"},
            )
        if path.endswith("/delete"):
            try:
                template_id = parse_proposal_template_delete_path(path)
            except ProposalTemplateError as exc:
                return json_response(
                    {"ok": False, "errors": exc.errors},
                    status=404,
                    headers={"Cache-Control": "no-store"},
                )
            result = await db_run(
                self.env,
                """
                DELETE FROM contractor_proposal_templates
                WHERE id = ? AND contractor_id = ?
                """,
                template_id,
                contractor_id,
            )
            if d1_change_count(result) != 1:
                return json_response(
                    {"ok": False, "error": "Proposal template not found."},
                    status=404,
                    headers={"Cache-Control": "no-store"},
                )
            await record_event(
                self.env,
                "contractor-proposal-template-deleted",
                target_type="contractor_proposal_template",
                target_id=template_id,
                payload={"contractor_id": contractor_id},
                status="processed",
            )
            return json_response(
                {"ok": True, "url": "/contractor/dashboard#proposal-templates"},
                headers={"Cache-Control": "no-store"},
            )
        try:
            body = await request_json_object(request, max_bytes=4096)
            template_form = proposal_template_request_payload(body)
        except OnboardingError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        except ProposalTemplateError as exc:
            return json_response(
                {"ok": False, "errors": exc.errors, "field_errors": exc.field_errors},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        source_bid = await contractor_bid_for_proposal_template(
            self.env,
            contractor_id,
            template_form["source_match_request_id"],
        )
        if not source_bid:
            return json_response(
                {
                    "ok": False,
                    "errors": ["Choose one of your mini bids."],
                    "field_errors": {
                        "source_match_request_id": ["Choose one of your mini bids."]
                    },
                },
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        values = proposal_template_values(template_form["name"], source_bid)
        timestamp = utc_now()
        result = await db_run(
            self.env,
            """
            INSERT INTO contractor_proposal_templates
                (contractor_id, name, source_match_request_id, scope_note,
                 timeline, experience, questions, availability,
                 created_at, updated_at)
            SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            WHERE (
                SELECT COUNT(*) FROM contractor_proposal_templates
                WHERE contractor_id = ?
            ) < ?
              AND NOT EXISTS (
                  SELECT 1 FROM contractor_proposal_templates
                  WHERE contractor_id = ? AND name = ? COLLATE NOCASE
              )
            """,
            contractor_id,
            values["name"],
            values["source_match_request_id"],
            values["scope_note"],
            values["timeline"],
            values["experience"],
            values["questions"],
            values["availability"],
            timestamp,
            timestamp,
            contractor_id,
            PROPOSAL_TEMPLATE_LIMIT,
            contractor_id,
            values["name"],
        )
        template_id = last_insert_id(result)
        if d1_change_count(result) != 1 or not template_id:
            count = len(
                await contractor_proposal_templates_for_user(
                    self.env, contractor_id
                )
            )
            if count >= PROPOSAL_TEMPLATE_LIMIT:
                message = (
                    f"Keep up to {PROPOSAL_TEMPLATE_LIMIT} proposal templates."
                )
                field_errors = {}
            else:
                message = "Use a different name for this proposal template."
                field_errors = {"name": [message]}
            return json_response(
                {"ok": False, "errors": [message], "field_errors": field_errors},
                status=409,
                headers={"Cache-Control": "no-store"},
            )
        saved = await contractor_proposal_template_for_user(
            self.env, contractor_id, template_id
        )
        await record_event(
            self.env,
            "contractor-proposal-template-created",
            target_type="contractor_proposal_template",
            target_id=template_id,
            payload={
                "contractor_id": contractor_id,
                "source_match_request_id": values["source_match_request_id"],
            },
            status="processed",
        )
        return json_response(
            {
                "ok": True,
                "id": template_id,
                "proposal_template": proposal_template_response(saved),
                "url": f"/jobs/{int(row_value(source_bid, 'job_id', 0) or 0)}#mini-bid",
            },
            status=201,
            headers={"Cache-Control": "no-store"},
        )

    async def contractor_profile_api(self, request):
        if request.method not in {"GET", "POST"}:
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET, POST", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before profiles can load."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        if not can_update_contractor_profile(user):
            return json_response(
                {"ok": False, "error": "Only active contractor accounts can update profiles."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )

        if request.method == "GET":
            profile = await ensure_contractor_profile(self.env, user, utc_now())
            market_fit = await contractor_market_fit_for_user(
                self.env,
                row_value(user, "id"),
                profile,
            )
            return json_response(
                {
                    "ok": True,
                    "profile": contractor_profile_response(profile, **market_fit),
                    "preferences": contractor_preferences_response(
                        await contractor_preferences_for_user(
                            self.env,
                            row_value(user, "id"),
                        )
                    ),
                    "credentials": [
                        credential_response(item, include_private=True)
                        for item in await contractor_credentials_for_user(
                            self.env, row_value(user, "id")
                        )
                    ],
                    "url": f"/contractors/{row_value(user, 'id')}",
                },
                headers={"Cache-Control": "no-store"},
            )

        try:
            body = await request_json_object(request, max_bytes=MAX_CONTRACTOR_PROFILE_BODY_BYTES)
            profile = contractor_profile_payload(body)
        except OnboardingError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        except ContractorProfileError as exc:
            return json_response(
                {"ok": False, "errors": exc.errors, "field_errors": exc.field_errors},
                status=400,
                headers={"Cache-Control": "no-store"},
            )

        updated_at = utc_now()
        await upsert_contractor_profile(self.env, row_value(user, "id"), profile, updated_at)
        await replace_contractor_market_fit(
            self.env,
            row_value(user, "id"),
            profile["service_slugs"],
            profile["service_zone_slugs"],
            updated_at,
        )
        saved = await contractor_profile_for_user(self.env, row_value(user, "id"))
        market_fit = await contractor_market_fit_for_user(
            self.env,
            row_value(user, "id"),
            saved or profile,
        )
        await record_event(
            self.env,
            "contractor-profile-updated",
            target_type="user",
            target_id=row_value(user, "id"),
            payload={"fields": sorted(profile)},
            status="processed",
        )
        return json_response(
            {
                "ok": True,
                "profile": contractor_profile_response(saved or profile, **market_fit),
                "url": f"/contractors/{row_value(user, 'id')}",
            },
            headers={"Cache-Control": "no-store"},
        )

    async def contractor_credentials_api(self, request, path: str):
        allowed_methods = {"GET", "POST"} if path == "/api/contractor/credentials" else {"POST"}
        if request.method not in allowed_methods:
            allow = ", ".join(sorted(allowed_methods))
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": allow, "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before credential claims can load."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        if not can_update_contractor_profile(user):
            return json_response(
                {"ok": False, "error": "Only active contractor accounts can manage credential claims."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        contractor_id = row_value(user, "id")
        if request.method == "GET":
            credentials = await contractor_credentials_for_user(self.env, contractor_id)
            return json_response(
                {
                    "ok": True,
                    "credentials": [
                        credential_response(item, include_private=True)
                        for item in credentials
                    ],
                },
                headers={"Cache-Control": "no-store"},
            )
        if path != "/api/contractor/credentials":
            try:
                credential_id = parse_contractor_credential_remove_path(path)
            except ContractorCredentialError as exc:
                return json_response(
                    {"ok": False, "errors": exc.errors},
                    status=404,
                    headers={"Cache-Control": "no-store"},
                )
            credential = await contractor_credential_for_owner(
                self.env, credential_id, contractor_id
            )
            if not credential:
                return json_response(
                    {"ok": False, "error": "Credential claim not found."},
                    status=404,
                    headers={"Cache-Control": "no-store"},
                )
            if row_value(credential, "status") not in {"self_reported", "pending", "rejected"}:
                return json_response(
                    {"ok": False, "error": "Source-checked and expired records remain in the audit history."},
                    status=409,
                    headers={"Cache-Control": "no-store"},
                )
            await db_run(
                self.env,
                "DELETE FROM contractor_credentials WHERE id = ? AND contractor_id = ?",
                credential_id,
                contractor_id,
            )
            await record_event(
                self.env,
                "contractor-credential-removed",
                target_type="credential",
                target_id=credential_id,
                payload={"contractor_id": contractor_id},
                status="processed",
            )
            return json_response(
                {"ok": True, "url": "/contractor/profile#credential-claims"},
                headers={"Cache-Control": "no-store"},
            )
        try:
            body = await request_json_object(
                request, max_bytes=MAX_CONTRACTOR_CREDENTIAL_BODY_BYTES
            )
            claim = contractor_credential_claim_payload(body)
        except OnboardingError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        except ContractorCredentialError as exc:
            return json_response(
                {"ok": False, "errors": exc.errors},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        duplicate = await contractor_credential_duplicate(
            self.env, contractor_id, claim
        )
        if duplicate:
            return json_response(
                {"ok": False, "error": "That credential claim is already on your profile."},
                status=409,
                headers={"Cache-Control": "no-store"},
            )
        created_at = utc_now()
        result = await db_run(
            self.env,
            """
            INSERT INTO contractor_credentials
                (contractor_id, credential_type, jurisdiction,
                 claimed_identifier, claimed_name, status, source_url,
                 checked_at, expires_at, reviewed_by, review_note,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'self_reported', ?, NULL, ?, NULL, '', ?, ?)
            """,
            contractor_id,
            claim["credential_type"],
            claim["jurisdiction"],
            claim["claimed_identifier"],
            claim["claimed_name"],
            claim["source_url"],
            claim["expires_at"] or None,
            created_at,
            created_at,
        )
        credential_id = last_insert_id(result)
        await record_event(
            self.env,
            "contractor-credential-submitted",
            target_type="credential",
            target_id=credential_id,
            payload={
                "contractor_id": contractor_id,
                "credential_type": claim["credential_type"],
                "jurisdiction": claim["jurisdiction"],
            },
            status="processed",
        )
        return json_response(
            {
                "ok": True,
                "id": credential_id,
                "url": "/contractor/profile#credential-claims",
            },
            status=201,
            headers={"Cache-Control": "no-store"},
        )

    async def public_contractor_profile(self, request, path: str):
        if request.method != "GET":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before profiles can load."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            contractor_id = parse_public_contractor_id(path)
        except ContractorPublicProfileError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=404,
                headers={"Cache-Control": "no-store"},
            )

        user = await self.optional_workdoe_user(request)
        params = parse_qs(urlparse(request.url).query)
        requested_job_id = parse_url_record_id(first_query_value(params, "job_id"))
        contractor = await public_contractor_for_profile(self.env, contractor_id)
        if not can_view_public_contractor_profile(user, contractor):
            return json_response(
                {"ok": False, "error": "Contractor profile not found."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        photos = (
            await visible_contractor_profile_photos(self.env, contractor_id)
            if user and row_value(user, "status") == "active"
            else []
        )
        credentials = await contractor_credentials_for_user(self.env, contractor_id)
        market_fit = await contractor_market_fit_for_user(
            self.env,
            contractor_id,
            contractor,
        )
        has_bid_relationship = await contractor_has_client_bid_relationship(
            self.env,
            contractor_id,
            user,
        )
        website_visible = can_view_contractor_website(
            user,
            contractor_id,
            has_bid_relationship,
        )
        profile_payload = public_contractor_profile_payload(
            contractor,
            photos,
            user,
            market_fit=market_fit,
            website_visible=website_visible,
            credentials=credentials,
        )
        relationship = (
            await client_contractor_choice_for_profile(
                self.env,
                contractor_id,
                requested_job_id,
                user,
            )
            if requested_job_id
            else None
        )
        profile_payload["contractor"]["choice_context"] = (
            contractor_choice_context(
                user,
                contractor_id,
                relationship,
            )
        )
        profile_payload["contractor"]["completed_work_reviews"] = (
            await visible_contractor_match_reviews(self.env, contractor_id)
            if website_visible
            else []
        )
        return json_response(
            profile_payload,
            headers={"Cache-Control": "no-store"},
        )

    async def create_report(self, request):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before reports can be sent."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        if not can_create_report(user):
            return json_response(
                {"ok": False, "error": "Only active accounts can send reports."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )

        try:
            body = await request_json_object(request, max_bytes=MAX_REPORT_BODY_BYTES)
            report = report_payload(body)
        except OnboardingError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        except ModerationReportError as exc:
            return json_response(
                {"ok": False, "errors": exc.errors},
                status=400,
                headers={"Cache-Control": "no-store"},
            )

        target_type, target_id = report["target_type"], report["target_id"]
        actor_id = row_value(user, "id")
        if not await report_target_visible_to_user(
            self.env,
            user,
            target_type,
            target_id,
        ):
            return report_unavailable_response()

        action = idempotency_action(f"report-{target_type}", target_id)
        try:
            request_state = await begin_idempotent_request(
                self.env,
                actor_id,
                action,
                "report",
                request_idempotency_value(request, body),
            )
        except IdempotencyError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        if target_type == "job" and request_state["state"] != "reserved" and not await report_target_visible_to_user(
            self.env, user, target_type, target_id,
        ):
            return report_unavailable_response()
        conflict = idempotency_conflict_response(request_state)
        if conflict:
            return conflict
        if request_state["state"] == "replay":
            replay_report_id = positive_int(request_state.get("resource_id"))
            if request_state.get("resource_type") != "report" or not replay_report_id:
                return json_response(
                    {"ok": False, "error": "The original report request is unavailable."},
                    status=409,
                    headers={"Cache-Control": "no-store"},
                )
            replay_payload = report_response(replay_report_id, report)
            replay_payload["replayed"] = True
            return json_response(
                replay_payload,
                headers={"Cache-Control": "no-store"},
            )

        created_at = utc_now()
        insert_sql = """
            INSERT INTO reports
                (reporter_id, target_type, target_id, reason, status, created_at, resolved_at)
            SELECT ?, ?, ?, ?, 'open', ?, NULL
        """
        bindings = (actor_id, target_type, target_id, report["reason"], created_at)
        if target_type == "job":
            # The authorization and insert must observe the same project state.
            insert_sql += " WHERE EXISTS (" + JOB_REPORT_ACCESS_SQL + ")"
            bindings += (actor_id, target_id)
        result = await db_run(self.env, insert_sql, *bindings)
        if target_type == "job" and d1_change_count(result) == 0:
            await cancel_idempotent_request(self.env, actor_id, request_state)
            return report_unavailable_response()
        report_id = last_insert_id(result)
        if not report_id:
            await cancel_idempotent_request(
                self.env, row_value(user, "id"), request_state
            )
            return json_response(
                {"ok": False, "error": "The report could not be created."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        await complete_idempotent_request(
            self.env,
            row_value(user, "id"),
            request_state,
            report_id,
        )
        await record_event(
            self.env,
            "report-created",
            target_type=report["target_type"],
            target_id=report["target_id"],
            payload={
                "report_id": report_id,
                "reporter_id": row_value(user, "id"),
                "reason_length": len(report["reason"]),
            },
            status="processed",
        )
        await queue_operator_report_alert(
            self.env,
            report_id=report_id,
            target_type=report["target_type"],
            target_id=report["target_id"],
        )
        response_payload = report_response(report_id, report)
        response_payload["replayed"] = False
        return json_response(
            response_payload,
            status=201,
            headers={"Cache-Control": "no-store"},
        )

    async def admin_moderation_action(self, request, path: str):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before admin actions can run."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            action = parse_admin_moderation_path(path)
        except AdminModerationError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=404,
                headers={"Cache-Control": "no-store"},
            )

        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        if not can_admin_moderate(user):
            return json_response(
                {"ok": False, "error": "Only active admins can moderate Workdoe."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        if not await admin_target_exists(self.env, action["target_type"], action["target_id"]):
            return json_response(
                {"ok": False, "error": "That moderation target is no longer available."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        if action["target_type"] == "user":
            target_user = await moderation_user_snapshot(self.env, action["target_id"])
            if not target_user:
                return json_response(
                    {"ok": False, "error": "That moderation target is no longer available."},
                    status=404, headers={"Cache-Control": "no-store"},
                )
            if row_value(target_user, "role") == "admin":
                return json_response(
                    {
                        "ok": False,
                        "error": "Admin account status must be changed through the operator recovery process.",
                    },
                    status=400,
                    headers={"Cache-Control": "no-store"},
                )
            if action["action"] == "activate" and row_value(target_user, "auth_provider") == "clerk":
                failure = await clerk_reactivation_failure(self.env, row_value(target_user, "external_subject"))
                if failure:
                    status, message = failure
                    return json_response(
                        {"ok": False, "error": message}, status=status, headers={"Cache-Control": "no-store"},
                    )

        if action["target_type"] == "credential":
            credential_result = await db_run(
                self.env,
                "SELECT * FROM contractor_credentials WHERE id = ? LIMIT 1",
                action["target_id"],
            )
            credential = first_row(credential_result)
            try:
                body = await request_json_object(
                    request,
                    max_bytes=MAX_CONTRACTOR_CREDENTIAL_BODY_BYTES,
                )
                review = contractor_credential_review_payload(
                    body,
                    action["action"],
                    row_value(credential, "source_url", ""),
                )
            except OnboardingError as exc:
                return json_response(
                    {"ok": False, "error": str(exc)},
                    status=400,
                    headers={"Cache-Control": "no-store"},
                )
            except ContractorCredentialError as exc:
                return json_response(
                    {"ok": False, "errors": exc.errors},
                    status=400,
                    headers={"Cache-Control": "no-store"},
                )
            acted_at = utc_now()
            expires_at = review["expires_at"]
            if action["action"] == "expire" and not expires_at:
                expires_at = acted_at[:10]
            await db_run(
                self.env,
                """
                UPDATE contractor_credentials
                SET status = ?, source_url = ?, checked_at = ?, expires_at = ?,
                    reviewed_by = ?, review_note = ?, updated_at = ?
                WHERE id = ?
                """,
                review["status"],
                review["source_url"],
                acted_at,
                expires_at,
                row_value(user, "id"),
                review["review_note"],
                acted_at,
                action["target_id"],
            )
            notes = f"Set contractor credential status to {review['status']}."
            await insert_moderation_action(
                self.env,
                admin_id=row_value(user, "id"),
                action_type=action["action"],
                target_type="credential",
                target_id=action["target_id"],
                notes=notes,
                created_at=acted_at,
            )
            await record_event(
                self.env,
                "admin-credential-review",
                target_type="credential",
                target_id=action["target_id"],
                payload={
                    "admin_id": row_value(user, "id"),
                    "action": action["action"],
                    "state": review["status"],
                },
                status="processed",
            )
            return json_response(
                admin_moderation_response(action, review["status"]),
                headers={"Cache-Control": "no-store"},
            )

        acted_at = utc_now()
        sql, params, notes, state = admin_update_statement(action, acted_at)
        if action["target_type"] == "user":
            changed = await update_moderated_user(self.env, target_user, state, row_value(user, "id"))
            if not changed:
                return json_response(
                    {"ok": False, "error": "The account changed during review. Reload and try again."},
                    status=409, headers={"Cache-Control": "no-store"},
                )
        else:
            await db_run(self.env, sql, *params)
        await insert_moderation_action(
            self.env,
            admin_id=row_value(user, "id"),
            action_type=action["action"],
            target_type=action["target_type"],
            target_id=action["target_id"],
            notes=notes,
            created_at=acted_at,
        )
        await record_event(
            self.env,
            "admin-moderation-action",
            target_type=action["target_type"],
            target_id=action["target_id"],
            payload={
                "admin_id": row_value(user, "id"),
                "action": action["action"],
                "state": state,
            },
            status="processed",
        )
        return json_response(
            admin_moderation_response(action, state),
            headers={"Cache-Control": "no-store"},
        )

    async def update_job_status(self, request, path: str):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before jobs can be updated."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            job_id, action, status = parse_job_status_path(path)
        except JobStatusError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=exc.status,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        job = await job_for_detail(self.env, job_id)
        if not job:
            return json_response(
                {"ok": False, "error": "Job not found."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        if not can_update_job_status(user, job):
            return json_response(
                {"ok": False, "error": "Only the owning client can update this job."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        if row_value(job, "status") == "hidden":
            return json_response(
                {"ok": False, "error": "Hidden jobs cannot be changed by clients."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        close_outcome = None
        if action == "close":
            try:
                body = await request_json_object(request, max_bytes=MAX_OUTCOME_BODY_BYTES)
                approved_match = first_row(
                    await db_run(
                        self.env,
                        """
                        SELECT id FROM match_requests
                        WHERE job_id = ? AND status = 'approved'
                        LIMIT 1
                        """,
                        job_id,
                    )
                )
                close_outcome = validate_project_close_payload(
                    body,
                    has_approved_match=bool(approved_match),
                )
            except (OnboardingError, JobStatusError) as exc:
                field = getattr(exc, "field", "")
                payload = {"ok": False, "error": str(exc)}
                if field:
                    payload["field_errors"] = {field: [str(exc)]}
                return json_response(
                    payload,
                    status=getattr(exc, "status", 400),
                    headers={"Cache-Control": "no-store"},
                )
        if action == "reopen":
            confirmation = first_row(
                await db_run(
                    self.env,
                    """
                    SELECT match_completions.match_request_id
                    FROM match_completions
                    JOIN match_requests
                      ON match_requests.id = match_completions.match_request_id
                    WHERE match_requests.job_id = ?
                      AND (
                        match_completions.client_confirmed_at IS NOT NULL
                        OR match_completions.contractor_confirmed_at IS NOT NULL
                      )
                    LIMIT 1
                    """,
                    job_id,
                )
            )
            if confirmation:
                return json_response(
                    {
                        "ok": False,
                        "error": "A project with completion confirmation cannot be reopened.",
                    },
                    status=409,
                    headers={"Cache-Control": "no-store"},
                )

        updated_at = utc_now()
        bidding_closes_at = row_value(job, "bidding_closes_at")
        if action == "reopen":
            reopened = bid_window(
                {**dict(job), "status": "open"},
                now=updated_at,
            )
            if reopened["is_expired"] and not reopened["is_full"]:
                bidding_closes_at = extended_bidding_closes_at(
                    bidding_closes_at,
                    updated_at,
                )
        changed = await db_run(
            self.env,
            """
            UPDATE jobs
            SET status = ?,
                bidding_closes_at = ?,
                close_reason = ?,
                close_note = ?,
                closed_at = ?,
                updated_at = ?
            WHERE id = ?
              AND client_id = ?
              AND status = ?
              AND updated_at IS ?
              AND EXISTS (
                SELECT 1 FROM users
                WHERE users.id = jobs.client_id
                  AND users.role = 'client' AND users.status = 'active'
              )
              AND NOT EXISTS (
                SELECT 1 FROM match_completions
                JOIN match_requests
                  ON match_requests.id = match_completions.match_request_id
                WHERE match_requests.job_id = jobs.id
                  AND (match_completions.client_confirmed_at IS NOT NULL
                    OR match_completions.contractor_confirmed_at IS NOT NULL)
              )
            """,
            status,
            bidding_closes_at,
            close_outcome["reason_code"] if close_outcome else None,
            close_outcome["note"] if close_outcome else "",
            updated_at if close_outcome else None,
            updated_at,
            job_id,
            row_value(user, "id"),
            row_value(job, "status"),
            row_value(job, "updated_at"),
        )
        if d1_change_count(changed) != 1:
            return json_response(
                {"ok": False, "error": "This project changed. Refresh before trying again."},
                status=409,
                headers={"Cache-Control": "no-store"},
            )
        if status == "closed":
            await db_run(
                self.env,
                """
                UPDATE repeat_provider_invitations
                SET status = 'withdrawn', responded_at = ?, updated_at = ?
                WHERE job_id = ? AND status = 'pending'
                """,
                updated_at,
                updated_at,
                job_id,
            )
        event_type = "job-closed" if status == "closed" else "job-reopened"
        await record_event(
            self.env,
            event_type,
            target_type="job",
            target_id=job_id,
            payload={
                "action": action,
                "client_id": row_value(user, "id"),
                "previous_status": row_value(job, "status"),
                "status": status,
                **(
                    {"reason_code": close_outcome["reason_code"]}
                    if close_outcome
                    else {}
                ),
            },
            status="processed",
        )
        return json_response(
            job_status_response(job_id, status),
            headers={"Cache-Control": "no-store"},
        )

    async def submit_job_quality_feedback(self, request, path: str):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before feedback can be saved."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            job_id = parse_job_quality_feedback_path(path)
        except JobStatusError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=exc.status,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        job = await job_for_detail(self.env, job_id)
        match_request = await contractor_request_for_job(
            self.env,
            job_id,
            row_value(user, "id"),
        )
        if not can_submit_lead_quality_feedback(user, job, match_request):
            return json_response(
                {"ok": False, "error": "Submit a bid before recording lead feedback."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        try:
            body = await request_json_object(request, max_bytes=MAX_OUTCOME_BODY_BYTES)
            feedback = validate_lead_quality_payload(body)
        except (OnboardingError, JobStatusError) as exc:
            field = getattr(exc, "field", "")
            payload = {"ok": False, "error": str(exc)}
            if field:
                payload["field_errors"] = {field: [str(exc)]}
            return json_response(
                payload,
                status=getattr(exc, "status", 400),
                headers={"Cache-Control": "no-store"},
            )
        timestamp = utc_now()
        await db_run(
            self.env,
            """
            INSERT INTO job_lead_feedback
                (job_id, contractor_id, reason_code, note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id, contractor_id) DO UPDATE SET
                reason_code = excluded.reason_code,
                note = excluded.note,
                updated_at = excluded.updated_at
            """,
            job_id,
            row_value(user, "id"),
            feedback["reason_code"],
            feedback["note"],
            timestamp,
            timestamp,
        )
        await record_event(
            self.env,
            "lead-quality-feedback-recorded",
            target_type="job",
            target_id=job_id,
            payload={
                "contractor_id": row_value(user, "id"),
                "reason_code": feedback["reason_code"],
            },
            status="processed",
        )
        return json_response(
            {"ok": True, "job_id": job_id, "url": f"/jobs/{job_id}#lead-quality"},
            headers={"Cache-Control": "no-store"},
        )

    async def job_detail(self, request, path: str):
        if request.method != "GET":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before job details can load."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            job_id = parse_job_detail_id(path)
        except JobDetailError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        role = row_value(user, "role")
        job = await job_for_detail(
            self.env, job_id, contractor_id=row_value(user, "id") if role == "contractor" else None,
        )
        allowed = can_view_job_detail(user, job)
        if not job or (role == "contractor" and not allowed):
            return json_response(
                {"ok": False, "error": "Job not found."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        if not allowed:
            return json_response(
                {"ok": False, "error": "You cannot view this job."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        viewer = viewer_kind(user, job)
        existing_request = None
        if viewer == "contractor":
            existing_request = await contractor_request_for_job(
                self.env,
                job_id,
                row_value(user, "id"),
            )
            if enforce_service_activation(self.env) and not existing_request:
                activation = await service_activation_record(
                    self.env,
                    row_value(job, "service_slug", ""),
                    row_value(job, "service_zone_slug", ""),
                )
                if not activation_is_live(activation):
                    return json_response(
                        {"ok": False, "error": "Job not found."},
                        status=404,
                        headers={"Cache-Control": "no-store"},
                    )
        photos = await detail_photos_for_viewer(self.env, user, job, existing_request)
        scope_answers = scope_answer_projection(
            row_value(job, "service_slug", ""),
            await load_job_scope_answers(self.env, job_id),
        )
        payload = job_detail_payload(
            user,
            job,
            photos=photos,
            existing_request=existing_request,
            scope_answer_count=len(scope_answers),
        )
        payload["scope_answers"] = scope_answers
        return json_response(payload, headers={"Cache-Control": "no-store"})

    async def confirm_match_completion(self, request, path: str):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {
                    "ok": False,
                    "error": "D1 binding is required before completion can be confirmed.",
                },
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            request_id = parse_match_completion_path(path)
        except MatchCompletionError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=exc.status,
                headers={"Cache-Control": "no-store"},
            )

        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        match = await match_for_completion(self.env, request_id)
        try:
            participant = validate_completion_confirmation(user, match)
        except MatchCompletionError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=exc.status,
                headers={"Cache-Control": "no-store"},
            )

        timestamp = utc_now()
        await db_run(
            self.env,
            """
            INSERT OR IGNORE INTO match_completions
                (match_request_id, client_confirmed_at, contractor_confirmed_at,
                 verified_at, created_at, updated_at)
            VALUES (?, NULL, NULL, NULL, ?, ?)
            """,
            request_id,
            timestamp,
            timestamp,
        )
        confirmation_result = await db_run(
            self.env,
            """
            UPDATE match_completions
            SET client_confirmed_at = CASE WHEN ? = 'client' THEN ? ELSE client_confirmed_at END,
                contractor_confirmed_at = CASE WHEN ? = 'contractor' THEN ? ELSE contractor_confirmed_at END,
                updated_at = ?
            WHERE match_request_id = ?
              AND ((? = 'client' AND client_confirmed_at IS NULL)
                OR (? = 'contractor' AND contractor_confirmed_at IS NULL))
              AND EXISTS (
                SELECT 1 FROM match_requests
                JOIN jobs ON jobs.id = match_requests.job_id
                JOIN users AS actor ON actor.id = ?
                WHERE match_requests.id = match_completions.match_request_id
                  AND match_requests.status = 'approved'
                  AND jobs.status = 'closed' AND jobs.close_reason = 'workdoe-match'
                  AND actor.status = 'active' AND actor.role = ?
                  AND ((actor.role = 'client' AND actor.id = jobs.client_id)
                    OR (actor.role = 'contractor' AND actor.id = match_requests.contractor_id))
              )
            """,
            participant,
            timestamp,
            participant,
            timestamp,
            timestamp,
            request_id,
            participant,
            participant,
            row_value(user, "id"),
            participant,
        )

        completion = await match_for_completion(self.env, request_id)
        if not row_value(completion, f"{participant}_confirmed_at"):
            return json_response(
                {"ok": False, "error": "This project changed. Refresh before trying again."},
                status=409,
                headers={"Cache-Control": "no-store"},
            )
        verified_now = bool(
            row_value(completion, "client_confirmed_at")
            and row_value(completion, "contractor_confirmed_at")
        )
        if verified_now and not row_value(completion, "verified_at"):
            await db_run(
                self.env,
                """
                UPDATE match_completions
                SET verified_at = ?, updated_at = ?
                WHERE match_request_id = ? AND verified_at IS NULL
                """,
                timestamp,
                timestamp,
                request_id,
            )
            completion = await match_for_completion(self.env, request_id)

        if d1_change_count(confirmation_result) == 1:
            await record_event(
                self.env,
                "match-completion-confirmed",
                target_type="match_request",
                target_id=request_id,
                payload={
                    "participant_role": participant,
                    "verified": bool(row_value(completion, "verified_at")),
                },
                status="processed",
            )
        response = completion_response(completion)
        response.update(
            {
                "ok": True,
                "url": (
                    f"/client/jobs/{row_value(completion, 'job_id')}"
                    if participant == "client"
                    else "/contractor/dashboard#completed-work"
                ),
            }
        )
        return json_response(
            response,
            headers={"Cache-Control": "no-store"},
        )

    async def create_match_review(self, request, path: str):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before feedback can be recorded."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            request_id = parse_match_review_create_path(path)
            body = await request_json_object(
                request, max_bytes=MAX_MATCH_REVIEW_BODY_BYTES
            )
        except (MatchReviewError, OnboardingError) as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=getattr(exc, "status", 400),
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        match = await match_for_review(self.env, request_id)
        existing = await match_review_for_participant(
            self.env, request_id, row_value(user, "id")
        )
        try:
            participant = validate_review_eligibility(user, match, existing)
            values = validate_review_payload(body)
        except MatchReviewError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=exc.status,
                headers={"Cache-Control": "no-store"},
            )
        timestamp = utc_now()
        result = await db_run(
            self.env,
            """
            INSERT OR IGNORE INTO match_reviews
                (match_request_id, reviewer_id, subject_id, reviewer_role,
                 communication, scope_accuracy, timeliness, work_outcome,
                 would_work_again, comment, response, response_at,
                 is_hidden, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', NULL, 0, ?, ?)
            """,
            request_id,
            row_value(user, "id"),
            review_subject_id(participant, match),
            participant,
            values["communication"],
            values["scope_accuracy"],
            values["timeliness"],
            values["work_outcome"],
            values["would_work_again"],
            values["comment"],
            timestamp,
            timestamp,
        )
        if d1_change_count(result) != 1:
            return json_response(
                {"ok": False, "error": "You already left feedback for this project."},
                status=409,
                headers={"Cache-Control": "no-store"},
            )
        created = await match_review_for_participant(
            self.env, request_id, row_value(user, "id")
        )
        review_id = int(row_value(created, "id", 0) or 0)
        await record_event(
            self.env,
            "match-review-created",
            target_type="match_review",
            target_id=review_id,
            payload={
                "match_request_id": request_id,
                "reviewer_role": participant,
                "dimension_codes": {
                    key: values[key]
                    for key in (
                        "communication",
                        "scope_accuracy",
                        "timeliness",
                        "work_outcome",
                    )
                },
                "would_work_again": values["would_work_again"],
                "has_comment": bool(values["comment"]),
            },
            status="processed",
        )
        return json_response(
            {
                "ok": True,
                "review": review_response(created, include_private=True),
                "url": review_return_path(participant, row_value(match, "job_id")),
            },
            status=201,
            headers={"Cache-Control": "no-store"},
        )

    async def match_review_action(self, request, path: str):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before feedback can be updated."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            review_id, action = parse_match_review_action_path(path)
            body = await request_json_object(
                request, max_bytes=MAX_MATCH_REVIEW_BODY_BYTES
            )
        except (MatchReviewError, OnboardingError) as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=getattr(exc, "status", 400),
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        review = await match_review_by_id(self.env, review_id)
        timestamp = utc_now()
        try:
            if action == "response":
                response = validate_review_response(user, review, body.get("response"))
                changed = await db_run(
                    self.env,
                    """
                    UPDATE match_reviews
                    SET response = ?, response_at = ?, updated_at = ?
                    WHERE id = ? AND subject_id = ? AND response = '' AND is_hidden = 0
                    """,
                    response,
                    timestamp,
                    timestamp,
                    review_id,
                    row_value(user, "id"),
                )
                if d1_change_count(changed) != 1:
                    raise MatchReviewError("A response is already recorded.", 409)
                event_type = "match-review-response-created"
                payload = {"responder_role": row_value(user, "role"), "has_response": True}
            else:
                reason = validate_review_report(user, review, body.get("reason"))
                changed = await db_run(
                    self.env,
                    """
                    INSERT OR IGNORE INTO match_review_reports
                        (review_id, reporter_id, reason, status, created_at, resolved_at)
                    VALUES (?, ?, ?, 'open', ?, NULL)
                    """,
                    review_id,
                    row_value(user, "id"),
                    reason,
                    timestamp,
                )
                if d1_change_count(changed) != 1:
                    raise MatchReviewError("You already reported this feedback.", 409)
                event_type = "match-review-reported"
                payload = {"reporter_role": row_value(user, "role")}
        except MatchReviewError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=exc.status,
                headers={"Cache-Control": "no-store"},
            )
        await record_event(
            self.env,
            event_type,
            target_type="match_review",
            target_id=review_id,
            payload=payload,
            status="processed",
        )
        return json_response(
            {
                "ok": True,
                "action": action,
                "url": review_return_path(
                    row_value(user, "role"), row_value(review, "job_id")
                ),
            },
            headers={"Cache-Control": "no-store"},
        )

    async def decide_match_request(self, request, path: str):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before bids can be reviewed."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            request_id, _, status = parse_match_decision_path(path)
        except MatchDecisionError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=404,
                headers={"Cache-Control": "no-store"},
            )

        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        match = await match_request_for_decision(self.env, request_id)
        if not match:
            return json_response(
                {"ok": False, "error": "Match request not found."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        if not can_decide_match_request(user, match):
            return json_response(
                {"ok": False, "error": "You cannot review this mini bid."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        current_status = row_value(match, "status")
        if current_status != "pending":
            return await self.existing_match_decision_response(
                match,
                request_id,
                requested_status=status,
                actor_id=row_value(user, "id"),
            )

        updated_at = utc_now()
        thread_id = None
        actor_id = row_value(user, "id")
        try:
            if status == "approved":
                thread_id = await approve_pending_match(
                    self.env, match, updated_at, actor_id=actor_id,
                )
                changed = thread_id is not None
            else:
                changed = await reject_pending_match(self.env, match, updated_at, actor_id=actor_id)
        except Exception:  # noqa: BLE001 - D1 failures cross the Worker binding boundary.
            event = "d1-match-approval-failed" if status == "approved" else "d1-match-rejection-failed"
            print(json.dumps({"event": event}))
            return json_response(
                {"ok": False, "error": "Could not confirm your choice. Refresh the project before retrying."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        if not changed:
            refreshed = await match_request_for_decision(self.env, request_id)
            if not refreshed:
                return json_response(
                    {"ok": False, "error": "Match request not found."},
                    status=404,
                    headers={"Cache-Control": "no-store"},
                )
            if not can_decide_match_request(user, refreshed):
                return json_response(
                    {"ok": False, "error": "You cannot review this mini bid."},
                    status=403,
                    headers={"Cache-Control": "no-store"},
                )
            if row_value(refreshed, "status") == "pending":
                return json_response(
                    {
                        "ok": False,
                        "error": "This project or account changed. Refresh before reviewing the mini bid.",
                    },
                    status=409,
                    headers={"Cache-Control": "no-store"},
                )
            return await self.existing_match_decision_response(
                refreshed,
                request_id,
                requested_status=status,
                actor_id=actor_id,
            )
        return json_response(
            match_decision_response(
                request_id,
                status,
                job_id=row_value(match, "job_id"),
                thread_id=thread_id,
            ),
            status=200,
            headers={"Cache-Control": "no-store"},
        )

    async def existing_match_decision_response(
        self,
        match,
        request_id: int,
        requested_status: str,
        *,
        actor_id: int,
    ):
        current_status = row_value(match, "status")
        thread_id = await existing_thread_id_for_match(self.env, request_id) if current_status == "approved" else None
        if current_status == requested_status:
            if current_status == "approved" and not thread_id:
                try:
                    thread_id = await ensure_thread_for_match(self.env, match, utc_now(), actor_id=actor_id)
                except Exception:  # noqa: BLE001 - D1 failures cross the Worker binding boundary.
                    print(json.dumps({"event": "d1-match-thread-repair-failed"}))
                    return json_response(
                        {"ok": False, "error": "Could not confirm the conversation. Refresh the project before retrying."},
                        status=503,
                        headers={"Cache-Control": "no-store"},
                    )
                if not thread_id:
                    return json_response(
                        {"ok": False, "error": "Messaging is unavailable for this project."},
                        status=409,
                        headers={"Cache-Control": "no-store"},
                    )
            return json_response(
                match_decision_response(
                    request_id,
                    current_status,
                    job_id=row_value(match, "job_id"),
                    thread_id=thread_id,
                ),
                headers={"Cache-Control": "no-store"},
            )
        return json_response(
            {
                "ok": False,
                "error": "This mini bid has already been reviewed.",
                "status": current_status,
                "thread_id": thread_id,
            },
            status=409,
            headers={"Cache-Control": "no-store"},
        )

    async def message_threads_api(self, request, path: str):
        if not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "D1 binding is required before messages can load."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        if row_value(user, "status") != "active":
            return json_response(
                {"ok": False, "error": "This account is not active."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        if path == "/api/messages/threads":
            if request.method != "GET":
                return Response(
                    "Method not allowed",
                    status=405,
                    headers={"Allow": "GET", "Cache-Control": "no-store"},
                )
            if row_value(user, "role") not in {"client", "contractor"}:
                return json_response(
                    {"ok": False, "error": "Only matched clients and contractors can list threads."},
                    status=403,
                    headers={"Cache-Control": "no-store"},
                )
            rows = await message_threads_for_user(
                self.env,
                row_value(user, "id"),
            )
            params = parse_qs(urlparse(request.url).query)
            return json_response(
                message_threads_listing_payload(
                    rows,
                    first_query_value(params, "view"),
                    row_value(user, "id"),
                ),
                headers={"Cache-Control": "no-store"},
            )

        try:
            thread_id = parse_thread_id(path)
        except MessageThreadError as exc:
            return json_response(
                {"ok": False, "error": str(exc), "field_errors": exc.field_errors},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        if request.method not in {"GET", "POST"}:
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET, POST", "Cache-Control": "no-store"},
            )
        thread = await thread_for_messages(self.env, thread_id)
        if not thread:
            return json_response(
                {"ok": False, "error": "Message thread not found."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        if not can_view_thread(user, thread):
            return json_response(
                {"ok": False, "error": "You cannot view this message thread."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        if request.method == "POST":
            if not can_send_thread_message(user, thread):
                return json_response(
                    {"ok": False, "error": "You cannot reply in this message thread."},
                    status=403,
                    headers={"Cache-Control": "no-store"},
                )
            try:
                body = await request_json_object(request, max_bytes=MAX_MESSAGE_BODY_BYTES)
                message_body = message_body_payload(body)
            except OnboardingError as exc:
                return json_response(
                    {"ok": False, "error": str(exc)},
                    status=400,
                    headers={"Cache-Control": "no-store"},
                )
            except MessageThreadError as exc:
                return json_response(
                    {"ok": False, "errors": exc.errors, "field_errors": exc.field_errors},
                    status=400,
                    headers={"Cache-Control": "no-store"},
                )
            try:
                request_state = await begin_idempotent_request(
                    self.env,
                    row_value(user, "id"),
                    idempotency_action("message-create", thread_id),
                    "message",
                    request_idempotency_value(request, body),
                )
            except IdempotencyError as exc:
                return json_response(
                    {"ok": False, "error": str(exc)},
                    status=400,
                    headers={"Cache-Control": "no-store"},
                )
            conflict = idempotency_conflict_response(request_state)
            if conflict:
                return conflict
            if request_state["state"] == "replay":
                replay_message_id = positive_int(request_state.get("resource_id"))
                if request_state.get("resource_type") != "message" or not replay_message_id:
                    return json_response(
                        {"ok": False, "error": "The original message request is unavailable."},
                        status=409,
                        headers={"Cache-Control": "no-store"},
                    )
                return json_response(
                    {
                        "ok": True,
                        "message_id": replay_message_id,
                        "thread_id": thread_id,
                        "url": f"/messages/{thread_id}",
                        "replayed": True,
                    },
                    headers={"Cache-Control": "no-store"},
                )
            actor_id = row_value(user, "id")
            failure_status = 409
            try:
                message_id = await save_thread_message(self.env, actor_id, thread_id, request_state, message_body)
            except Exception:  # noqa: BLE001 - D1 binding failures can be JS-backed.
                print(json.dumps({"event": "d1-message-save-failed"}))
                message_id = None
                failure_status = 503
            if not message_id:
                try:
                    await cancel_idempotent_request(self.env, actor_id, request_state)
                except Exception:  # noqa: BLE001 - D1 may be unavailable for cleanup.
                    print(json.dumps({"event": "d1-message-reservation-cleanup-failed"}))
                    failure_status = 503
                return json_response(
                    {"ok": False, "error": (
                        "Could not confirm your message. Check the thread before retrying."
                        if failure_status == 503
                        else "You can no longer reply in this message thread. Refresh to continue."
                    )},
                    status=failure_status,
                    headers={"Cache-Control": "no-store"},
                )
            return json_response(
                {
                    "ok": True,
                    "message_id": message_id,
                    "thread_id": thread_id,
                    "url": f"/messages/{thread_id}",
                    "replayed": False,
                },
                status=201,
                headers={"Cache-Control": "no-store"},
            )

        try:
            params = parse_qs(urlparse(request.url).query, keep_blank_values=True)
            through = parse_message_through(params.get("through", []))
        except ValueError as exc:
            return json_response({"ok": False, "error": str(exc)}, status=400, headers={"Cache-Control": "no-store"})
        messages, next_through = await messages_for_thread(
            self.env,
            thread_id,
            through,
            include_hidden=row_value(user, "role") == "admin",
        )
        if row_value(user, "role") != "admin" and through is None:
            await mark_message_thread_read(
                self.env,
                thread_id,
                row_value(user, "id"),
                positive_int(row_value(messages[-1], "id")) if messages else 0,
                row_value(messages[-1], "created_at")
                if messages
                else row_value(thread, "created_at"),
            )
        payload = thread_detail_payload(thread, messages, include_moderation_evidence=row_value(user, "role") == "admin")
        payload["history"] = {"through": through, "next_through": next_through}
        return json_response(payload, headers={"Cache-Control": "no-store"})

    async def verified_clerk_claims(self, request):
        if not clerk_production_configuration_ready(self.env):
            raise SessionVerificationError("Clerk production authentication is not configured.")
        token = extract_clerk_session_token(request.headers)
        if not token:
            raise SessionVerificationError("Session token not found.")
        staging = is_staging_environment(self.env)
        stage_url = getattr(self.env, "WORKDOE_PUBLIC_URL", "")
        jwt_key = getattr(self.env, "CLERK_JWT_KEY", "")

        async def jwks_fetcher(secret_key):
            async def lookup():
                return await budgeted_clerk_jwks(self.env, secret_key)

            # Access-protected staging does not support the Workers Cache API.
            if staging:
                return await lookup()
            scope = hashlib.sha256(f"{jwt_key}\0{secret_key}".encode()).hexdigest()
            return await cached_clerk_jwks(scope, lookup)

        claims = await verify_clerk_session_token(
            token=token,
            jwt_key=jwt_key,
            secret_key=getattr(self.env, "CLERK_SECRET_KEY", ""),
            authorized_parties=[stage_url] if staging else authorized_parties_from_env(self.env, request.url),
            jwks_fetcher=jwks_fetcher,
        )
        if staging and (claims.get("iss") != staging_clerk_origin(self.env) or claims.get("azp") != stage_url):
            raise SessionVerificationError("Session token does not belong to the staging site.")
        return claims

    async def optional_workdoe_user(self, request):
        if native_email_code_enabled(self.env):
            try:
                claims = session_from_cookie(
                    request_header(request, "Cookie"),
                    getattr(self.env, "WORKDOE_SECRET_KEY", ""),
                )
                user = await workdoe_user_by_id(self.env, int(claims["user_id"]))
            except (EmailCodeAuthError, KeyError, TypeError, ValueError):
                return None
            return user if user and row_value(user, "status") == "active" else None
        try:
            claims = await self.verified_clerk_claims(request)
        except SessionVerificationError:
            return None
        return await linked_workdoe_user(self.env, claims["sub"])

    async def private_media(self, request, path: str):
        if request.method not in {"GET", "HEAD"}:
            return private_media_response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET, HEAD"},
            )
        if private_media_embedding_blocked(
            request_header(request, "Sec-Fetch-Site"),
            request_header(request, "Sec-Fetch-Mode"),
            request_header(request, "Sec-Fetch-Dest"),
        ):
            return private_media_response("Forbidden", status=403)
        if not hasattr(self.env, "DB") or not hasattr(self.env, "MEDIA"):
            return private_media_response("Media storage is not configured.", status=503)
        try:
            scope, photo_id = media_scope_from_path(path)
        except MediaAccessError:
            return private_media_response("Media not found", status=404)

        if scope == "job":
            return await self.private_job_photo(request, photo_id)
        return await self.private_contractor_photo(request, photo_id)

    async def private_job_photo(self, request, photo_id: int):
        user = await self.optional_workdoe_user(request)
        if not user:
            return private_media_response("Sign in required", status=401)

        result = await db_run(
            self.env,
            """
            SELECT
                job_photos.id,
                job_photos.job_id,
                job_photos.stored_path,
                job_photos.content_type,
                job_photos.is_hidden,
                jobs.client_id,
                jobs.status,
                clients.status AS client_status,
                EXISTS (
                    SELECT 1
                    FROM match_requests
                    WHERE match_requests.job_id = jobs.id AND match_requests.status = 'approved'
                ) AS has_any_approved_match,
                CASE WHEN EXISTS (
                    SELECT 1
                    FROM match_requests
                    WHERE match_requests.job_id = jobs.id
                      AND match_requests.contractor_id = ?
                      AND match_requests.status = 'approved'
                ) THEN 1 ELSE 0 END AS has_approved_match
            FROM job_photos
            JOIN jobs ON jobs.id = job_photos.job_id
            JOIN users AS clients ON clients.id = jobs.client_id
            WHERE job_photos.id = ?
            LIMIT 1
            """,
            row_value(user, "id"),
            photo_id,
        )
        rows = rows_from(result)
        if not rows:
            return private_media_response("Media not found", status=404)
        photo = rows[0]
        if not can_view_job_photo(user, photo):
            if row_value(photo, "is_hidden") or row_value(photo, "status") == "hidden":
                return private_media_response("Media not found", status=404)
            return private_media_response("Forbidden", status=403)

        try:
            key = safe_media_key(row_value(photo, "stored_path"), f"jobs/{row_value(photo, 'job_id')}")
        except MediaAccessError:
            return private_media_response("Media not found", status=404)
        return await self.r2_media_response(request, key, photo)

    async def private_contractor_photo(self, request, photo_id: int):
        user = await self.optional_workdoe_user(request)
        if not user:
            return private_media_response("Sign in required", status=401)
        if row_value(user, "status") != "active":
            return private_media_response("Active account required", status=403)
        result = await db_run(
            self.env,
            """
            SELECT
                contractor_photos.id,
                contractor_photos.contractor_id,
                contractor_photos.stored_path,
                contractor_photos.content_type,
                contractor_photos.is_hidden,
                users.status
            FROM contractor_photos
            JOIN users ON users.id = contractor_photos.contractor_id
            WHERE contractor_photos.id = ?
            LIMIT 1
            """,
            photo_id,
        )
        rows = rows_from(result)
        if not rows:
            return private_media_response("Media not found", status=404)
        photo = rows[0]
        if not can_view_contractor_photo(user, photo):
            return private_media_response("Media not found", status=404)

        try:
            key = safe_media_key(
                row_value(photo, "stored_path"),
                f"contractors/{row_value(photo, 'contractor_id')}",
            )
        except MediaAccessError:
            return private_media_response("Media not found", status=404)
        return await self.r2_media_response(request, key, photo)

    async def r2_media_response(self, request, key: str, photo):
        content_type = str(row_value(photo, "content_type") or "").strip().lower()
        if content_type not in ALLOWED_IMAGE_MIME.values():
            return private_media_response("Media not found", status=404)

        try:
            media_object = (
                await self.env.MEDIA.head(key)
                if request.method == "HEAD"
                else await self.env.MEDIA.get(key)
            )
        except Exception:  # noqa: BLE001 - R2 failures cross the Worker binding boundary.
            return private_media_response("Media is temporarily unavailable.", status=503)
        if media_object is None or media_object is JS_NULL:
            return private_media_response("Media not found", status=404)

        headers = {
            "Cache-Control": "private, no-store",
            "Content-Disposition": inline_content_disposition(
                f"workdoe-photo-{row_value(photo, 'id', 'image')}"
            ),
            "Content-Type": content_type,
            "X-Content-Type-Options": "nosniff",
            "X-Workdoe-Media-Policy": PRIVATE_MEDIA_NOTICE,
        }
        http_etag = getattr(media_object, "httpEtag", "")
        if http_etag:
            headers["ETag"] = http_etag
        body = None if request.method == "HEAD" else getattr(media_object, "body", None)
        return private_media_response(body, status=200, headers=headers)

    async def upload_private_media(self, request, path: str):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not media_uploads_enabled(self.env):
            return json_response(
                {"ok": False, "error": "Photo uploads are not available during this beta."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        if (
            not hasattr(self.env, "DB")
            or not hasattr(self.env, "MEDIA")
            or not hasattr(self.env, "MEDIA_QUEUE")
            or not hasattr(self.env, "IMAGES")
        ):
            return json_response(
                {"ok": False, "error": "Media upload bindings are not configured."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        content_length = parse_request_content_length(request)
        if content_length <= 0:
            return json_response(
                {"ok": False, "error": "Image uploads must include Content-Length."},
                status=411,
                headers={"Cache-Control": "no-store"},
            )
        # Multipart framing is small compared with the bounded source file.
        if content_length > MAX_UPLOAD_BYTES + (16 * 1024):
            return json_response(
                {"ok": False, "error": "Image upload is too large."},
                status=413,
                headers={"Cache-Control": "no-store"},
            )

        try:
            scope, owner_id = media_upload_scope_from_path(path)
        except MediaUploadError:
            return json_response(
                {"ok": False, "error": "Unsupported media upload route."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )

        user = await self.optional_workdoe_user(request)
        if not user:
            return json_response(
                {"ok": False, "error": "Sign in required."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )
        if not await self.can_upload_to_media_owner(scope, owner_id, user):
            return json_response(
                {"ok": False, "error": "You cannot upload media for this record."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        quota_error = await self.media_upload_quota_error(scope, owner_id, user)
        if quota_error:
            return json_response(
                {"ok": False, "error": quota_error},
                status=400,
                headers={"Cache-Control": "no-store"},
            )

        key = ""
        photo_id = None
        request_state = None
        upload_stage = "validating"
        try:
            form_data = await request.formData()
            upload_file = form_file_value(form_data, scope)
            source_details = uploaded_file_details(upload_file)
            await validate_uploaded_file_signature(upload_file, source_details["extension"])
            resource_type = "job_photo" if scope == "job" else "contractor_photo"
            request_state = await begin_idempotent_request(
                self.env,
                row_value(user, "id"),
                idempotency_action(f"media-upload-{scope}", owner_id),
                resource_type,
                request_idempotency_value(request, form_data),
            )
            conflict = idempotency_conflict_response(request_state)
            if conflict:
                return conflict
            if request_state["state"] == "replay":
                replay_photo_id = positive_int(request_state.get("resource_id"))
                if request_state.get("resource_type") != resource_type or not replay_photo_id:
                    return json_response(
                        {"ok": False, "error": "The original image request is unavailable."},
                        status=409,
                        headers={"Cache-Control": "no-store"},
                    )
                if scope == "job":
                    photo_result = await db_run(
                        self.env,
                        "SELECT id, stored_path FROM job_photos WHERE id = ? AND job_id = ? LIMIT 1",
                        replay_photo_id,
                        owner_id,
                    )
                else:
                    photo_result = await db_run(
                        self.env,
                        "SELECT id, stored_path FROM contractor_photos WHERE id = ? AND contractor_id = ? LIMIT 1",
                        replay_photo_id,
                        owner_id,
                    )
                replay_photo = first_row(photo_result)
                if not replay_photo:
                    return json_response(
                        {"ok": False, "error": "The original image request is unavailable."},
                        status=409,
                        headers={"Cache-Control": "no-store"},
                    )
                return json_response(
                    {
                        "ok": True,
                        "photo_id": replay_photo_id,
                        "stored_path": row_value(replay_photo, "stored_path"),
                        "review_queued": True,
                        "replayed": True,
                    },
                    headers={"Cache-Control": "no-store"},
                )
            upload_stage = "sanitizing"
            sanitized = await sanitize_uploaded_image(
                self.env.IMAGES,
                upload_file,
                javascript_object,
            )
            details = sanitized_upload_details(source_details, sanitized)
            key = build_r2_upload_key(scope, owner_id, SANITIZED_IMAGE_EXTENSION)
            await self.env.MEDIA.put(
                key,
                sanitized["body"],
                {
                    "httpMetadata": upload_http_metadata(details),
                    "customMetadata": {
                        "scope": scope,
                        "owner_id": str(owner_id),
                        "uploaded_by": str(row_value(user, "id")),
                        "sanitization": details["sanitization"],
                        "source_width": str(details["source_width"]),
                        "source_height": str(details["source_height"]),
                    },
                },
            )
            upload_stage = "object-stored"
            photo_id = await self.insert_media_metadata(scope, owner_id, user, key, details)
            upload_stage = "metadata-stored"
            payload = media_review_payload(
                scope,
                photo_id,
                owner_id,
                row_value(user, "id"),
                key,
                details,
            )
            await send_queue_json(self.env.MEDIA_QUEUE, payload)
            upload_stage = "review-queued"
            await complete_idempotent_request(
                self.env,
                row_value(user, "id"),
                request_state,
                photo_id,
            )
            upload_stage = "request-completed"
        except IdempotencyError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        except MediaUploadError as exc:
            await cancel_idempotent_request(
                self.env, row_value(user, "id"), request_state
            )
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        except Exception as exc:  # noqa: BLE001 - upload rollback must cover binding errors.
            cleanup = await self.rollback_media_upload(scope, owner_id, photo_id, key)
            await cancel_idempotent_request(
                self.env, row_value(user, "id"), request_state
            )
            failure_payload = {
                "stage": upload_stage,
                "error_type": type(exc).__name__,
                **cleanup,
            }
            try:
                await record_event(
                    self.env,
                    "media-upload-failed",
                    target_type=scope,
                    target_id=owner_id,
                    payload=failure_payload,
                    status="failed",
                )
            except Exception as audit_exc:  # noqa: BLE001 - auditing is best effort.
                print(
                    json.dumps(
                        {
                            "event": "media-upload-failure-audit-failed",
                            "error_type": type(audit_exc).__name__,
                            **failure_payload,
                        }
                    )
                )
            return json_response(
                {"ok": False, "error": "Image upload is temporarily unavailable."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )

        await record_event(
            self.env,
            "media-uploaded",
            target_type=f"{scope}_photo",
            target_id=photo_id,
            payload=payload,
            status="processed",
        )
        await record_event(
            self.env,
            "media-review-queued",
            target_type=f"{scope}_photo",
            target_id=photo_id,
            payload={"queue": "workdoe-media-review", "stored_path": key},
        )
        return json_response(
            {
                "ok": True,
                "photo_id": photo_id,
                "stored_path": key,
                "review_queued": True,
                "replayed": False,
            },
            status=201,
            headers={"Cache-Control": "no-store"},
        )

    async def can_upload_to_media_owner(self, scope: str, owner_id: int, user) -> bool:
        if scope == "job":
            job = first_row(
                await db_run(
                    self.env,
                    """
                    SELECT id, client_id, status
                    FROM jobs
                    WHERE id = ?
                    LIMIT 1
                    """,
                    owner_id,
                )
            )
            return bool(job) and can_upload_job_photo(user, job)
        contractor = first_row(
            await db_run(
                self.env,
                """
                SELECT users.id AS contractor_id, users.status
                FROM users
                JOIN contractor_profiles ON contractor_profiles.user_id = users.id
                WHERE users.id = ?
                  AND users.role = 'contractor'
                LIMIT 1
                """,
                owner_id,
            )
        )
        return bool(contractor) and can_upload_contractor_photo(user, contractor)

    async def media_upload_quota_error(self, scope: str, owner_id: int, user) -> str | None:
        """Check bounded per-resource and per-user media quotas before decoding."""
        if scope == "job":
            resource_result = await db_run(
                self.env,
                "SELECT COUNT(*) AS count FROM job_photos WHERE job_id = ?",
                owner_id,
            )
        else:
            resource_result = await db_run(
                self.env,
                "SELECT COUNT(*) AS count FROM contractor_photos WHERE contractor_id = ?",
                owner_id,
            )
        resource_row = first_row(resource_result) or {}
        recent_since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(
            timespec="seconds"
        )
        user_id = row_value(user, "id")
        recent_result = await db_run(
            self.env,
            """
            SELECT COUNT(*) AS count
            FROM automation_events
            WHERE event_type = 'media-uploaded'
              AND created_at >= ?
              AND json_extract(payload_json, '$.uploaded_by') = ?
            """,
            recent_since,
            user_id,
        )
        recent_row = first_row(recent_result) or {}
        return media_upload_quota_error(
            scope,
            int(row_value(resource_row, "count", 0) or 0),
            int(row_value(recent_row, "count", 0) or 0),
        )

    async def insert_media_metadata(self, scope: str, owner_id: int, user, key: str, details: dict) -> int:
        if scope == "job":
            await db_run(
                self.env,
                """
                INSERT INTO job_photos
                    (job_id, uploaded_by, original_filename, stored_path, content_type,
                     size_bytes, is_hidden, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                """,
                owner_id,
                row_value(user, "id"),
                details["original_filename"],
                key,
                details["content_type"],
                details["size_bytes"],
                utc_now(),
            )
            lookup = await db_run(
                self.env,
                "SELECT id FROM job_photos WHERE stored_path = ? LIMIT 1",
                key,
            )
        else:
            await db_run(
                self.env,
                """
                INSERT INTO contractor_photos
                    (contractor_id, original_filename, stored_path, content_type,
                     size_bytes, is_hidden, created_at)
                VALUES (?, ?, ?, ?, ?, 0, ?)
                """,
                owner_id,
                details["original_filename"],
                key,
                details["content_type"],
                details["size_bytes"],
                utc_now(),
            )
            lookup = await db_run(
                self.env,
                "SELECT id FROM contractor_photos WHERE stored_path = ? LIMIT 1",
                key,
            )
        row = first_row(lookup)
        if not row:
            raise RuntimeError("Uploaded media metadata was not recorded.")
        return int(row_value(row, "id"))

    async def delete_media_metadata(
        self,
        scope: str,
        owner_id: int,
        photo_id: int,
        key: str,
    ) -> None:
        sql, params = media_metadata_delete_statement(scope, photo_id, owner_id, key)
        await db_run(self.env, sql, *params)

    async def rollback_media_upload(
        self,
        scope: str,
        owner_id: int,
        photo_id: int | None,
        key: str,
    ) -> dict:
        cleanup = {
            "metadata_cleanup": "not-created",
            "object_cleanup": "not-created",
        }
        if photo_id:
            try:
                await self.delete_media_metadata(scope, owner_id, photo_id, key)
                cleanup["metadata_cleanup"] = "deleted"
            except Exception as exc:  # noqa: BLE001 - cleanup spans D1 binding failures.
                cleanup["metadata_cleanup"] = f"failed:{type(exc).__name__}"
        if key:
            try:
                await self.env.MEDIA.delete(key)
                cleanup["object_cleanup"] = "deleted"
            except Exception as exc:  # noqa: BLE001 - cleanup spans R2 binding failures.
                cleanup["object_cleanup"] = f"failed:{type(exc).__name__}"
        return cleanup

    async def request_auth_code(self, request):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not native_email_code_enabled(self.env):
            return json_response(
                {"ok": False, "error": "Email-code sign-in is not enabled."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        if not all(
            hasattr(self.env, binding)
            for binding in ("DB", "EMAIL_QUEUE")
        ):
            return json_response(
                {"ok": False, "error": "Workdoe sign-in services are not configured."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )

        try:
            body = await request_json_object(request, max_bytes=MAX_AUTH_BODY_BYTES)
            await verify_turnstile_for_request(
                self.env,
                request,
                body,
                action="login" if body.get("mode") == "signin" else "start",
            )
            secret = getattr(self.env, "WORKDOE_SECRET_KEY", "")
            email = normalize_email(body.get("email"))
            if not valid_email(email):
                raise EmailCodeAuthError("Enter a valid email address.")
            mode = "signin" if body.get("mode") == "signin" else "start"
            intent = normalize_auth_intent(body.get("intent"))
            requested_role = role_for_intent(intent)
            display_name = compact_auth_text(body.get("display_name"), 120)
            company_name = compact_auth_text(body.get("company_name"), 160)
            selected_job_id = 0
            try:
                selected_job_id = max(0, int(body.get("selected_job_id") or 0))
            except (TypeError, ValueError):
                selected_job_id = 0

            existing_result = await db_run(
                self.env,
                """
                SELECT id, email, role, display_name, company_name, status
                FROM users
                WHERE email = ?
                LIMIT 1
                """,
                email,
            )
            existing = first_row(existing_result)
            if mode == "signin" and not existing:
                raise EmailCodeAuthError(
                    "No Workdoe account uses that email yet. Choose Start to create one.",
                    404,
                )
            if existing and row_value(existing, "status") != "active":
                raise EmailCodeAuthError("This Workdoe account is not active.", 403)
            if existing and row_value(existing, "role") == "admin":
                raise EmailCodeAuthError("Administrator email-code access is disabled.", 403)
            if not existing and not display_name:
                raise EmailCodeAuthError(
                    "Add a public business name or non-identifying handle to create a Workdoe account."
                )
            if not existing and contains_disallowed_personal_data(
                (display_name, company_name)
            ):
                raise EmailCodeAuthError(
                    "Do not include an email address, phone number, or exact street address in your public business name or handle."
                )

            role = fixed_account_role(
                row_value(existing, "role") if existing else None,
                requested_role,
            )
            display_name = row_value(existing, "display_name") if existing else display_name
            company_name = row_value(existing, "company_name", "") if existing else company_name
            if role != "contractor":
                selected_job_id = 0

            email_rate_result = await db_run(
                self.env,
                """
                SELECT COUNT(*) AS request_count
                FROM login_codes
                WHERE email = ?
                  AND datetime(created_at) >= datetime('now', '-15 minutes')
                """,
                email,
            )
            email_rate = int(row_value(first_row(email_rate_result), "request_count", 0) or 0)
            ip_hash = hash_identifier(remote_ip_from_headers(request.headers), secret)
            ip_rate_result = await db_run(
                self.env,
                """
                SELECT COUNT(*) AS request_count
                FROM login_codes
                WHERE request_ip_hash = ?
                  AND datetime(created_at) >= datetime('now', '-15 minutes')
                """,
                ip_hash,
            )
            ip_rate = int(row_value(first_row(ip_rate_result), "request_count", 0) or 0)
            if email_rate >= AUTH_REQUESTS_PER_EMAIL or ip_rate >= AUTH_REQUESTS_PER_IP:
                raise EmailCodeAuthError(
                    "Too many sign-in codes were requested. Wait 15 minutes and try again.",
                    429,
                )

            issued_at = datetime.now(timezone.utc)
            expires_at = issued_at + timedelta(seconds=CHALLENGE_TTL_SECONDS)
            code = generate_code()
            await db_run(
                self.env,
                """
                UPDATE login_codes
                SET used_at = ?
                WHERE email = ? AND used_at IS NULL
                """,
                issued_at.isoformat(timespec="seconds"),
                email,
            )
            result = await db_run(
                self.env,
                """
                INSERT INTO login_codes
                    (email, role, display_name, company_name, intent,
                     selected_job_id, code_hash, expires_at, used_at,
                     created_at, attempt_count, request_ip_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 0, ?)
                """,
                email,
                role,
                display_name,
                company_name,
                intent,
                selected_job_id or None,
                hash_code(code, secret),
                expires_at.isoformat(timespec="seconds"),
                issued_at.isoformat(timespec="seconds"),
                ip_hash,
            )
            code_id = last_insert_id(result)
            if not code_id:
                raise EmailCodeAuthError("Workdoe could not create a sign-in code.", 500)
            try:
                await send_queue_json(
                    self.env.EMAIL_QUEUE,
                    {
                        "type": "login-code",
                        "to": email,
                        "code": code,
                        "expires_minutes": 10,
                        "intent": "post a project" if role == "client" else "find local work",
                    }
                )
            except Exception as exc:
                await db_run(
                    self.env,
                    "UPDATE login_codes SET used_at = ? WHERE id = ?",
                    utc_now(),
                    code_id,
                )
                await record_event(
                    self.env,
                    "login-code-queue-failed",
                    target_type="login_code",
                    target_id=code_id,
                    payload={"error_type": type(exc).__name__},
                    status="failed",
                )
                raise EmailCodeAuthError("Workdoe could not send the sign-in code.", 503) from exc

            await record_event(
                self.env,
                "login-code-requested",
                target_type="login_code",
                target_id=code_id,
                payload={"mode": mode, "role": role},
                status="processed",
            )
            return json_response(
                {
                    "ok": True,
                    "challenge_token": challenge_token(code_id, email, secret),
                    "expires_minutes": 10,
                    "message": "Code sent. Check your email for the six-digit Workdoe code.",
                },
                status=202,
                headers={"Cache-Control": "no-store"},
            )
        except TurnstileError:
            return json_response(
                {"ok": False, "error": "Complete the security check and try again."},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        except (EmailCodeAuthError, OnboardingError) as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=getattr(exc, "status", 400),
                headers={"Cache-Control": "no-store"},
            )
        except Exception as exc:  # noqa: BLE001 - Worker bindings may raise JS-backed errors.
            await record_event(
                self.env,
                "login-code-request-failed",
                payload={"error_type": type(exc).__name__},
                status="failed",
            )
            return json_response(
                {
                    "ok": False,
                    "error": "Sign-in is temporarily unavailable. Please try again.",
                },
                status=503,
                headers={"Cache-Control": "no-store"},
            )

    async def verify_auth_code(self, request):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not native_email_code_enabled(self.env) or not hasattr(self.env, "DB"):
            return json_response(
                {"ok": False, "error": "Email-code sign-in is not configured."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )

        try:
            body = await request_json_object(request, max_bytes=MAX_AUTH_BODY_BYTES)
            secret = getattr(self.env, "WORKDOE_SECRET_KEY", "")
            challenge = verified_token(
                body.get("challenge_token"),
                secret,
                "challenge",
            )
            code = normalize_code(body.get("code"))
            if len(code) != 6 or not code.isdigit():
                raise EmailCodeAuthError("Enter the six-digit code.")
            result = await db_run(
                self.env,
                """
                SELECT *
                FROM login_codes
                WHERE id = ? AND email = ?
                LIMIT 1
                """,
                int(challenge["code_id"]),
                normalize_email(challenge["email"]),
            )
            login_code = first_row(result)
            if (
                not login_code
                or row_value(login_code, "used_at")
                or row_value(login_code, "expires_at", "") < utc_now()
                or int(row_value(login_code, "attempt_count", 0) or 0) >= MAX_CODE_ATTEMPTS
            ):
                raise EmailCodeAuthError("That sign-in code expired. Request a new one.", 401)

            if not tokens_match(
                hash_code(code, secret),
                row_value(login_code, "code_hash", ""),
            ):
                failed_at = utc_now()
                await db_run(
                    self.env,
                    """
                    UPDATE login_codes
                    SET attempt_count = attempt_count + 1,
                        used_at = CASE
                            WHEN attempt_count + 1 >= ? THEN ?
                            ELSE used_at
                        END
                    WHERE id = ?
                      AND used_at IS NULL
                      AND attempt_count < ?
                    """,
                    MAX_CODE_ATTEMPTS,
                    failed_at,
                    row_value(login_code, "id"),
                    MAX_CODE_ATTEMPTS,
                )
                raise EmailCodeAuthError("That code did not match.", 401)

            authenticated_at = utc_now()
            login_code_consume_result = await db_run(
                self.env,
                """
                UPDATE login_codes
                SET used_at = ?,
                    attempt_count = attempt_count + 1
                WHERE id = ?
                  AND used_at IS NULL
                  AND expires_at >= ?
                  AND attempt_count < ?
                """,
                authenticated_at,
                row_value(login_code, "id"),
                authenticated_at,
                MAX_CODE_ATTEMPTS,
            )
            if d1_change_count(login_code_consume_result) != 1:
                raise EmailCodeAuthError(
                    "That sign-in code expired. Request a new one.",
                    401,
                )

            user_result = await db_run(
                self.env,
                """
                SELECT id, email, role, display_name, company_name, status
                FROM users
                WHERE email = ?
                LIMIT 1
                """,
                row_value(login_code, "email"),
            )
            user = first_row(user_result)
            created = False
            if not user:
                created_at = utc_now()
                create_result = await db_run(
                    self.env,
                    """
                    INSERT OR IGNORE INTO users
                        (email, password_hash, role, display_name, company_name,
                         status, email_verified, auth_provider, external_subject,
                         created_at)
                    VALUES (?, 'email-code-only', ?, ?, ?, 'active', 1, ?, ?, ?)
                    """,
                    row_value(login_code, "email"),
                    row_value(login_code, "role"),
                    row_value(login_code, "display_name"),
                    row_value(login_code, "company_name", ""),
                    EMAIL_CODE_AUTH_PROVIDER,
                    row_value(login_code, "email"),
                    created_at,
                )
                created = d1_change_count(create_result) == 1
                user = await workdoe_user_by_id_from_email(
                    self.env,
                    row_value(login_code, "email"),
                )
                if not user:
                    raise EmailCodeAuthError("Workdoe could not create the account.", 500)

            if row_value(user, "status") != "active":
                raise EmailCodeAuthError("This Workdoe account is not active.", 403)
            await ensure_role_profile(self.env, user, utc_now())
            await record_event(
                self.env,
                "email-code-authenticated",
                target_type="user",
                target_id=row_value(user, "id"),
                payload={"created": created, "role": row_value(user, "role")},
                status="processed",
            )
            token = session_token(row_value(user, "id"), secret)
            return json_response(
                {
                    "ok": True,
                    "authenticated": True,
                    "created": created,
                    "workdoe_user": workdoe_user_json(user),
                    "redirect_url": auth_redirect_for_user(user, body.get("next")),
                },
                headers={
                    "Cache-Control": "no-store",
                    "Set-Cookie": session_cookie(token),
                },
            )
        except (EmailCodeAuthError, OnboardingError, KeyError, TypeError, ValueError) as exc:
            return json_response(
                {"ok": False, "error": str(exc) or "Sign-in code was not accepted."},
                status=getattr(exc, "status", 400),
                headers={"Cache-Control": "no-store"},
            )
        except Exception as exc:  # noqa: BLE001 - Worker bindings may raise JS-backed errors.
            await record_event(
                self.env,
                "login-code-verification-failed",
                payload={"error_type": type(exc).__name__},
                status="failed",
            )
            return json_response(
                {
                    "ok": False,
                    "error": "Verification is temporarily unavailable. Please try again.",
                },
                status=503,
                headers={"Cache-Control": "no-store"},
            )

    async def auth_logout(self, request):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        native_auth = native_email_code_enabled(self.env)
        if not native_auth:
            try:
                secret_key = str(getattr(self.env, "CLERK_SECRET_KEY", "") or "").strip()
                if secret_key:
                    await asyncio.wait_for(
                        self.revoke_clerk_logout_session(request, secret_key),
                        timeout=CLERK_LOGOUT_TIMEOUT_SECONDS,
                    )
            except Exception:  # noqa: BLE001 - Clerk fetch errors cross the JS boundary.
                print(json.dumps({"event": "clerk-session-revoke-failed"}))
        cleared_session = (
            clear_session_cookie()
            if native_auth else "__session=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"
        )
        return json_response(
            {"ok": True}, headers={"Cache-Control": "no-store"},
            set_cookies=(cleared_session, clear_job_draft_cookie()),
        )

    async def revoke_clerk_logout_session(self, request, secret_key: str) -> None:
        claims = await self.verified_clerk_claims(request)
        options = {}
        try:
            from js import AbortController
        except ImportError:  # pragma: no cover - the JS API is only available inside Workers.
            controller = None
        else:
            controller = AbortController.new()
            options["signal"] = controller.signal
        try:
            response = await fetch(
                f"https://api.clerk.com/v1/sessions/{claims['sid']}/revoke",
                method="POST", redirect="manual",
                headers={"Accept": "application/json", "Authorization": f"Bearer {secret_key}"},
                **options,
            )
            if not response.ok:
                raise SessionVerificationError("Clerk session revocation was not accepted.")
        except asyncio.CancelledError:
            if controller is not None:
                controller.abort()
            raise

    async def auth_session(self, request):
        if request.method != "GET":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {
                    "authenticated": False,
                    "error": "D1 binding is required before sessions can load.",
                },
                status=503,
                headers={"Cache-Control": "no-store"},
            )

        if native_email_code_enabled(self.env):
            user = await self.optional_workdoe_user(request)
            if not user:
                return json_response(
                    {
                        "authenticated": False,
                        "onboarding_required": False,
                        "workdoe_user": None,
                    },
                    status=401,
                    headers={"Cache-Control": "no-store"},
                )
            return json_response(
                {
                    "authenticated": True,
                    "onboarding_required": False,
                    "workdoe_user": {"role": row_value(user, "role")},
                },
                headers={"Cache-Control": "no-store"},
            )

        try:
            claims = await self.verified_clerk_claims(request)
        except SessionVerificationError as exc:
            print(
                json.dumps(
                    {
                        "event": "clerk-session-verification-failed",
                        "reason": str(exc),
                    }
                )
            )
            return json_response(
                {"authenticated": False, "error": "Session token not verified."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )

        lookup = await db_run(
            self.env,
            """
            SELECT role, status
            FROM users
            WHERE auth_provider = 'clerk'
              AND external_subject = ?
            LIMIT 1
            """,
            claims["sub"],
        )
        rows = rows_from(lookup)
        if not rows:
            return json_response(
                {
                    "authenticated": True,
                    "onboarding_required": True,
                    "workdoe_user": None,
                },
                headers={"Cache-Control": "no-store"},
            )

        user = rows[0]
        if row_value(user, "status") != "active":
            return json_response(
                {
                    "authenticated": False,
                    "error": "Workdoe account is not active.",
                },
                status=403,
                headers={"Cache-Control": "no-store"},
            )

        return json_response(
            {
                "authenticated": True,
                "onboarding_required": False,
                "workdoe_user": {"role": row_value(user, "role")},
            },
            headers={"Cache-Control": "no-store"},
        )

    async def auth_onboard(self, request):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB"):
            return json_response(
                {
                    "ok": False,
                    "error": "D1 binding is required before Clerk onboarding can run.",
                },
                status=503,
                headers={"Cache-Control": "no-store"},
            )

        try:
            claims = await self.verified_clerk_claims(request)
        except SessionVerificationError:
            return json_response(
                {"ok": False, "error": "Session token not verified."},
                status=401,
                headers={"Cache-Control": "no-store"},
            )

        try:
            profile = onboarding_profile(await request_json_object(request))
        except OnboardingError:
            return json_response(
                {"ok": False, "error": "Onboarding request was not accepted."},
                status=400,
                headers={"Cache-Control": "no-store"},
            )

        subject = claims["sub"]
        key = f"clerk-onboard:{hashlib.sha256(subject.encode('utf-8')).hexdigest()}"
        limited = await worker_write_rate_limit_response(self.env, key)
        if limited is not None:
            return limited

        try:
            secret_key = str(getattr(self.env, "CLERK_SECRET_KEY", "") or "").strip()
            if not secret_key:
                raise RuntimeError("Clerk user lookup is not configured.")
            clerk_user = await fetch_clerk_user(subject, secret_key)
        except Exception:  # noqa: BLE001 - sanitize JS transport/stream failures without logging provider data.
            return json_response(
                {"ok": False, "error": "Could not check your verified email. Please try again."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )

        try:
            claims = claims_with_verified_clerk_email(claims, clerk_user)
            payload = onboarding_payload(claims, profile)
        except OnboardingError:
            return json_response(
                {"ok": False, "error": "Onboarding request was not accepted."},
                status=400,
                headers={"Cache-Control": "no-store"},
            )

        try:
            user, created = await provision_clerk_account(self.env, subject, payload, utc_now())
        except Exception:  # noqa: BLE001 - D1 failures cross the Worker binding boundary.
            return json_response(
                {"ok": False, "error": "Could not finish creating your workspace. Please try again."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        if not user:
            return json_response(
                {"ok": False, "error": "A Workdoe account already uses this email."},
                status=409,
                headers={"Cache-Control": "no-store"},
            )
        if row_value(user, "status") != "active":
            return json_response(
                {"ok": False, "error": "Workdoe account is not active."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        return json_response(
            {"ok": True, "created": created, "workdoe_user": workdoe_user_json(user)},
            status=201 if created else 200,
            headers={"Cache-Control": "no-store"},
        )

    async def handle_clerk_webhook(self, request):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST"},
            )
        if not clerk_production_configuration_ready(self.env):
            return json_response(
                {"ok": False, "error": "Clerk authentication is not configured."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        if not getattr(self.env, "CLERK_WEBHOOK_SECRET", ""):
            return json_response(
                {
                    "ok": False,
                    "error": "CLERK_WEBHOOK_SECRET is required before Clerk webhooks are accepted.",
                },
                status=503,
            )

        content_length = parse_request_content_length(request)
        if content_length <= 0:
            return json_response(
                {"ok": False, "error": "Webhook requests must include Content-Length."},
                status=411,
                headers={"Cache-Control": "no-store"},
            )
        if content_length > MAX_CLERK_WEBHOOK_BODY_BYTES:
            return json_response(
                {"ok": False, "error": "Webhook request body is too large."},
                status=413,
                headers={"Cache-Control": "no-store"},
            )
        try:
            raw_body = await asyncio.wait_for(
                read_json_stream_bytes(
                    request.body, max_bytes=content_length, max_chunks=MAX_CLERK_WEBHOOK_BODY_CHUNKS,
                    label="Webhook request",
                ),
                timeout=CLERK_WEBHOOK_BODY_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            return json_response(
                {"ok": False, "error": "Webhook request body timed out."},
                status=408,
                headers={"Cache-Control": "no-store"},
            )
        except JsonDataError:
            raw_body = b""
        if len(raw_body) != content_length:
            return json_response(
                {"ok": False, "error": "Webhook request body is invalid."},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        try:
            event = verify_svix_signature(
                secret=self.env.CLERK_WEBHOOK_SECRET,
                headers=request.headers,
                raw_body=raw_body,
            )
        except SvixVerificationError:
            return json_response(
                {"ok": False, "error": "Webhook verification failed."},
                status=400,
                headers={"Cache-Control": "no-store"},
            )

        sync = await sync_linked_clerk_user(self.env, event)
        if sync["action"] != "ignored":
            await record_event(
                self.env,
                "clerk-webhook-verified",
                target_type=event["type"],
                payload={"sync": sync},
                status="processed",
            )
        return json_response(
            {
                "ok": True,
                "verified": True,
                "sync": "linked_users_only",
            },
            status=202,
        )

    async def scheduled(self, controller, env, ctx):
        # Class entrypoints receive their bindings on self, even if the event env is null.
        env = self.env
        if is_staging_environment(env) or workspace_mode(env) != "normal":
            return
        cron = getattr(controller, "cron", "")
        if cron == EXPIRE_CODES_CRON:
            await expire_local_auth_tokens(env)
            return
        if cron == STALE_MATCH_REMINDERS_CRON:
            await queue_stale_match_reminders(env)
            return
        if cron == MODERATION_DIGEST_CRON:
            await queue_moderation_digest(env)
            return
        await record_event(env, "unknown-cron", payload={"cron": cron}, status="failed")

    async def queue(self, batch, env=None, ctx=None):
        if workspace_mode(self.env) != "normal":
            for message in batch.messages:
                retry_message(message, delay_seconds=RECOVERY_RETRY_SECONDS)
            return
        queue_name = getattr(batch, "queue", "unknown")
        staging = is_staging_environment(self.env)
        media_queue = "workdoe-staging-media-review" if staging else "workdoe-media-review"
        if staging and queue_name != media_queue:
            for message in batch.messages:
                if queue_name == "workdoe-staging-email":
                    ack_message(message)
                else:
                    retry_message(message, delay_seconds=RECOVERY_RETRY_SECONDS)
            return
        if queue_name not in {"workdoe-email", media_queue}:
            for message in batch.messages:
                retry_message(message, delay_seconds=RECOVERY_RETRY_SECONDS)
            return
        email = queue_name == "workdoe-email"
        for message in batch.messages:
            try:
                body = getattr(message, "body", {})
                if email:
                    await dispatch_queue_json(self.env, message, body, queue_name, process_email_queue_message)
                else:
                    await dispatch_media_review_message(self.env, message, body, queue_name)
            except Exception:  # noqa: BLE001 - isolate JS-backed binding failures to their broker receipt.
                retry_message(message)
                print(json.dumps({
                    "event": "queue-message-processing-failed",
                    "binding": "EMAIL_QUEUE" if email else "MEDIA_QUEUE",
                    "attempts": getattr(message, "attempts", 0),
                }, sort_keys=True))


async def expire_local_auth_tokens(env) -> None:
    await db_run(
        env,
        """
        UPDATE login_codes
        SET used_at = ?
        WHERE used_at IS NULL
          AND datetime(expires_at) < datetime('now')
        """,
        utc_now(),
    )
    await db_run(
        env,
        """
        UPDATE password_reset_tokens
        SET used_at = ?
        WHERE used_at IS NULL
          AND datetime(expires_at) < datetime('now')
        """,
        utc_now(),
    )
    await record_event(env, "expire-login-codes", status="processed")


async def sync_linked_clerk_user(env, event: dict) -> dict:
    sync = clerk_user_sync_payload(event)
    if not sync["syncable"]:
        return {"action": "ignored", "reason": sync["reason"]}

    clerk_user_id = sync["clerk_user_id"]
    lookup = await db_run(
        env,
        """
        SELECT id
        FROM users
        WHERE auth_provider = 'clerk'
          AND external_subject = ?
        LIMIT 1
        """,
        clerk_user_id,
    )
    rows = rows_from(lookup)
    if not rows:
        return {"action": "skipped", "reason": "no-linked-workdoe-user"}

    user_id = rows[0]["id"]
    # Profile events cannot lift local moderation or an earlier provider disable.
    status_sql = """
        UPDATE users
        SET status = CASE WHEN ? = 'suspended' THEN 'suspended' ELSE status END
        WHERE id = ? AND auth_provider = 'clerk' AND external_subject = ?
        """
    status_params = (sync["status"], user_id, clerk_user_id)
    if sync["status"] == "suspended":
        # The receipt advances in the same D1 transaction as the restriction.
        status_result, _ = await db_batch(env, (
            (status_sql, status_params),
            ("""
            INSERT INTO automation_events (event_type, target_type, target_id, payload_json, status, created_at)
            SELECT 'clerk-provider-restriction', 'user', ?, '{}', 'processed', ?
            WHERE changes() = 1
            """, (user_id, utc_now())),
        ))
    else:
        status_result = await db_run(env, status_sql, *status_params)
    if d1_change_count(status_result) != 1:
        return {"action": "skipped", "reason": "identity-link-changed"}

    email = sync.get("email", "")
    if email:
        conflict = await db_run(
            env,
            """
            SELECT id
            FROM users
            WHERE email = ?
              AND id != ?
            LIMIT 1
            """,
            email,
            user_id,
        )
        if rows_from(conflict):
            return {"action": "blocked", "reason": "email-conflict", "user_id": user_id}
        email_result = await db_run(
            env,
            """
            UPDATE users
            SET email = ?,
                email_verified = ?
            WHERE id = ? AND auth_provider = 'clerk' AND external_subject = ?
            """,
            email,
            sync["email_verified"],
            user_id,
            clerk_user_id,
        )
        if d1_change_count(email_result) != 1:
            return {"action": "skipped", "reason": "identity-link-changed"}
        return {"action": "updated", "user_id": user_id}

    return {"action": "status-updated", "user_id": user_id}


async def queue_stale_match_reminders(env) -> None:
    if not marketplace_email_enabled(env):
        return
    result = await db_run(
        env,
        """
        SELECT
            match_requests.id,
            jobs.title AS job_title,
            jobs.city,
            jobs.state,
            clients.email AS client_email,
            contractors.display_name AS contractor_name
        FROM match_requests
        JOIN jobs ON jobs.id = match_requests.job_id
        JOIN users AS clients ON clients.id = jobs.client_id
        LEFT JOIN client_profiles ON client_profiles.user_id = clients.id
        JOIN users AS contractors ON contractors.id = match_requests.contractor_id
        WHERE match_requests.status = 'pending'
          AND COALESCE(client_profiles.notification_preference, 'workdoe') = 'email'
          AND client_profiles.email_reminder_consent_at IS NOT NULL
          AND datetime(match_requests.created_at) <= datetime('now', '-24 hours')
          AND NOT EXISTS (
              SELECT 1
              FROM automation_events
              WHERE automation_events.event_type = 'stale-match-reminder'
                AND automation_events.target_type = 'match_request'
                AND automation_events.target_id = match_requests.id
                AND date(automation_events.created_at) = date('now')
          )
        ORDER BY match_requests.created_at ASC
        LIMIT 50
        """,
    )
    for row in rows_from(result):
        payload = {
            "type": "stale-match-reminder",
            "match_request_id": row["id"],
            "to": row["client_email"],
            "job_title": row["job_title"],
            "location": f"{row['city']}, {row['state']}",
            "contractor_name": row["contractor_name"],
            "preferences_url": "https://workdoe.com/client/profile#bid-reminders",
        }
        await send_queue_json(env.EMAIL_QUEUE, payload)
        await record_event(
            env,
            "stale-match-reminder",
            target_type="match_request",
            target_id=row["id"],
            payload=email_audit_metadata(
                payload,
                getattr(env, "WORKDOE_SECRET_KEY", ""),
            ),
        )


async def queue_repeat_provider_invitation_email(
    env,
    contractor_id: int,
    job_id: int,
    job_title: str,
    city: str,
    state: str,
) -> bool:
    if not marketplace_email_enabled(env):
        return False
    recipient = first_row(
        await db_run(
            env,
            """
            SELECT email
            FROM users
            WHERE id = ? AND role = 'contractor' AND status = 'active'
            LIMIT 1
            """,
            contractor_id,
        )
    )
    payload = {
        "type": "repeat-provider-invitation",
        "contractor_id": contractor_id,
        "job_id": job_id,
        "to": row_value(recipient, "email", ""),
        "job_title": job_title,
        "location": f"{city}, {state}",
        "job_url": f"https://workdoe.com/jobs/{job_id}",
    }
    try:
        await send_queue_json(env.EMAIL_QUEUE, payload)
    except Exception as exc:  # noqa: BLE001 - Queue binding errors are JS-backed.
        await record_event_best_effort(
            env,
            "repeat-provider-invitation-email-queue-failed",
            target_type="job",
            target_id=job_id,
            payload={"error_type": type(exc).__name__},
            status="failed",
        )
        return False
    await record_event_best_effort(
        env,
        "repeat-provider-invitation-email",
        target_type="job",
        target_id=job_id,
        payload=email_audit_metadata(
            payload,
            getattr(env, "WORKDOE_SECRET_KEY", ""),
        ),
        status="queued",
    )
    return True


async def queue_operator_report_alert(
    env,
    *,
    report_id: int,
    target_type: str,
    target_id: int,
) -> bool:
    """Queue a generic operator alert without report content or account details."""
    if is_staging_environment(env):
        return False
    payload = {
        "type": "operator-report-alert",
        "to": getattr(env, "WORKDOE_ADMIN_EMAIL", ""),
        "report_id": report_id,
        "target_type": target_type,
        "target_id": target_id,
        "moderation_url": "https://workdoe.com/admin",
    }
    try:
        await send_queue_json(env.EMAIL_QUEUE, payload)
    except Exception as exc:  # noqa: BLE001 - Queue binding errors are JS-backed.
        await record_event_best_effort(
            env,
            "operator-report-alert-queue-failed",
            target_type=target_type,
            target_id=target_id,
            payload={"report_id": report_id, "error_type": type(exc).__name__},
            status="failed",
        )
        return False
    await record_event_best_effort(
        env,
        "operator-report-alert",
        target_type=target_type,
        target_id=target_id,
        payload={
            **email_audit_metadata(payload, getattr(env, "WORKDOE_SECRET_KEY", "")),
            "report_id": report_id,
        },
        status="queued",
    )
    return True


async def queue_contractor_lead_alert_fanout(env, job_id: int) -> bool:
    if not marketplace_email_enabled(env):
        return False
    payload = {"type": "contractor-lead-alert-fanout", "job_id": job_id}
    try:
        await send_queue_json(env.EMAIL_QUEUE, payload)
    except Exception as exc:  # noqa: BLE001 - Queue binding errors are JS-backed.
        await record_event_best_effort(
            env,
            "contractor-lead-alert-fanout-queue-failed",
            target_type="job",
            target_id=job_id,
            payload={"error_type": type(exc).__name__},
            status="failed",
        )
        return False
    await record_event_best_effort(
        env,
        "contractor-lead-alert-fanout",
        target_type="job",
        target_id=job_id,
        payload={"job_id": job_id},
        status="queued",
    )
    return True


async def process_contractor_lead_alert_fanout(env, job_id: int) -> int:
    if not marketplace_email_enabled(env):
        return 0
    candidates = rows_from(
        await db_run(
            env,
            lead_alert_candidates_query(),
            job_id,
        )
    )
    queued_count = 0
    for candidate in candidates:
        contractor_id = positive_int(row_value(candidate, "contractor_id"))
        delivery_id = positive_int(row_value(candidate, "delivery_id"))
        timestamp = utc_now()
        if not delivery_id:
            await db_run(
                env,
                """
                INSERT OR IGNORE INTO contractor_lead_alert_deliveries
                    (contractor_id, job_id, status, created_at, queued_at,
                     sent_at, updated_at)
                VALUES (?, ?, 'pending', ?, NULL, NULL, ?)
                """,
                contractor_id,
                job_id,
                timestamp,
                timestamp,
            )
            delivery = first_row(
                await db_run(
                    env,
                    """
                    SELECT id, status
                    FROM contractor_lead_alert_deliveries
                    WHERE contractor_id = ? AND job_id = ?
                    LIMIT 1
                    """,
                    contractor_id,
                    job_id,
                )
            )
            delivery_id = positive_int(row_value(delivery, "id"))
            if row_value(delivery, "status") not in {"pending", "failed"}:
                continue
        if not delivery_id:
            continue
        email_payload = {
            "type": "contractor-new-lead",
            "to": row_value(candidate, "contractor_email", ""),
            "job_title": row_value(candidate, "job_title", ""),
            "service_name": service_label(
                row_value(candidate, "service_slug", ""),
                row_value(candidate, "category", "local work"),
            ),
            "location": (
                f"{row_value(candidate, 'city', '')}, "
                f"{row_value(candidate, 'state', '')}"
            ),
            "job_url": f"https://workdoe.com/jobs/{job_id}",
            "settings_url": "https://workdoe.com/leads#saved-lead-alerts",
            "lead_alert_delivery_id": delivery_id,
        }
        try:
            await send_queue_json(env.EMAIL_QUEUE, email_payload)
        except Exception:
            await db_run(
                env,
                """
                UPDATE contractor_lead_alert_deliveries
                SET status = 'failed', updated_at = ?
                WHERE id = ?
                """,
                utc_now(),
                delivery_id,
            )
            raise
        await db_run(
            env,
            """
            UPDATE contractor_lead_alert_deliveries
            SET status = 'queued', queued_at = ?, updated_at = ?
            WHERE id = ?
            """,
            timestamp,
            timestamp,
            delivery_id,
        )
        await record_event_best_effort(
            env,
            "contractor-new-lead-email",
            target_type="contractor_lead_alert",
            target_id=delivery_id,
            payload={
                **email_audit_metadata(
                    email_payload,
                    getattr(env, "WORKDOE_SECRET_KEY", ""),
                ),
                "job_id": job_id,
                "contractor_id": contractor_id,
            },
            status="queued",
        )
        queued_count += 1
    return queued_count


async def queue_moderation_digest(env) -> None:
    already_sent = await db_run(
        env,
        """
        SELECT id
        FROM automation_events
        WHERE event_type = 'moderation-digest'
          AND date(created_at) = date('now')
        LIMIT 1
        """,
    )
    if rows_from(already_sent):
        return

    summary_result = await db_run(
        env,
        """
        SELECT
            (SELECT COUNT(*) FROM reports WHERE status = 'open') AS open_reports,
            (SELECT COUNT(*) FROM job_photos WHERE is_hidden = 1) AS hidden_job_photos,
            (SELECT COUNT(*) FROM contractor_photos WHERE is_hidden = 1) AS hidden_contractor_photos,
            (SELECT COUNT(*) FROM messages WHERE is_hidden = 1) AS hidden_messages,
            (SELECT COUNT(*) FROM users WHERE status = 'suspended') AS suspended_users
        """,
    )
    rows = rows_from(summary_result)
    summary = rows[0] if rows else {}
    payload = {
        "type": "moderation-digest",
        "to": getattr(env, "WORKDOE_ADMIN_EMAIL", ""),
        "summary": summary,
    }
    await send_queue_json(env.EMAIL_QUEUE, payload)
    await record_event(
        env,
        "moderation-digest",
        payload={
            **email_audit_metadata(
                payload,
                getattr(env, "WORKDOE_SECRET_KEY", ""),
            ),
            "summary": summary,
        },
    )


def ack_message(message) -> None:
    ack = getattr(message, "ack", None)
    if callable(ack):
        ack()


def retry_message(message, *, delay_seconds: int | None = None) -> None:
    if delay_seconds is not None and (
        type(delay_seconds) is not int or not 1 <= delay_seconds <= 86400
    ):
        raise ValueError("Queue retry delay must be between 1 and 86400 seconds.")
    retry = getattr(message, "retry", None)
    if callable(retry):
        if delay_seconds is None:
            retry()
        else:
            retry(javascript_object({"delaySeconds": delay_seconds}))


def queue_payload_shape(body) -> dict:
    if not isinstance(body, dict):
        return {"payload_type": type(body).__name__}
    return {"payload_type": "dict", "payload_key_count": len(body)}


def last_insert_id(result) -> int | None:
    if isinstance(result, dict):
        meta = result.get("meta") or result.get("result", {}).get("meta") or {}
    else:
        meta = getattr(result, "meta", {}) or {}
    for key in ("last_row_id", "lastRowId", "last_insert_rowid"):
        value = row_value(meta, key)
        if value:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


JOB_REPORT_ACCESS_SQL = """
    SELECT 1
    FROM jobs
    JOIN users AS owner ON owner.id = jobs.client_id
    JOIN users AS reporter ON reporter.id = ?
    WHERE jobs.id = ? AND reporter.status = 'active' AND (
        reporter.role = 'admin' OR (
            reporter.role = 'contractor' AND owner.status = 'active'
            AND jobs.status IN ('open', 'closed') AND (
                EXISTS (
                    SELECT 1 FROM match_requests AS own_request
                    WHERE own_request.job_id = jobs.id AND own_request.contractor_id = reporter.id
                ) OR (jobs.status = 'open' AND NOT EXISTS (
                    SELECT 1 FROM match_requests AS approved_request
                    WHERE approved_request.job_id = jobs.id AND approved_request.status = 'approved'
                ))
            )
        )
    )
"""


def report_unavailable_response() -> Response:
    return json_response(
        {"ok": False, "error": "That item is no longer available to report."},
        status=404, headers={"Cache-Control": "no-store"},
    )


async def report_target_visible_to_user(env, user, target_type: str, target_id: int) -> bool:
    role = row_value(user, "role")
    user_id = row_value(user, "id")
    if target_type == "job":
        return first_row(await db_run(env, JOB_REPORT_ACCESS_SQL, user_id, target_id)) is not None
    if role == "admin":
        result = await db_run(env, report_target_query(target_type), target_id)
        return first_row(result) is not None
    if target_type == "profile":
        contractor = await public_contractor_for_profile(env, target_id)
        return (
            user_id != target_id
            and can_view_public_contractor_profile(user, contractor)
        )
    if target_type == "message":
        result = await db_run(
            env,
            """
            SELECT messages.id, messages.is_hidden,
                   threads.client_id, threads.contractor_id
            FROM messages
            JOIN threads ON threads.id = messages.thread_id
            WHERE messages.id = ?
            LIMIT 1
            """,
            target_id,
        )
        message = first_row(result)
        return bool(
            message
            and not row_value(message, "is_hidden", 0)
            and can_view_thread(user, message)
        )
    return False


async def admin_target_exists(env, target_type: str, target_id: int) -> bool:
    result = await db_run(env, admin_target_query(target_type), target_id)
    return first_row(result) is not None


async def moderation_user_snapshot(env, target_id: int):
    return first_row(await db_run(env, """
        SELECT id, role, status, auth_provider, external_subject, created_at,
               (SELECT COALESCE(MAX(id), 0) FROM automation_events
                WHERE event_type = 'clerk-provider-restriction' AND target_type = 'user'
                  AND target_id = users.id) AS restriction_revision
        FROM users WHERE id = ? LIMIT 1
    """, target_id))


async def clerk_reactivation_failure(env, subject) -> tuple[int, str] | None:
    if not isinstance(subject, str) or not re.fullmatch(r"user_[A-Za-z0-9_-]{1,128}", subject):
        return 409, "This account does not have a valid linked sign-in."
    try:
        secret = str(getattr(env, "CLERK_SECRET_KEY", "") or "").strip()
        if not secret:
            raise ValueError("Clerk lookup is unavailable.")
        account = await fetch_clerk_user(subject, secret)
    except Exception:  # noqa: BLE001 - JS transport and provider errors must not be exposed.
        return 503, "Could not verify the linked sign-in. No changes were made."
    if (account.get("id") != subject or account.get("object") != "user"
            or account.get("banned") is not False or account.get("locked") is not False
            or any(account.get(flag, False) is not False for flag in CLERK_RESTRICTION_FLAGS)):
        return 409, "The linked sign-in is restricted or could not be confirmed. No changes were made."
    return None


async def update_moderated_user(env, target, state: str, admin_id: int) -> bool:
    result = await db_run(env, """
        UPDATE users SET status = ?
        WHERE id = ? AND role IN ('client', 'contractor') AND role = ? AND status = ?
          AND auth_provider = ? AND external_subject IS ? AND created_at = ?
          AND EXISTS (SELECT 1 FROM users AS actor WHERE actor.id = ? AND actor.role = 'admin'
                        AND actor.status = 'active')
          AND (? != 'active' OR ? = (SELECT COALESCE(MAX(id), 0) FROM automation_events
               WHERE event_type = 'clerk-provider-restriction' AND target_type = 'user' AND target_id = users.id))
    """, state, target["id"], target["role"], target["status"], target["auth_provider"],
        target["external_subject"], target["created_at"], admin_id, state, target["restriction_revision"])
    return d1_change_count(result) == 1


async def insert_moderation_action(
    env,
    admin_id: int,
    action_type: str,
    target_type: str,
    target_id: int,
    notes: str,
    created_at: str,
) -> None:
    await db_run(
        env,
        """
        INSERT INTO moderation_actions
            (admin_id, action_type, target_type, target_id, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        admin_id,
        action_type,
        target_type,
        target_id,
        notes,
        created_at,
    )


async def admin_dashboard_payload(env) -> dict:
    users = rows_from(
        await db_run(
            env,
            """
            SELECT id, email, role, display_name, company_name, status, created_at
            FROM users
            ORDER BY created_at DESC
            LIMIT 50
            """,
        )
    )
    jobs = rows_from(
        await db_run(
            env,
            """
            SELECT jobs.*, users.display_name AS client_name
            FROM jobs
            JOIN users ON users.id = jobs.client_id
            ORDER BY jobs.created_at DESC
            LIMIT 20
            """,
        )
    )
    lead_feedback = rows_from(
        await db_run(
            env,
            """
            SELECT job_lead_feedback.*, jobs.title AS job_title,
                   users.email AS contractor_email
            FROM job_lead_feedback
            JOIN jobs ON jobs.id = job_lead_feedback.job_id
            JOIN users ON users.id = job_lead_feedback.contractor_id
            ORDER BY job_lead_feedback.updated_at DESC
            LIMIT 20
            """,
        )
    )
    close_outcomes = rows_from(
        await db_run(
            env,
            """
            SELECT close_reason, COUNT(*) AS total
            FROM jobs
            WHERE status = 'closed' AND close_reason IS NOT NULL
            GROUP BY close_reason
            ORDER BY total DESC, close_reason
            """,
        )
    )
    lead_quality_outcomes = rows_from(
        await db_run(
            env,
            """
            SELECT reason_code, COUNT(*) AS total
            FROM job_lead_feedback
            GROUP BY reason_code
            ORDER BY total DESC, reason_code
            """,
        )
    )
    reports = rows_from(
        await db_run(
            env,
            """
            SELECT reports.*,
                   users.email AS reporter_email,
                   reported_jobs.title AS job_title,
                   reported_messages.thread_id AS message_thread_id,
                   reported_messages.body AS message_excerpt,
                   message_jobs.title AS message_job_title,
                   contractor_profiles.business_name AS profile_business_name
            FROM reports
            JOIN users ON users.id = reports.reporter_id
            LEFT JOIN jobs AS reported_jobs
                ON reports.target_type = 'job' AND reported_jobs.id = reports.target_id
            LEFT JOIN messages AS reported_messages
                ON reports.target_type = 'message' AND reported_messages.id = reports.target_id
            LEFT JOIN threads AS message_threads
                ON message_threads.id = reported_messages.thread_id
            LEFT JOIN jobs AS message_jobs
                ON message_jobs.id = message_threads.job_id
            LEFT JOIN contractor_profiles
                ON reports.target_type = 'profile' AND contractor_profiles.user_id = reports.target_id
            WHERE reports.status = 'open'
            ORDER BY reports.created_at DESC
            LIMIT 50
            """,
        )
    )
    messages = rows_from(
        await db_run(
            env,
            """
            SELECT messages.*, users.email AS sender_email, jobs.title AS job_title
            FROM messages
            JOIN users ON users.id = messages.sender_id
            JOIN threads ON threads.id = messages.thread_id
            JOIN jobs ON jobs.id = threads.job_id
            ORDER BY messages.created_at DESC
            LIMIT 20
            """,
        )
    )
    actions = rows_from(
        await db_run(
            env,
            """
            SELECT moderation_actions.*, users.email AS admin_email
            FROM moderation_actions
            LEFT JOIN users ON users.id = moderation_actions.admin_id
            ORDER BY moderation_actions.created_at DESC
            LIMIT 20
            """,
        )
    )
    automation_events = rows_from(
        await db_run(
            env,
            """
            SELECT id, event_type, target_type, target_id, status, created_at
            FROM automation_events
            ORDER BY created_at DESC
            LIMIT 20
            """,
        )
    )
    service_activations = rows_from(
        await db_run(
            env,
            """
            SELECT service_zone_activations.*,
                   service_types.name AS service_name,
                   service_zones.name AS zone_name,
                   (
                       SELECT COUNT(*)
                       FROM users
                       WHERE users.role = 'contractor'
                         AND users.status = 'active'
                         AND EXISTS (
                             SELECT 1 FROM contractor_service_capabilities
                             WHERE contractor_service_capabilities.contractor_id = users.id
                               AND contractor_service_capabilities.service_slug = service_zone_activations.service_slug
                         )
                         AND EXISTS (
                             SELECT 1 FROM contractor_service_zones
                             WHERE contractor_service_zones.contractor_id = users.id
                               AND contractor_service_zones.zone_slug = service_zone_activations.zone_slug
                         )
                   ) AS eligible_contractors
            FROM service_zone_activations
            JOIN service_types ON service_types.slug = service_zone_activations.service_slug
            JOIN service_zones ON service_zones.slug = service_zone_activations.zone_slug
            ORDER BY service_zones.sort_order, service_types.group_slug,
                     service_types.sort_order, service_types.name
            """,
        )
    )
    photos = rows_from(
        await db_run(
            env,
            """
            SELECT job_photos.*, jobs.title
            FROM job_photos
            JOIN jobs ON jobs.id = job_photos.job_id
            ORDER BY job_photos.created_at DESC
            LIMIT 20
            """,
        )
    )
    contractor_photos = rows_from(
        await db_run(
            env,
            """
            SELECT contractor_photos.*, contractor_profiles.business_name
            FROM contractor_photos
            JOIN contractor_profiles ON contractor_profiles.user_id = contractor_photos.contractor_id
            ORDER BY contractor_photos.created_at DESC
            LIMIT 20
            """,
        )
    )
    credential_rows = rows_from(
        await db_run(
            env,
            """
            SELECT contractor_credentials.*,
                   users.email AS contractor_email,
                   contractor_profiles.business_name
            FROM contractor_credentials
            JOIN users ON users.id = contractor_credentials.contractor_id
            JOIN contractor_profiles
              ON contractor_profiles.user_id = contractor_credentials.contractor_id
            ORDER BY
              CASE contractor_credentials.status
                WHEN 'self_reported' THEN 0
                WHEN 'pending' THEN 1
                ELSE 2
              END,
              contractor_credentials.updated_at DESC
            LIMIT 50
            """,
        )
    )
    credentials = [
        {
            **credential_response(item, include_private=True),
            "contractor_email": row_value(item, "contractor_email", "") or "",
            "business_name": row_value(item, "business_name", "") or "",
        }
        for item in credential_rows
    ]
    hidden_content = first_row(
        await db_run(
            env,
            """
            SELECT
                (SELECT COUNT(*) FROM jobs WHERE status = 'hidden') +
                (SELECT COUNT(*) FROM job_photos WHERE is_hidden = 1) +
                (SELECT COUNT(*) FROM contractor_photos WHERE is_hidden = 1) +
                (SELECT COUNT(*) FROM messages WHERE is_hidden = 1) +
                (SELECT COUNT(*) FROM match_reviews WHERE is_hidden = 1) AS total
            """,
        )
    )
    audit_actions = first_row(
        await db_run(
            env,
            "SELECT COUNT(*) AS total FROM moderation_actions",
        )
    )
    automation_event_count = first_row(
        await db_run(
            env,
            "SELECT COUNT(*) AS total FROM automation_events",
        )
    )
    marketplace_row = first_row(await db_run(env, MARKETPLACE_OUTCOMES_SQL))
    marketplace_metrics = {
        key: int(row_value(marketplace_row, key, 0) or 0)
        for key in (
            "published_projects",
            "total_bids",
            "projects_with_bids",
            "matched_projects",
            "approved_matches",
            "completion_signals",
            "verified_completions",
            "closed_projects",
            "workdoe_match_outcomes",
            "lead_quality_signals",
        )
    }
    marketplace_metrics["qualified_match_rate"] = percentage_rate(
        marketplace_metrics["matched_projects"],
        marketplace_metrics["published_projects"],
    )
    marketplace_metrics["verified_completion_rate"] = percentage_rate(
        marketplace_metrics["verified_completions"],
        marketplace_metrics["approved_matches"],
    )
    marketplace_metrics["workdoe_close_rate"] = percentage_rate(
        marketplace_metrics["workdoe_match_outcomes"],
        marketplace_metrics["closed_projects"],
    )
    pilot_project_rows = rows_from(
        await db_run(
            env,
            """
            SELECT jobs.id,
                   jobs.service_slug,
                   jobs.service_zone_slug,
                   jobs.category,
                   jobs.description,
                   jobs.project_setting,
                   jobs.desired_date,
                   jobs.status,
                   jobs.close_reason,
                   jobs.budget_min,
                   jobs.budget_max,
                   jobs.created_at,
                   COALESCE(service_types.name, jobs.category, 'Unclassified service')
                       AS service_name,
                   COALESCE(service_zones.name, jobs.service_zone_slug, 'Unclassified zone')
                       AS zone_name,
                   (
                       SELECT COUNT(*)
                       FROM job_scope_answers
                       WHERE job_scope_answers.job_id = jobs.id
                   ) AS scope_answer_count,
                   (
                       SELECT COUNT(*)
                       FROM job_photos
                       WHERE job_photos.job_id = jobs.id
                         AND job_photos.is_hidden = 0
                   ) AS photo_count,
                   COUNT(match_requests.id) AS bid_count,
                   MIN(match_requests.created_at) AS first_bid_at,
                   SUM(CASE WHEN match_requests.status = 'approved' THEN 1 ELSE 0 END)
                       AS matched_count,
                   SUM(CASE WHEN match_requests.status = 'approved'
                                 AND match_completions.verified_at IS NOT NULL THEN 1 ELSE 0 END)
                       AS verified_completion_count,
                   (
                       SELECT COUNT(*)
                       FROM reports
                       WHERE reports.target_type = 'job'
                         AND reports.target_id = jobs.id
                         AND reports.status = 'open'
                   ) AS open_report_count
            FROM jobs
            JOIN users AS project_owners ON project_owners.id = jobs.client_id
            LEFT JOIN service_types ON service_types.slug = jobs.service_slug
            LEFT JOIN service_zones ON service_zones.slug = jobs.service_zone_slug
            LEFT JOIN match_requests ON match_requests.job_id = jobs.id
              AND EXISTS (
                  SELECT 1 FROM users AS bidder
                  WHERE bidder.id = match_requests.contractor_id
                    AND lower(bidder.email) NOT LIKE '%@workdoe.local'
              )
            LEFT JOIN match_completions
              ON match_completions.match_request_id = match_requests.id
            WHERE jobs.status != 'hidden'
              AND lower(project_owners.email) NOT LIKE '%@workdoe.local'
              AND jobs.created_at >= ?
            GROUP BY jobs.id
            ORDER BY jobs.created_at DESC
            """,
            (datetime.now(timezone.utc) - timedelta(days=84)).isoformat(),
        )
    )
    pilot_metrics = pilot_cell_metrics(
        pilot_project_rows,
        [
            {
                "service_slug": row_value(activation, "service_slug", ""),
                "zone_slug": row_value(activation, "zone_slug", ""),
                "current_eligible_contractors": row_value(
                    activation, "eligible_contractors", 0
                ),
                "minimum_eligible_contractors": row_value(
                    activation, "minimum_eligible_contractors", 3
                ),
                "activation_status": row_value(activation, "status", "candidate"),
                "service_name": row_value(
                    activation, "service_name", "Unclassified service"
                ),
                "zone_name": row_value(
                    activation, "zone_name", "Unclassified zone"
                ),
            }
            for activation in service_activations
        ],
        as_of=datetime.now(timezone.utc).date().isoformat(),
    )
    repeat_work_row = first_row(await db_run(env, REPEAT_INVITATION_OUTCOMES_SQL))
    repeat_work_metrics = {
        key: int(row_value(repeat_work_row, key, 0) or 0)
        for key in (
            "invitations_created",
            "invitations_pending",
            "invitations_bid_sent",
            "invitations_declined",
            "invitations_withdrawn",
            "verified_repeat_projects",
        )
    }
    repeat_work_metrics["invitation_bid_rate"] = percentage_rate(
        repeat_work_metrics["invitations_bid_sent"],
        repeat_work_metrics["invitations_created"],
    )
    repeat_work_metrics["verified_repeat_rate"] = percentage_rate(
        repeat_work_metrics["verified_repeat_projects"],
        repeat_work_metrics["invitations_bid_sent"],
    )
    repeat_invitations = rows_from(
        await db_run(
            env,
            """
            SELECT repeat_provider_invitations.id,
                   repeat_provider_invitations.job_id,
                   repeat_provider_invitations.status,
                   repeat_provider_invitations.created_at,
                   repeat_provider_invitations.responded_at,
                   jobs.title AS project_title,
                   jobs.city,
                   jobs.state,
                   COALESCE(
                       NULLIF(contractor_profiles.business_name, ''),
                       NULLIF(users.company_name, ''),
                       users.display_name,
                       'Contractor'
                   ) AS contractor_name,
                   EXISTS (
                       SELECT 1
                       FROM match_requests
                       JOIN match_completions
                         ON match_completions.match_request_id = match_requests.id
                       WHERE match_requests.job_id = repeat_provider_invitations.job_id
                         AND match_requests.contractor_id = repeat_provider_invitations.contractor_id
                         AND match_requests.status = 'approved'
                         AND match_completions.verified_at IS NOT NULL
                   ) AS verified_complete
            FROM repeat_provider_invitations
            JOIN jobs ON jobs.id = repeat_provider_invitations.job_id
            JOIN users ON users.id = repeat_provider_invitations.contractor_id
            LEFT JOIN contractor_profiles
              ON contractor_profiles.user_id = repeat_provider_invitations.contractor_id
            ORDER BY repeat_provider_invitations.created_at DESC
            LIMIT 20
            """,
        )
    )
    lead_alert_row = first_row(
        await db_run(
            env,
            """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM contractor_lead_preferences
                    WHERE lead_alert_preference = 'email'
                      AND lead_alert_consent_at IS NOT NULL
                ) AS opted_in_contractors,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END)
                    AS pending_alerts,
                SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END)
                    AS queued_alerts,
                SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END)
                    AS sent_alerts,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END)
                    AS failed_alerts
            FROM contractor_lead_alert_deliveries
            """,
        )
    )
    lead_alert_metrics = {
        key: int(row_value(lead_alert_row, key, 0) or 0)
        for key in (
            "opted_in_contractors",
            "pending_alerts",
            "queued_alerts",
            "sent_alerts",
            "failed_alerts",
        )
    }
    recent_lead_alerts = rows_from(
        await db_run(
            env,
            """
            SELECT contractor_lead_alert_deliveries.id,
                   contractor_lead_alert_deliveries.job_id,
                   contractor_lead_alert_deliveries.status,
                   contractor_lead_alert_deliveries.created_at,
                   contractor_lead_alert_deliveries.queued_at,
                   contractor_lead_alert_deliveries.sent_at,
                   jobs.title AS project_title,
                   jobs.city,
                   jobs.state,
                   COALESCE(
                       NULLIF(contractor_profiles.business_name, ''),
                       NULLIF(users.company_name, ''),
                       users.display_name,
                       'Contractor'
                   ) AS contractor_name
            FROM contractor_lead_alert_deliveries
            JOIN jobs ON jobs.id = contractor_lead_alert_deliveries.job_id
            JOIN users ON users.id = contractor_lead_alert_deliveries.contractor_id
            LEFT JOIN contractor_profiles
              ON contractor_profiles.user_id = contractor_lead_alert_deliveries.contractor_id
            ORDER BY contractor_lead_alert_deliveries.created_at DESC
            LIMIT 20
            """,
        )
    )
    match_review_row = first_row(
        await db_run(
            env,
            """
            SELECT
                COUNT(*) AS total_reviews,
                SUM(CASE WHEN reviewer_role = 'client' THEN 1 ELSE 0 END)
                    AS client_reviews,
                SUM(CASE WHEN reviewer_role = 'contractor' THEN 1 ELSE 0 END)
                    AS contractor_reviews,
                SUM(CASE WHEN response != '' THEN 1 ELSE 0 END)
                    AS responses,
                SUM(CASE WHEN is_hidden = 1 THEN 1 ELSE 0 END)
                    AS hidden_reviews
            FROM match_reviews
            """,
        )
    )
    match_review_metrics = {
        key: int(row_value(match_review_row, key, 0) or 0)
        for key in (
            "total_reviews",
            "client_reviews",
            "contractor_reviews",
            "responses",
            "hidden_reviews",
        )
    }
    recent_match_review_rows = rows_from(
        await db_run(
            env,
            """
            SELECT match_reviews.*,
                   jobs.title AS project_title,
                   reviewer.email AS reviewer_email,
                   subject.email AS subject_email,
                   match_completions.verified_at
            FROM match_reviews
            JOIN match_requests ON match_requests.id = match_reviews.match_request_id
            JOIN jobs ON jobs.id = match_requests.job_id
            JOIN users AS reviewer ON reviewer.id = match_reviews.reviewer_id
            JOIN users AS subject ON subject.id = match_reviews.subject_id
            JOIN match_completions
              ON match_completions.match_request_id = match_reviews.match_request_id
            ORDER BY match_reviews.created_at DESC, match_reviews.id DESC
            LIMIT 20
            """,
        )
    )
    recent_match_reviews = [
        {
            **review_response(item, include_private=True),
            "project_title": row_value(item, "project_title", "") or "",
            "reviewer_email": row_value(item, "reviewer_email", "") or "",
            "subject_email": row_value(item, "subject_email", "") or "",
        }
        for item in recent_match_review_rows
    ]
    match_review_reports = rows_from(
        await db_run(
            env,
            """
            SELECT match_review_reports.*,
                   match_reviews.match_request_id,
                   match_reviews.reviewer_role,
                   jobs.title AS project_title,
                   users.email AS reporter_email
            FROM match_review_reports
            JOIN match_reviews ON match_reviews.id = match_review_reports.review_id
            JOIN match_requests ON match_requests.id = match_reviews.match_request_id
            JOIN jobs ON jobs.id = match_requests.job_id
            JOIN users ON users.id = match_review_reports.reporter_id
            WHERE match_review_reports.status = 'open'
            ORDER BY match_review_reports.created_at DESC
            LIMIT 50
            """,
        )
    )
    match_review_metrics["open_reports"] = len(match_review_reports)
    return {
        "ok": True,
        "users": users,
        "jobs": jobs,
        "lead_feedback": lead_feedback,
        "close_outcomes": close_outcomes,
        "lead_quality_outcomes": lead_quality_outcomes,
        "reports": reports,
        "messages": messages,
        "actions": actions,
        "automation_events": automation_events,
        "service_activations": service_activations,
        "photos": photos,
        "contractor_photos": contractor_photos,
        "credentials": credentials,
        "marketplace_metrics": marketplace_metrics,
        "pilot_metrics": pilot_metrics,
        "repeat_work_metrics": repeat_work_metrics,
        "repeat_invitations": repeat_invitations,
        "lead_alert_metrics": lead_alert_metrics,
        "recent_lead_alerts": recent_lead_alerts,
        "match_review_metrics": match_review_metrics,
        "recent_match_reviews": recent_match_reviews,
        "match_review_reports": match_review_reports,
        "stats": {
            "open_reports": len(reports) + len(match_review_reports),
            "suspended_users": sum(1 for user in users if row_value(user, "status") == "suspended"),
            "hidden_content": row_value(hidden_content, "total", 0) or 0,
            "audit_actions": row_value(audit_actions, "total", 0) or 0,
            "automation_events": row_value(automation_event_count, "total", 0) or 0,
        },
    }


async def client_profile_for_user(env, user_id: int):
    result = await db_run(
        env,
        """
        SELECT *
        FROM client_profiles
        WHERE user_id = ?
        LIMIT 1
        """,
        user_id,
    )
    return first_row(result)


async def ensure_client_profile(env, user, created_at: str):
    user_id = row_value(user, "id")
    existing = await client_profile_for_user(env, user_id)
    if existing:
        return existing
    organization_name = (
        row_value(user, "company_name", "")
        or row_value(user, "display_name", "")
        or "Workdoe consumer"
    )
    await db_run(
        env,
        """
        INSERT OR IGNORE INTO client_profiles
            (user_id, organization_name, phone, account_type,
             notification_preference, email_reminder_consent_at,
             profile_note, updated_at)
        VALUES (?, ?, '', 'household', 'workdoe', NULL, '', ?)
        """,
        user_id,
        organization_name,
        created_at,
    )
    return await client_profile_for_user(env, user_id)


async def upsert_client_profile(
    env,
    user_id: int,
    profile: dict,
    updated_at: str,
) -> None:
    await db_run(
        env,
        """
        INSERT INTO client_profiles
            (user_id, organization_name, phone, account_type,
             notification_preference, email_reminder_consent_at,
             profile_note, updated_at)
        VALUES (?, ?, '', ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            organization_name = excluded.organization_name,
            account_type = excluded.account_type,
            notification_preference = excluded.notification_preference,
            email_reminder_consent_at = excluded.email_reminder_consent_at,
            profile_note = excluded.profile_note,
            updated_at = excluded.updated_at
        """,
        user_id,
        profile["organization_name"],
        profile["account_type"],
        profile["notification_preference"],
        updated_at if profile["notification_preference"] == "email" else None,
        profile["profile_note"],
        updated_at,
    )


async def client_saved_locations_for_user(env, client_id: int) -> list[dict]:
    result = await db_run(
        env,
        """
        SELECT id, label, city, state, zip_code, created_at, updated_at
        FROM client_saved_locations
        WHERE client_id = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT ?
        """,
        client_id,
        SAVED_LOCATION_LIMIT,
    )
    return rows_from(result)


async def client_saved_location_for_user(env, client_id: int, location_id: int):
    result = await db_run(
        env,
        """
        SELECT id, label, city, state, zip_code
        FROM client_saved_locations
        WHERE id = ? AND client_id = ?
        LIMIT 1
        """,
        location_id,
        client_id,
    )
    return first_row(result)


async def client_project_templates_for_user(env, client_id: int) -> list[dict]:
    result = await db_run(
        env,
        """
        SELECT * FROM client_project_templates
        WHERE client_id = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT ?
        """,
        client_id,
        PROJECT_TEMPLATE_LIMIT,
    )
    return rows_from(result)


async def client_project_template_for_user(env, client_id: int, template_id: int):
    result = await db_run(
        env,
        """
        SELECT * FROM client_project_templates
        WHERE id = ? AND client_id = ?
        LIMIT 1
        """,
        template_id,
        client_id,
    )
    return first_row(result)


async def client_template_source_jobs_for_user(env, client_id: int) -> list[dict]:
    result = await db_run(
        env,
        """
        SELECT id, title, category, status, updated_at
        FROM jobs
        WHERE client_id = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT 100
        """,
        client_id,
    )
    return rows_from(result)


async def client_job_for_template(env, client_id: int, job_id: int):
    result = await db_run(
        env,
        "SELECT id FROM jobs WHERE id = ? AND client_id = ? LIMIT 1",
        job_id,
        client_id,
    )
    return first_row(result)


async def contractor_proposal_templates_for_user(
    env, contractor_id: int
) -> list[dict]:
    result = await db_run(
        env,
        """
        SELECT * FROM contractor_proposal_templates
        WHERE contractor_id = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT ?
        """,
        contractor_id,
        PROPOSAL_TEMPLATE_LIMIT,
    )
    return rows_from(result)


async def contractor_proposal_template_for_user(
    env, contractor_id: int, template_id: int
):
    result = await db_run(
        env,
        """
        SELECT * FROM contractor_proposal_templates
        WHERE id = ? AND contractor_id = ?
        LIMIT 1
        """,
        template_id,
        contractor_id,
    )
    return first_row(result)


async def contractor_bid_for_proposal_template(
    env, contractor_id: int, match_request_id: int
):
    result = await db_run(
        env,
        """
        SELECT id, job_id, scope_note, timeline, experience, questions, availability
        FROM match_requests
        WHERE id = ? AND contractor_id = ?
        LIMIT 1
        """,
        match_request_id,
        contractor_id,
    )
    return first_row(result)


async def contractor_profile_for_user(env, user_id: int):
    result = await db_run(
        env,
        """
        SELECT *
        FROM contractor_profiles
        WHERE user_id = ?
        LIMIT 1
        """,
        user_id,
    )
    return first_row(result)


async def contractor_preferences_for_user(env, contractor_id: int):
    result = await db_run(
        env,
        """
        SELECT *
        FROM contractor_lead_preferences
        WHERE contractor_id = ?
        LIMIT 1
        """,
        contractor_id,
    )
    return first_row(result)


async def upsert_contractor_availability(
    env,
    contractor_id: int,
    values: dict,
    updated_at: str,
) -> None:
    await db_run(
        env,
        """
        INSERT INTO contractor_lead_preferences
            (contractor_id, availability_status, available_from, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(contractor_id) DO UPDATE SET
            availability_status = excluded.availability_status,
            available_from = excluded.available_from,
            updated_at = excluded.updated_at
        """,
        contractor_id,
        values["availability_status"],
        values["available_from"] or None,
        updated_at,
    )


async def upsert_contractor_saved_lead_view(
    env,
    contractor_id: int,
    values: dict,
    updated_at: str,
) -> None:
    alert_consent_at = (
        updated_at if values["lead_alert_preference"] == "email" else None
    )
    await db_run(
        env,
        """
        INSERT INTO contractor_lead_preferences
            (contractor_id, saved_query, saved_category,
             saved_service_group_slug, saved_service_slug, saved_sort,
             saved_at, lead_alert_preference, lead_alert_consent_at,
             updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(contractor_id) DO UPDATE SET
            saved_query = excluded.saved_query,
            saved_category = excluded.saved_category,
            saved_service_group_slug = excluded.saved_service_group_slug,
            saved_service_slug = excluded.saved_service_slug,
            saved_sort = excluded.saved_sort,
            saved_at = excluded.saved_at,
            lead_alert_preference = excluded.lead_alert_preference,
            lead_alert_consent_at = CASE
                WHEN excluded.lead_alert_preference = 'email'
                THEN COALESCE(
                    contractor_lead_preferences.lead_alert_consent_at,
                    excluded.lead_alert_consent_at
                )
                ELSE NULL
            END,
            updated_at = excluded.updated_at
        """,
        contractor_id,
        values["saved_query"],
        values["saved_category"],
        values["saved_service_group_slug"],
        values["saved_service_slug"],
        values["saved_sort"],
        updated_at,
        values["lead_alert_preference"],
        alert_consent_at,
        updated_at,
    )


async def contractor_credentials_for_user(env, contractor_id: int) -> list[dict]:
    result = await db_run(
        env,
        """
        SELECT * FROM contractor_credentials
        WHERE contractor_id = ?
        ORDER BY updated_at DESC, id DESC
        """,
        contractor_id,
    )
    return rows_from(result)


async def contractor_credential_for_owner(env, credential_id: int, contractor_id: int):
    result = await db_run(
        env,
        """
        SELECT * FROM contractor_credentials
        WHERE id = ? AND contractor_id = ?
        LIMIT 1
        """,
        credential_id,
        contractor_id,
    )
    return first_row(result)


async def contractor_credential_duplicate(env, contractor_id: int, claim: dict):
    result = await db_run(
        env,
        """
        SELECT id FROM contractor_credentials
        WHERE contractor_id = ?
          AND credential_type = ?
          AND jurisdiction = ?
          AND claimed_identifier = ?
        LIMIT 1
        """,
        contractor_id,
        claim["credential_type"],
        claim["jurisdiction"],
        claim["claimed_identifier"],
    )
    return first_row(result)


async def contractor_market_fit_for_user(env, user_id: int, profile=None) -> dict:
    service_result = await db_run(
        env,
        """
        SELECT service_slug
        FROM contractor_service_capabilities
        WHERE contractor_id = ?
        ORDER BY service_slug
        """,
        user_id,
    )
    zone_result = await db_run(
        env,
        """
        SELECT zone_slug
        FROM contractor_service_zones
        WHERE contractor_id = ?
        ORDER BY zone_slug
        """,
        user_id,
    )
    services = normalize_service_slugs(
        [row_value(row, "service_slug", "") for row in rows_from(service_result)]
    )
    zones = normalize_zone_slugs(
        [row_value(row, "zone_slug", "") for row in rows_from(zone_result)]
    )
    if profile is None:
        profile = await contractor_profile_for_user(env, user_id)
    if profile and not services:
        services = infer_service_slugs_from_trades(row_value(profile, "trades", ""))
    if profile and not zones:
        zones = infer_zone_slugs_from_area(row_value(profile, "service_area", ""))
    return {"service_slugs": services, "service_zone_slugs": zones}


async def replace_contractor_market_fit(
    env,
    user_id: int,
    service_slugs,
    service_zone_slugs,
    created_at: str,
) -> None:
    services = normalize_service_slugs(service_slugs)
    zones = normalize_zone_slugs(service_zone_slugs)
    await db_run(
        env,
        "DELETE FROM contractor_service_capabilities WHERE contractor_id = ?",
        user_id,
    )
    await db_run(
        env,
        "DELETE FROM contractor_service_zones WHERE contractor_id = ?",
        user_id,
    )
    for service_slug in services:
        await db_run(
            env,
            """
            INSERT INTO contractor_service_capabilities
                (contractor_id, service_slug, created_at)
            VALUES (?, ?, ?)
            """,
            user_id,
            service_slug,
            created_at,
        )
    for zone_slug in zones:
        await db_run(
            env,
            """
            INSERT INTO contractor_service_zones
                (contractor_id, zone_slug, created_at)
            VALUES (?, ?, ?)
            """,
            user_id,
            zone_slug,
            created_at,
        )


async def public_contractor_for_profile(env, contractor_id: int):
    result = await db_run(
        env,
        """
        SELECT users.id, users.status,
               contractor_profiles.business_name,
               contractor_profiles.trades,
               contractor_profiles.service_area,
               contractor_profiles.intro,
               contractor_profiles.years_in_business,
               contractor_profiles.website,
               contractor_profiles.updated_at,
               contractor_lead_preferences.availability_status,
               contractor_lead_preferences.available_from,
               (
                   SELECT COUNT(*)
                   FROM match_requests
                   JOIN match_completions
                     ON match_completions.match_request_id = match_requests.id
                   WHERE match_requests.contractor_id = users.id
                     AND match_completions.verified_at IS NOT NULL
               ) AS verified_completions
        FROM users
        JOIN contractor_profiles ON contractor_profiles.user_id = users.id
        LEFT JOIN contractor_lead_preferences
          ON contractor_lead_preferences.contractor_id = users.id
        WHERE users.id = ?
          AND users.role = 'contractor'
        LIMIT 1
        """,
        contractor_id,
    )
    return first_row(result)


async def visible_contractor_profile_photos(env, contractor_id: int) -> list[dict]:
    result = await db_run(
        env,
        """
        SELECT id, original_filename, content_type, created_at
        FROM contractor_photos
        WHERE contractor_id = ?
          AND is_hidden = 0
        ORDER BY created_at DESC
        LIMIT 24
        """,
        contractor_id,
    )
    return rows_from(result)


async def contractor_has_client_bid_relationship(env, contractor_id: int, viewer) -> bool:
    if not viewer or row_value(viewer, "role") != "client":
        return False
    result = await db_run(
        env,
        """
        SELECT 1
        FROM match_requests
        JOIN jobs ON jobs.id = match_requests.job_id
        WHERE match_requests.contractor_id = ?
          AND jobs.client_id = ?
        LIMIT 1
        """,
        contractor_id,
        row_value(viewer, "id"),
    )
    return first_row(result) is not None


async def client_contractor_choice_for_profile(
    env,
    contractor_id: int,
    job_id: int,
    viewer,
):
    if (
        not viewer
        or row_value(viewer, "role") != "client"
        or row_value(viewer, "status") != "active"
        or job_id < 1
    ):
        return None
    result = await db_run(
        env,
        """
        SELECT jobs.id AS job_id,
               jobs.title AS job_title,
               jobs.client_id,
               match_requests.contractor_id,
               match_requests.id AS request_id,
               match_requests.price_range,
               match_requests.timeline,
               match_requests.availability,
               match_requests.status,
               threads.id AS thread_id
        FROM jobs
        JOIN match_requests
          ON match_requests.job_id = jobs.id
        LEFT JOIN threads
          ON threads.match_request_id = match_requests.id
        WHERE jobs.id = ?
          AND jobs.client_id = ?
          AND match_requests.contractor_id = ?
        LIMIT 1
        """,
        job_id,
        row_value(viewer, "id"),
        contractor_id,
    )
    return first_row(result)


async def client_jobs_for_user(env, client_id: int) -> list[dict]:
    result = await db_run(
        env,
        """
        SELECT
            jobs.id,
            jobs.title,
            jobs.category,
            jobs.service_slug,
            jobs.project_setting,
            jobs.license_preference,
            jobs.city,
            jobs.state,
            jobs.zip_code,
            jobs.description,
            jobs.desired_date,
            jobs.budget_min,
            jobs.budget_max,
            jobs.status,
            jobs.close_reason,
            jobs.created_at,
            jobs.updated_at,
            jobs.bid_limit,
            jobs.bidding_closes_at,
            (SELECT COUNT(*) FROM job_photos
             WHERE job_photos.job_id = jobs.id AND job_photos.is_hidden = 0)
                AS photo_count,
            (SELECT COUNT(*) FROM job_scope_answers
             WHERE job_scope_answers.job_id = jobs.id) AS scope_answer_count,
            COUNT(match_requests.id) AS request_count,
            SUM(CASE WHEN match_requests.status = 'pending' THEN 1 ELSE 0 END) AS pending_count,
            SUM(CASE WHEN match_requests.status = 'approved' THEN 1 ELSE 0 END) AS approved_count,
            SUM(CASE WHEN match_requests.status = 'rejected' THEN 1 ELSE 0 END) AS rejected_count,
            SUM(CASE WHEN match_completions.verified_at IS NOT NULL THEN 1 ELSE 0 END)
                AS verified_completion_count,
            SUM(CASE WHEN match_completions.client_confirmed_at IS NOT NULL
                          OR match_completions.contractor_confirmed_at IS NOT NULL
                     THEN 1 ELSE 0 END) AS completion_signal_count
            ,(
                SELECT verified_request.id
                FROM match_requests AS verified_request
                JOIN match_completions AS verified_completion
                  ON verified_completion.match_request_id = verified_request.id
                WHERE verified_request.job_id = jobs.id
                  AND verified_request.status = 'approved'
                  AND verified_completion.verified_at IS NOT NULL
                ORDER BY verified_completion.verified_at DESC, verified_request.id DESC
                LIMIT 1
            ) AS repeat_match_request_id
            ,(
                SELECT COALESCE(
                    NULLIF(verified_profile.business_name, ''),
                    NULLIF(verified_user.company_name, ''),
                    verified_user.display_name,
                    'Contractor'
                )
                FROM match_requests AS verified_request
                JOIN match_completions AS verified_completion
                  ON verified_completion.match_request_id = verified_request.id
                JOIN users AS verified_user
                  ON verified_user.id = verified_request.contractor_id
                LEFT JOIN contractor_profiles AS verified_profile
                  ON verified_profile.user_id = verified_user.id
                WHERE verified_request.job_id = jobs.id
                  AND verified_request.status = 'approved'
                  AND verified_completion.verified_at IS NOT NULL
                  AND verified_user.status = 'active'
                ORDER BY verified_completion.verified_at DESC, verified_request.id DESC
                LIMIT 1
            ) AS repeat_contractor_name
        FROM jobs
        LEFT JOIN match_requests ON match_requests.job_id = jobs.id
        LEFT JOIN match_completions
          ON match_completions.match_request_id = match_requests.id
        WHERE jobs.client_id = ?
        GROUP BY jobs.id
        ORDER BY jobs.created_at DESC, jobs.id DESC
        LIMIT ?
        """,
        client_id,
        CLIENT_JOB_LIMIT,
    )
    return rows_from(result)


async def repeat_invitation_source_record(
    env,
    client_id: int,
    source_job_id: int,
    source_match_request_id: int,
):
    result = await db_run(
        env,
        """
        SELECT jobs.id AS source_job_id,
               jobs.client_id,
               jobs.status AS source_job_status,
               jobs.close_reason,
               jobs.service_slug,
               jobs.category,
               match_requests.id AS source_match_request_id,
               match_requests.contractor_id,
               match_requests.status AS match_status,
               match_completions.verified_at,
               users.status AS contractor_status,
               COALESCE(
                   NULLIF(contractor_profiles.business_name, ''),
                   NULLIF(users.company_name, ''),
                   users.display_name,
                   'Contractor'
               ) AS contractor_name
        FROM match_requests
        JOIN jobs ON jobs.id = match_requests.job_id
        JOIN match_completions
          ON match_completions.match_request_id = match_requests.id
        JOIN users ON users.id = match_requests.contractor_id
        LEFT JOIN contractor_profiles
          ON contractor_profiles.user_id = users.id
        WHERE jobs.id = ?
          AND jobs.client_id = ?
          AND match_requests.id = ?
        LIMIT 1
        """,
        source_job_id,
        client_id,
        source_match_request_id,
    )
    return first_row(result)


async def repeat_invitation_for_job(env, job_id: int, contractor_id: int = 0):
    sql = """
        SELECT repeat_provider_invitations.*,
               jobs.title AS project_title,
               jobs.category,
               jobs.city,
               jobs.state,
               jobs.desired_date,
               jobs.status AS job_status,
               COALESCE(
                   NULLIF(contractor_profiles.business_name, ''),
                   NULLIF(users.company_name, ''),
                   users.display_name,
                   'Contractor'
               ) AS contractor_name
        FROM repeat_provider_invitations
        JOIN jobs ON jobs.id = repeat_provider_invitations.job_id
        JOIN users ON users.id = repeat_provider_invitations.contractor_id
        LEFT JOIN contractor_profiles
          ON contractor_profiles.user_id = users.id
        WHERE repeat_provider_invitations.job_id = ?
    """
    bindings = [job_id]
    if contractor_id:
        sql += " AND repeat_provider_invitations.contractor_id = ?"
        bindings.append(contractor_id)
    sql += " LIMIT 1"
    return first_row(await db_run(env, sql, *bindings))


async def repeat_invitation_by_id(env, invitation_id: int):
    return first_row(
        await db_run(
            env,
            "SELECT * FROM repeat_provider_invitations WHERE id = ? LIMIT 1",
            invitation_id,
        )
    )


async def contractor_repeat_invitations(env, contractor_id: int) -> list[dict]:
    result = await db_run(
        env,
        """
        SELECT repeat_provider_invitations.*,
               jobs.title AS project_title,
               jobs.category,
               jobs.city,
               jobs.state,
               jobs.desired_date,
               jobs.status AS job_status,
               jobs.bid_limit,
               jobs.bidding_closes_at,
               COUNT(match_requests.id) AS request_count
        FROM repeat_provider_invitations
        JOIN jobs ON jobs.id = repeat_provider_invitations.job_id
        LEFT JOIN match_requests ON match_requests.job_id = jobs.id
        WHERE repeat_provider_invitations.contractor_id = ?
          AND repeat_provider_invitations.status = 'pending'
          AND jobs.status = 'open'
          AND datetime(jobs.bidding_closes_at) > datetime(?)
          AND NOT EXISTS (
              SELECT 1
              FROM match_requests AS approved_request
              WHERE approved_request.job_id = jobs.id
                AND approved_request.status = 'approved'
          )
          AND NOT EXISTS (
              SELECT 1
              FROM match_requests AS own_request
              WHERE own_request.job_id = jobs.id
                AND own_request.contractor_id = repeat_provider_invitations.contractor_id
          )
        GROUP BY repeat_provider_invitations.id
        ORDER BY repeat_provider_invitations.created_at DESC
        """,
        contractor_id,
        utc_now(),
    )
    invitations = []
    for row in rows_from(result):
        item = repeat_invitation_response(row)
        item["bid_window"] = bid_window(
            {
                "status": row_value(row, "job_status"),
                "bid_limit": row_value(row, "bid_limit"),
                "bidding_closes_at": row_value(row, "bidding_closes_at"),
                "request_count": row_value(row, "request_count", 0),
            }
        )
        invitations.append(item)
    return invitations


async def client_job_for_requests(env, job_id: int):
    result = await db_run(
        env,
        """
        SELECT jobs.id, jobs.client_id, jobs.title, jobs.status,
               jobs.bid_limit, jobs.bidding_closes_at,
               (SELECT COUNT(*) FROM match_requests WHERE job_id = jobs.id)
                   AS request_count
        FROM jobs
        WHERE id = ?
        LIMIT 1
        """,
        job_id,
    )
    return first_row(result)


async def client_requests_for_job(env, job_id: int) -> list[dict]:
    result = await db_run(
        env,
        """
        SELECT
            match_requests.id,
            match_requests.job_id,
            match_requests.contractor_id,
            match_requests.scope_note,
            match_requests.price_range,
            match_requests.timeline,
            match_requests.experience,
            match_requests.questions,
            match_requests.availability,
            match_requests.status,
            match_requests.created_at,
            match_requests.updated_at,
            users.display_name,
            users.company_name,
            contractor_profiles.business_name,
            contractor_profiles.trades,
            contractor_profiles.insurance_status,
            contractor_profiles.years_in_business,
            (
                SELECT contractor_photos.id
                FROM contractor_photos
                WHERE contractor_photos.contractor_id = users.id
                  AND contractor_photos.is_hidden = 0
                ORDER BY contractor_photos.created_at DESC,
                         contractor_photos.id DESC
                LIMIT 1
            ) AS profile_photo_id,
            (
                SELECT COUNT(*)
                FROM contractor_credentials
                WHERE contractor_credentials.contractor_id = users.id
                  AND contractor_credentials.status = 'verified'
                  AND (
                      contractor_credentials.expires_at IS NULL
                      OR contractor_credentials.expires_at = ''
                      OR date(contractor_credentials.expires_at) >= date('now')
                  )
            ) AS source_checked_credential_count,
            (
                SELECT COUNT(*)
                FROM contractor_credentials
                WHERE contractor_credentials.contractor_id = users.id
                  AND contractor_credentials.credential_type = 'trade_license'
                  AND contractor_credentials.status = 'verified'
                  AND (
                      contractor_credentials.expires_at IS NULL
                      OR contractor_credentials.expires_at = ''
                      OR date(contractor_credentials.expires_at) >= date('now')
                  )
            ) AS source_checked_license_count,
            (
                SELECT COUNT(DISTINCT completed_request.id)
                FROM match_requests AS completed_request
                JOIN match_completions AS completed_match
                  ON completed_match.match_request_id = completed_request.id
                WHERE completed_request.contractor_id = users.id
                  AND completed_request.status = 'approved'
                  AND completed_match.verified_at IS NOT NULL
            ) AS verified_work_count,
            threads.id AS thread_id,
            match_completions.client_confirmed_at,
            match_completions.contractor_confirmed_at,
            match_completions.verified_at
        FROM match_requests
        JOIN users ON users.id = match_requests.contractor_id
        LEFT JOIN contractor_profiles ON contractor_profiles.user_id = users.id
        LEFT JOIN threads ON threads.match_request_id = match_requests.id
        LEFT JOIN match_completions
          ON match_completions.match_request_id = match_requests.id
        WHERE match_requests.job_id = ?
        ORDER BY
            CASE match_requests.status
                WHEN 'pending' THEN 0
                WHEN 'approved' THEN 1
                WHEN 'rejected' THEN 2
                ELSE 3
            END,
            match_requests.created_at DESC,
            match_requests.id DESC
        LIMIT ?
        """,
        job_id,
        CLIENT_REQUEST_LIMIT,
    )
    return rows_from(result)


async def read_public_project_page(
    env,
    filters: dict[str, str],
    viewport: dict[str, float] | None,
    *,
    limit: int,
    source: str,
    cursor_offset: int = 0,
) -> tuple[list, str, bool]:
    query, bindings = build_public_open_jobs_query(
        filters,
        viewport,
        order_clause=public_job_order_clause(filters["sort"]),
        limit=limit + PUBLIC_PROJECT_PRIVACY_LOOKAHEAD,
        cursor_offset=cursor_offset,
        service_activation_clause=live_service_activation_sql() if enforce_service_activation(env) else "",
    )
    result = await db_run(env, query, *bindings)
    visible, cursor_advance = public_project_page(rows_from(result), limit)
    telemetry = public_query_telemetry(
        result, returned_rows=min(len(visible), limit), filters=filters,
        viewport_applied=viewport is not None, cursor_offset=cursor_offset,
    )
    print(json.dumps({**telemetry, "source": source}, sort_keys=True))
    truncated = len(visible) > limit
    rows = guest_project_rows(
        visible, filters, limit=limit, viewport=viewport, include_demo=cursor_offset == 0,
    )
    return rows, next_public_cursor(cursor_offset, cursor_advance, has_more=truncated), truncated


async def contractor_leads_for_user(
    env,
    contractor_id: int,
    filters: dict[str, str],
    limit: int,
) -> list[dict]:
    sql = [
        """
        SELECT
            jobs.id,
            jobs.title,
            jobs.category,
            jobs.service_slug,
            jobs.service_group_slug,
            jobs.service_slug,
            jobs.project_setting,
            jobs.city,
            jobs.state,
            jobs.zip_code,
            jobs.description,
            jobs.desired_date,
            jobs.budget_min,
            jobs.budget_max,
            jobs.approx_lat,
            jobs.approx_lng,
            jobs.created_at,
            jobs.bid_limit,
            jobs.bidding_closes_at,
            COUNT(job_photos.id) AS photo_count,
            (SELECT COUNT(*) FROM job_scope_answers
             WHERE job_scope_answers.job_id = jobs.id) AS scope_answer_count,
            (SELECT COUNT(*) FROM match_requests AS all_requests
             WHERE all_requests.job_id = jobs.id) AS request_count,
            MAX(match_requests.status) AS request_status
        FROM jobs
        JOIN users AS clients
          ON clients.id = jobs.client_id
         AND clients.status = 'active'
        LEFT JOIN job_photos
          ON job_photos.job_id = jobs.id
         AND job_photos.is_hidden = 0
        LEFT JOIN match_requests
          ON match_requests.job_id = jobs.id
         AND match_requests.contractor_id = ?
        WHERE jobs.status = 'open'
          AND NOT EXISTS (
              SELECT 1
              FROM match_requests AS approved_request
              WHERE approved_request.job_id = jobs.id
                AND approved_request.status = 'approved'
          )
        """,
    ]
    bindings: list[str | int] = [contractor_id]
    if enforce_service_activation(env):
        sql.append(live_service_activation_sql())
    if filters["category"]:
        sql.append("AND jobs.category = ?")
        bindings.append(filters["category"])
    if filters.get("service"):
        sql.append("AND jobs.service_slug = ?")
        bindings.append(filters["service"])
    if filters["family"]:
        sql.append("AND jobs.service_group_slug = ?")
        bindings.append(filters["family"])
    search, search_bindings = literal_project_search(filters["q"])
    if search:
        sql.append(search)
        bindings.extend(search_bindings)
    sql.append(f"GROUP BY jobs.id ORDER BY {contractor_lead_order_clause(filters['sort'])} LIMIT ?")
    bindings.append(limit)
    result = await db_run(env, "\n".join(sql), *bindings)
    return rows_from(result)


async def contractor_bids_for_user(env, contractor_id: int) -> list[dict]:
    result = await db_run(
        env,
        """
        SELECT
            match_requests.id,
            match_requests.job_id,
            match_requests.scope_note,
            match_requests.price_range,
            match_requests.timeline,
            match_requests.availability,
            match_requests.status,
            match_requests.created_at,
            match_requests.updated_at,
            jobs.title,
            jobs.category,
            jobs.city,
            jobs.state,
            jobs.description,
            jobs.desired_date,
            jobs.status AS job_status,
            jobs.close_reason,
            threads.id AS thread_id,
            match_completions.client_confirmed_at,
            match_completions.contractor_confirmed_at,
            match_completions.verified_at
        FROM match_requests
        JOIN jobs ON jobs.id = match_requests.job_id
        LEFT JOIN threads ON threads.match_request_id = match_requests.id
        LEFT JOIN match_completions
          ON match_completions.match_request_id = match_requests.id
        WHERE match_requests.contractor_id = ?
        ORDER BY match_requests.created_at DESC, match_requests.id DESC
        LIMIT ?
        """,
        contractor_id,
        CONTRACTOR_BID_LIMIT,
    )
    return rows_from(result)


async def ensure_contractor_profile(env, user, created_at: str):
    user_id = row_value(user, "id")
    existing = await contractor_profile_for_user(env, user_id)
    if existing:
        return existing
    business_name = row_value(user, "company_name") or row_value(user, "display_name") or ""
    await db_run(
        env,
        """
        INSERT INTO contractor_profiles
            (user_id, business_name, trades, service_area, intro,
             insurance_status, license_number, years_in_business,
             website, phone, updated_at)
        VALUES (?, ?, '', 'DMV area', '', '', '', NULL, '', '', ?)
        """,
        user_id,
        business_name,
        created_at,
    )
    return await contractor_profile_for_user(env, user_id)


async def upsert_contractor_profile(env, user_id: int, profile: dict, updated_at: str) -> None:
    await db_run(
        env,
        """
        INSERT INTO contractor_profiles
            (user_id, business_name, trades, service_area, intro,
             insurance_status, license_number, years_in_business,
             website, phone, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            business_name = excluded.business_name,
            trades = excluded.trades,
            service_area = excluded.service_area,
            intro = excluded.intro,
            insurance_status = excluded.insurance_status,
            license_number = excluded.license_number,
            years_in_business = excluded.years_in_business,
            website = excluded.website,
            phone = excluded.phone,
            updated_at = excluded.updated_at
        """,
        user_id,
        profile["business_name"],
        profile["trades"],
        profile["service_area"],
        profile["intro"],
        profile["insurance_status"],
        profile["license_number"],
        profile["years_in_business_value"],
        profile["website"],
        "",
        updated_at,
    )


def job_draft_form(row) -> dict:
    return {
        "title": str(row_value(row, "title", "") or ""),
        "category": str(row_value(row, "category", "") or ""),
        "service_group_slug": str(row_value(row, "service_group_slug", "") or ""),
        "service_slug": str(row_value(row, "service_slug", "") or ""),
        "project_setting": str(row_value(row, "project_setting", "") or ""),
        "license_preference": (
            "1" if int(row_value(row, "license_preference", 0) or 0) == 1 else ""
        ),
        "desired_date": str(row_value(row, "desired_date", "") or ""),
        "city": str(row_value(row, "city", "") or ""),
        "state": str(row_value(row, "state", "DC") or "DC"),
        "zip_code": str(row_value(row, "zip_code", "") or ""),
        "budget_min": (
            str(row_value(row, "budget_min"))
            if row_value(row, "budget_min") is not None
            else ""
        ),
        "budget_max": (
            str(row_value(row, "budget_max"))
            if row_value(row, "budget_max") is not None
            else ""
        ),
        "description": str(row_value(row, "description", "") or ""),
        "scope_answers": dict(row_value(row, "scope_answers", {}) or {}),
    }


async def job_draft_for_request(env, request):
    token = job_draft_token_from_cookie(request.headers.get("Cookie"))
    if not token:
        return None
    try:
        token_hash = job_draft_token_hash(token, getattr(env, "WORKDOE_SECRET_KEY", ""))
        result = await db_run(
            env,
            """
            SELECT draft.id, draft.title, draft.category, draft.service_group_slug, draft.service_slug,
                   draft.project_setting, draft.license_preference, draft.desired_date, draft.city,
                   draft.state, draft.zip_code, draft.budget_min, draft.budget_max, draft.description,
                   (SELECT json_group_object(question_key, answer_code)
                    FROM job_draft_scope_answers WHERE draft_id = draft.id) AS scope_answers_json
            FROM job_drafts AS draft
            WHERE draft.token_hash = ? AND draft.consumed_at IS NULL AND draft.expires_at >= ?
            LIMIT 1
            """,
            token_hash, utc_now(),
        )
    except Exception as exc:
        raise JobDraftReadError from exc
    if row_value(result, "success") is not True or row_value(result, "results") is None:
        raise JobDraftReadError
    rows = rows_from(result)
    if not isinstance(rows, list) or len(rows) > 1:
        raise JobDraftReadError
    if not rows:
        return None
    row = rows[0]
    try:
        draft_id = int(row_value(row, "id", 0) or 0)
        scope_answers = json.loads(row_value(row, "scope_answers_json"))
        form = job_draft_form(row)
    except (TypeError, ValueError, RecursionError) as exc:
        raise JobDraftReadError from exc
    if draft_id <= 0 or not isinstance(scope_answers, dict) or not all(
        isinstance(answer, str) for answer in scope_answers.values()
    ):
        raise JobDraftReadError
    form["id"] = draft_id
    form["scope_answers"] = scope_answers
    return form


async def save_job_draft_record(env, request, form: dict) -> str:
    secret = getattr(env, "WORKDOE_SECRET_KEY", "")
    old_token = job_draft_token_from_cookie(request.headers.get("Cookie"))
    now = datetime.now(timezone.utc)
    created_at = now.isoformat(timespec="seconds")
    expires_at = (now + timedelta(seconds=JOB_DRAFT_TTL_SECONDS)).isoformat(
        timespec="seconds"
    )
    token = generate_job_draft_token()
    token_hash = job_draft_token_hash(token, secret)
    commands = []
    if old_token:
        commands.append((
            "DELETE FROM job_drafts WHERE token_hash = ?",
            (job_draft_token_hash(old_token, secret),),
        ))
    commands.append((
        "DELETE FROM job_drafts WHERE consumed_at IS NOT NULL OR expires_at < ?",
        (created_at,),
    ))
    insert_index = len(commands)
    commands.append((
        """
        INSERT INTO job_drafts
            (token_hash, title, category, service_group_slug, service_slug,
             project_setting, license_preference, city, state, zip_code, description,
             desired_date, budget_min, budget_max, expires_at, consumed_at,
             created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
        """,
        (
            token_hash, form["title"], form["category"], form["service_group_slug"],
            form["service_slug"], form["project_setting"], int(form["license_preference"] == "1"),
            form["city"], form["state"], form["zip_code"], form["description"],
            form["desired_date"], budget_database_value(form["budget_min"]),
            budget_database_value(form["budget_max"]), expires_at, created_at, created_at,
        ),
    ))
    # Resolve the new parent inside the same D1 transaction as its scope answers.
    commands.extend((
        """
        INSERT INTO job_draft_scope_answers
            (draft_id, schema_version, question_key, answer_code, created_at, updated_at)
        VALUES ((SELECT id FROM job_drafts WHERE token_hash = ?), ?, ?, ?, ?, ?)
        """,
        (token_hash, SCOPE_SCHEMA_VERSION, answer["question_key"], answer["answer_code"], created_at, created_at),
    ) for answer in scope_answer_projection(form["service_slug"], form.get("scope_answers", {})))
    results = await db_batch(env, commands)
    if (
        any(row_value(result, "success") is not True for result in results)
        or d1_change_count(results[insert_index]) != 1
    ):
        raise ValueError("Unsuccessful D1 project draft batch.")
    return token


async def publish_job(
    env,
    actor_id: int,
    request_state: dict,
    job: dict,
    service_zone_slug: str,
    repeat_source: dict | None,
    draft_hash: str,
) -> int | None:
    timestamp = utc_now()
    receipt_key = (actor_id, request_state["action"], request_state["key_hash"])
    policy = service_policy(job["service_slug"])
    if policy["acknowledgement_required"] and job["service_policy_acknowledgement"] != policy["version"]:
        raise ValueError("The service policy acknowledgement is not current.")
    answers = {
        answer["question_key"]: answer["answer_code"]
        for answer in scope_answer_projection(job["service_slug"], job.get("scope_answers", {}))
    }
    # Bind the new row to this request before other inserts can change last_insert_rowid().
    commands = [
        (
            """
            INSERT INTO jobs
                (client_id, title, category, service_group_slug, service_slug,
                 service_zone_slug, project_setting, license_preference,
                 city, state, zip_code, description, desired_date, budget_min, budget_max,
                 status, approx_lat, approx_lng, bid_limit, bidding_closes_at, created_at, updated_at)
            SELECT actor.id, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   'open', ?, ?, ?, ?, ?, ?
            FROM users AS actor
            JOIN idempotency_requests AS receipt ON receipt.actor_id = actor.id
            WHERE actor.id = ? AND actor.status = 'active' AND actor.role IN ('client', 'admin')
              AND receipt.action = ? AND receipt.key_hash = ? AND receipt.resource_type = 'job'
              AND receipt.status = 'processing' AND receipt.resource_id IS NULL AND receipt.expires_at >= ?
            """,
            (
                job["title"], job["category"], job["service_group_slug"], job["service_slug"],
                service_zone_slug, job["project_setting"], int(job["license_preference"] == "1"),
                job["city"], job["state"], job["zip_code"], job["description"], job["desired_date"],
                budget_database_value(job["budget_min"]), budget_database_value(job["budget_max"]),
                job["approx_lat"], job["approx_lng"], DEFAULT_BID_LIMIT,
                default_bidding_closes_at(timestamp), timestamp, timestamp, *receipt_key, timestamp,
            ),
        ),
        (
            """
            UPDATE idempotency_requests SET resource_id = last_insert_rowid()
            WHERE actor_id = ? AND action = ? AND key_hash = ? AND resource_type = 'job'
              AND status = 'processing' AND resource_id IS NULL AND changes() = 1
            """,
            receipt_key,
        ),
    ]
    if policy["acknowledgement_required"]:
        commands.append((
            """
            INSERT INTO service_policy_acknowledgements
                (user_id, actor_role, context, service_slug, policy_version, job_id, acknowledged_at)
            SELECT actor_id, 'client', 'project-post', ?, ?, resource_id, ?
            FROM idempotency_requests
            WHERE actor_id = ? AND action = ? AND key_hash = ? AND resource_type = 'job'
              AND status = 'processing' AND resource_id IS NOT NULL
            """,
            (job["service_slug"], policy["version"], timestamp, *receipt_key),
        ))
    if answers:
        commands.append((
            """
            INSERT INTO job_scope_answers
                (job_id, schema_version, question_key, answer_code, created_at, updated_at)
            SELECT receipt.resource_id, ?, answer.key, answer.value, ?, ?
            FROM idempotency_requests AS receipt CROSS JOIN json_each(?) AS answer
            WHERE receipt.actor_id = ? AND receipt.action = ? AND receipt.key_hash = ?
              AND receipt.resource_type = 'job' AND receipt.status = 'processing'
              AND receipt.resource_id IS NOT NULL
            """,
            (SCOPE_SCHEMA_VERSION, timestamp, timestamp, json.dumps(answers), *receipt_key),
        ))
    if repeat_source:
        source_job_id = repeat_source["source_job_id"]
        source_match_id = repeat_source["source_match_request_id"]
        contractor_id = repeat_source["contractor_id"]
        commands.extend([
            (
                """
                INSERT INTO repeat_provider_invitations
                    (job_id, source_job_id, source_match_request_id, client_id,
                     contractor_id, service_slug, status, created_at, updated_at)
                SELECT resource_id, ?, ?, actor_id, ?, ?, 'pending', ?, ?
                FROM idempotency_requests
                WHERE actor_id = ? AND action = ? AND key_hash = ? AND resource_type = 'job'
                  AND status = 'processing' AND resource_id IS NOT NULL
                """,
                (source_job_id, source_match_id, contractor_id, repeat_source["service_slug"],
                 timestamp, timestamp, *receipt_key),
            ),
            (
                """
                INSERT INTO automation_events (event_type, target_type, target_id, payload_json, status, created_at)
                SELECT 'repeat-provider-invited', 'job', resource_id,
                       json_object('source_job_id', ?, 'source_match_request_id', ?, 'contractor_id', ?),
                       'processed', ?
                FROM idempotency_requests
                WHERE actor_id = ? AND action = ? AND key_hash = ? AND resource_type = 'job'
                  AND status = 'processing' AND resource_id IS NOT NULL
                """,
                (source_job_id, source_match_id, contractor_id, timestamp, *receipt_key),
            ),
        ])
    if draft_hash:
        commands.append((
            """
            UPDATE job_drafts SET consumed_at = ?, updated_at = ?
            WHERE token_hash = ? AND consumed_at IS NULL AND EXISTS (
                SELECT 1 FROM idempotency_requests
                WHERE actor_id = ? AND action = ? AND key_hash = ? AND resource_type = 'job'
                  AND status = 'processing' AND resource_id IS NOT NULL
            )
            """,
            (timestamp, timestamp, draft_hash, *receipt_key),
        ))
    commands.extend([
        (
            """
            INSERT INTO automation_events (event_type, target_type, target_id, payload_json, status, created_at)
            SELECT 'job-created', 'job', resource_id,
                   json_object('client_id', actor_id, 'category', ?), 'processed', ?
            FROM idempotency_requests
            WHERE actor_id = ? AND action = ? AND key_hash = ? AND resource_type = 'job'
              AND status = 'processing' AND resource_id IS NOT NULL
            """,
            (job["category"], timestamp, *receipt_key),
        ),
        (
            """
            UPDATE idempotency_requests SET status = 'completed', completed_at = ?
            WHERE actor_id = ? AND action = ? AND key_hash = ? AND resource_type = 'job'
              AND status = 'processing' AND resource_id IS NOT NULL
            """,
            (timestamp, *receipt_key),
        ),
    ])
    results = await db_batch(env, commands)
    if d1_change_count(results[0]) == 0:
        return None
    job_id = last_insert_id(results[0])
    if not job_id or d1_change_count(results[-1]) != 1:
        raise ValueError("Unexpected D1 project publication batch result.")
    return job_id


async def save_match_request(env, job, contractor_id: int, bid: dict, timestamp: str) -> int | None:
    job_id = row_value(job, "id")
    service_slug = row_value(job, "service_slug")
    zone_slug = row_value(job, "service_zone_slug")
    policy = service_policy(service_slug)
    acknowledgement_required = policy["acknowledgement_required"]
    if acknowledgement_required and bid["service_policy_acknowledgement"] != policy["version"]:
        raise ValueError("The service policy acknowledgement is not current.")
    # The activation clause is fixed SQL; all record values are bound separately.
    activation_gate = live_service_activation_sql() if enforce_service_activation(env) else ""
    bid_key = (job_id, contractor_id)
    # Each dependent statement only writes if the prior statement changed one row.
    commands = [
        (
            f"""
            INSERT INTO match_requests
                (job_id, contractor_id, scope_note, price_range, timeline,
                 experience, questions, availability, status, created_at, updated_at)
            SELECT jobs.id, contractor.id, ?, ?, ?, ?, ?, ?, 'pending', ?, ?
            FROM jobs
            JOIN users AS clients ON clients.id = jobs.client_id AND clients.status = 'active'
            JOIN users AS contractor ON contractor.id = ?
              AND contractor.role = 'contractor' AND contractor.status = 'active'
            WHERE jobs.id = ? AND jobs.status = 'open'
              AND jobs.service_slug IS ? AND jobs.service_zone_slug IS ?
              AND datetime(jobs.bidding_closes_at) > datetime(?)
              AND NOT EXISTS (
                  SELECT 1 FROM match_requests AS approved_request
                  WHERE approved_request.job_id = jobs.id AND approved_request.status = 'approved'
              )
              AND (SELECT COUNT(*) FROM match_requests WHERE match_requests.job_id = jobs.id) < jobs.bid_limit
              {activation_gate}
            ON CONFLICT(job_id, contractor_id) DO NOTHING
            """,  # nosec B608
            (
                bid["scope_note"], bid["price_range"], bid["timeline"], bid["experience"],
                bid["questions"], bid["availability"], timestamp, timestamp,
                contractor_id, job_id, service_slug, zone_slug, timestamp,
            ),
        ),
    ]
    if acknowledgement_required:
        commands.append((
            """
            INSERT INTO service_policy_acknowledgements
                (user_id, actor_role, context, service_slug, policy_version, job_id, match_request_id, acknowledged_at)
            SELECT contractor_id, 'contractor', 'mini-bid', ?, ?, job_id, id, ?
            FROM match_requests
            WHERE job_id = ? AND contractor_id = ? AND changes() = 1
            """,
            (service_slug, policy["version"], timestamp, *bid_key),
        ))
    commands.extend([
        (
            """
            INSERT INTO automation_events (event_type, target_type, target_id, payload_json, status, created_at)
            SELECT 'match-request-created', 'match_request', id,
                   json_object('job_id', job_id, 'contractor_id', contractor_id, 'status', 'pending'),
                   'processed', ?
            FROM match_requests
            WHERE job_id = ? AND contractor_id = ? AND changes() = 1
            """,
            (timestamp, *bid_key),
        ),
        (
            """
            UPDATE repeat_provider_invitations
            SET status = 'bid_sent', responded_at = ?, updated_at = ?
            WHERE job_id = ? AND contractor_id = ? AND status = 'pending' AND changes() = 1
            """,
            (timestamp, timestamp, *bid_key),
        ),
        (
            """
            INSERT INTO automation_events (event_type, target_type, target_id, payload_json, status, created_at)
            SELECT 'repeat-provider-invitation-bid-sent', 'job', job_id,
                   json_object('contractor_id', contractor_id, 'match_request_id', id),
                   'processed', ?
            FROM match_requests
            WHERE job_id = ? AND contractor_id = ? AND changes() = 1
            """,
            (timestamp, *bid_key),
        ),
    ])
    results = await db_batch(env, commands)
    if d1_change_count(results[0]) == 0:
        return None
    request_id = last_insert_id(results[0])
    if (
        not request_id or any(d1_change_count(result) != 1 for result in results[:-2])
        or d1_change_count(results[-2]) != d1_change_count(results[-1])
    ):
        raise ValueError("Unexpected D1 bid save batch result.")
    return request_id


async def job_for_detail(env, job_id: int, *, contractor_id: int | None = None):
    result = await db_run(
        env,
        """
        SELECT jobs.*, users.display_name AS client_name, users.company_name AS client_company,
               users.status AS client_status,
               (SELECT COUNT(*) FROM match_requests WHERE job_id = jobs.id)
                   AS request_count,
               EXISTS (
                   SELECT 1
                   FROM match_requests AS approved_request
                   WHERE approved_request.job_id = jobs.id
                     AND approved_request.status = 'approved'
               ) AS has_approved_match,
               EXISTS (
                   SELECT 1 FROM match_requests AS own_request
                   WHERE own_request.job_id = jobs.id AND own_request.contractor_id = ?
               ) AS has_viewer_request
        FROM jobs
        JOIN users ON users.id = jobs.client_id
        WHERE jobs.id = ?
        LIMIT 1
        """,
        contractor_id, job_id,
    )
    return first_row(result)


async def detail_photos_for_viewer(env, user, job, existing_request) -> list[dict]:
    owner_view = viewer_kind(user, job) in {"owner", "admin"}
    if not owner_view and not contractor_can_view_project(
        row_value(job, "status"), row_value(job, "client_status"),
        has_approved_match=bool(row_value(job, "has_approved_match")),
        participates=row_value(existing_request, "status") == "approved",
    ):
        return []
    return await job_photos_for_detail(env, row_value(job, "id"), include_hidden=owner_view)


async def job_photos_for_detail(env, job_id: int, include_hidden: bool = False) -> list[dict]:
    query = (
        """
        SELECT id, is_hidden
        FROM job_photos
        WHERE job_id = ?
        ORDER BY created_at
        LIMIT 24
        """
        if include_hidden
        else """
        SELECT id, is_hidden
        FROM job_photos
        WHERE job_id = ? AND is_hidden = 0
        ORDER BY created_at
        LIMIT 24
        """
    )
    result = await db_run(
        env,
        query,
        job_id,
    )
    return rows_from(result)


async def contractor_request_for_job(env, job_id: int, contractor_id: int):
    result = await db_run(
        env,
        """
        SELECT match_requests.*, threads.id AS thread_id
        FROM match_requests
        LEFT JOIN threads ON threads.match_request_id = match_requests.id
        WHERE match_requests.job_id = ?
          AND match_requests.contractor_id = ?
        LIMIT 1
        """,
        job_id,
        contractor_id,
    )
    return first_row(result)


async def contractor_lead_feedback_for_job(env, job_id: int, contractor_id: int):
    result = await db_run(
        env,
        """
        SELECT reason_code, note, updated_at
        FROM job_lead_feedback
        WHERE job_id = ? AND contractor_id = ?
        LIMIT 1
        """,
        job_id,
        contractor_id,
    )
    return first_row(result)


async def match_request_for_decision(env, request_id: int):
    result = await db_run(
        env,
        """
        SELECT
            match_requests.id,
            match_requests.job_id,
            match_requests.contractor_id,
            match_requests.status,
            jobs.client_id
        FROM match_requests
        JOIN jobs ON jobs.id = match_requests.job_id
        WHERE match_requests.id = ?
        LIMIT 1
        """,
        request_id,
    )
    return first_row(result)


async def reject_pending_match(env, match, timestamp: str, *, actor_id: int) -> bool:
    request_id = row_value(match, "id")
    job_id = row_value(match, "job_id")
    client_id = row_value(match, "client_id")
    contractor_id = row_value(match, "contractor_id")
    payload = json.dumps({
        "action": "reject", "job_id": job_id, "client_id": client_id, "contractor_id": contractor_id,
        "thread_id": None, "closed_offer_count": 0,
    }, sort_keys=True)
    updated, audit = await db_batch(env, (
        (
            """
            UPDATE match_requests
            SET status = 'rejected', updated_at = ?
            WHERE id = ? AND status = 'pending'
              AND job_id = ? AND contractor_id = ?
              AND EXISTS (
                  SELECT 1 FROM jobs
                  JOIN users AS actor ON actor.id = ? AND actor.status = 'active'
                  WHERE jobs.id = match_requests.job_id
                    AND jobs.client_id = ?
                    AND (actor.role = 'admin' OR
                         (actor.role = 'client' AND actor.id = jobs.client_id))
              )
            """,
            (timestamp, request_id, job_id, contractor_id, actor_id, client_id),
        ),
        (
            """
            INSERT INTO automation_events (event_type, target_type, target_id, payload_json, status, created_at)
            SELECT 'match-request-rejected', 'match_request', ?, ?, 'processed', ?
            WHERE changes() = 1
            """,
            (request_id, payload, timestamp),
        ),
    ))
    write_count = d1_change_count(updated)
    if write_count not in (0, 1) or d1_change_count(audit) != write_count:
        raise ValueError("Unexpected D1 rejection batch result.")
    return write_count == 1


async def approve_pending_match(env, match, timestamp: str, *, actor_id: int) -> int | None:
    request_id = row_value(match, "id")
    job_id = row_value(match, "job_id")
    client_id = row_value(match, "client_id")
    contractor_id = row_value(match, "contractor_id")
    # In this batch each later write requires exactly one row from the preceding
    # write. A stale approval changes nothing; a SQL error rolls back the batch.
    results = await db_batch(
        env,
        (
            (
                """
                UPDATE match_requests
                SET status = 'approved', updated_at = ?
                WHERE id = ? AND status = 'pending'
                  AND job_id = ? AND contractor_id = ?
                  AND EXISTS (
                      SELECT 1 FROM jobs
                      JOIN users AS clients ON clients.id = jobs.client_id
                        AND clients.role = 'client' AND clients.status = 'active'
                      JOIN users AS contractors ON contractors.id = match_requests.contractor_id
                        AND contractors.role = 'contractor' AND contractors.status = 'active'
                      JOIN users AS actor ON actor.id = ? AND actor.status = 'active'
                      WHERE jobs.id = match_requests.job_id
                        AND jobs.client_id = ?
                        AND jobs.status IN ('open', 'closed')
                        AND (actor.role = 'admin' OR
                             (actor.role = 'client' AND actor.id = jobs.client_id))
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM match_requests AS approved_request
                      WHERE approved_request.job_id = match_requests.job_id
                        AND approved_request.status = 'approved'
                  )
                """,
                (timestamp, request_id, job_id, contractor_id, actor_id, client_id),
            ),
            (
                """
                INSERT INTO threads
                    (job_id, match_request_id, client_id, contractor_id, created_at)
                SELECT ?, ?, ?, ?, ? WHERE changes() = 1
                """,
                (job_id, request_id, client_id, contractor_id, timestamp),
            ),
            (
                """
                INSERT INTO messages (thread_id, sender_id, body, is_hidden, created_at)
                SELECT id, contractor_id, ?, 0, ?
                FROM threads WHERE match_request_id = ? AND changes() = 1
                """,
                (APPROVAL_THREAD_MESSAGE, timestamp, request_id),
            ),
            (
                """
                INSERT INTO automation_events
                    (event_type, target_type, target_id, payload_json, status, created_at)
                SELECT 'match-request-approved', 'match_request', threads.match_request_id,
                    json_object(
                        'action', 'approve', 'job_id', threads.job_id,
                        'client_id', threads.client_id, 'contractor_id', threads.contractor_id,
                        'thread_id', threads.id, 'closed_offer_count', (
                            SELECT COUNT(*) FROM match_requests AS offers
                            WHERE offers.job_id = threads.job_id
                              AND offers.id != threads.match_request_id
                              AND offers.status = 'pending'
                        )
                    ), 'processed', ?
                FROM threads WHERE match_request_id = ? AND changes() = 1
                """,
                (timestamp, request_id),
            ),
            (
                """
                UPDATE match_requests
                SET status = 'rejected', updated_at = ?
                WHERE job_id = ? AND id != ? AND status = 'pending' AND changes() = 1
                """,
                (timestamp, job_id, request_id),
            ),
        ),
    )
    if d1_change_count(results[0]) == 0:
        return None
    thread_id = last_insert_id(results[1])
    if not thread_id or any(d1_change_count(results[index]) != 1 for index in range(4)):
        raise ValueError("Unexpected D1 approval batch result.")
    return thread_id


async def match_for_completion(env, request_id: int):
    result = await db_run(
        env,
        """
        SELECT
            match_requests.id AS match_request_id,
            match_requests.contractor_id,
            match_requests.status AS match_status,
            jobs.id AS job_id,
            jobs.client_id,
            jobs.status AS job_status,
            jobs.close_reason,
            match_completions.client_confirmed_at,
            match_completions.contractor_confirmed_at,
            match_completions.verified_at
        FROM match_requests
        JOIN jobs ON jobs.id = match_requests.job_id
        LEFT JOIN match_completions
          ON match_completions.match_request_id = match_requests.id
        WHERE match_requests.id = ?
        LIMIT 1
        """,
        request_id,
    )
    return first_row(result)


async def match_for_review(env, request_id: int):
    result = await db_run(
        env,
        """
        SELECT match_requests.id AS match_request_id,
               match_requests.contractor_id,
               match_requests.status AS match_status,
               jobs.id AS job_id,
               jobs.client_id,
               jobs.status AS job_status,
               jobs.close_reason,
               match_completions.verified_at
        FROM match_requests
        JOIN jobs ON jobs.id = match_requests.job_id
        LEFT JOIN match_completions
          ON match_completions.match_request_id = match_requests.id
        WHERE match_requests.id = ?
        LIMIT 1
        """,
        request_id,
    )
    return first_row(result)


async def match_review_for_participant(env, request_id: int, reviewer_id: int):
    result = await db_run(
        env,
        """
        SELECT match_reviews.*, match_completions.verified_at
        FROM match_reviews
        JOIN match_completions
          ON match_completions.match_request_id = match_reviews.match_request_id
        WHERE match_reviews.match_request_id = ?
          AND match_reviews.reviewer_id = ?
        LIMIT 1
        """,
        request_id,
        reviewer_id,
    )
    return first_row(result)


async def match_review_by_id(env, review_id: int):
    result = await db_run(
        env,
        """
        SELECT match_reviews.*,
               match_requests.job_id,
               match_requests.contractor_id,
               jobs.client_id,
               match_completions.verified_at
        FROM match_reviews
        JOIN match_requests ON match_requests.id = match_reviews.match_request_id
        JOIN jobs ON jobs.id = match_requests.job_id
        JOIN match_completions
          ON match_completions.match_request_id = match_reviews.match_request_id
        WHERE match_reviews.id = ?
        LIMIT 1
        """,
        review_id,
    )
    return first_row(result)


async def match_reviews_for_request_ids(
    env, request_ids: list[int]
) -> dict[int, dict[str, dict]]:
    if not request_ids:
        return {}
    placeholders = ",".join("?" for _ in request_ids)
    # The interpolated text contains only generated placeholders for integer IDs.
    result = await db_run(
        env,
        f"""
        SELECT match_reviews.*, match_completions.verified_at
        FROM match_reviews
        JOIN match_completions
          ON match_completions.match_request_id = match_reviews.match_request_id
        WHERE match_reviews.match_request_id IN ({placeholders})
        ORDER BY match_reviews.created_at, match_reviews.id
        """,  # nosec B608
        *request_ids,
    )
    grouped: dict[int, dict[str, dict]] = {}
    for row in rows_from(result):
        item = review_response(row, include_private=True)
        grouped.setdefault(item["match_request_id"], {})[
            item["reviewer_role"]
        ] = item
    return grouped


async def visible_contractor_match_reviews(env, contractor_id: int) -> list[dict]:
    result = await db_run(
        env,
        """
        SELECT match_reviews.*,
               match_completions.verified_at,
               jobs.service_slug,
               jobs.category
        FROM match_reviews
        JOIN match_requests ON match_requests.id = match_reviews.match_request_id
        JOIN match_completions
          ON match_completions.match_request_id = match_requests.id
        JOIN jobs ON jobs.id = match_requests.job_id
        WHERE match_reviews.subject_id = ?
          AND match_reviews.reviewer_role = 'client'
          AND match_reviews.is_hidden = 0
          AND match_completions.verified_at IS NOT NULL
        ORDER BY match_reviews.created_at DESC, match_reviews.id DESC
        LIMIT 20
        """,
        contractor_id,
    )
    reviews = []
    for row in rows_from(result):
        item = review_response(row, include_private=True)
        item["service_name"] = service_label(
            row_value(row, "service_slug", ""), row_value(row, "category", "")
        )
        reviews.append(item)
    return reviews


def review_return_path(role: str, job_id) -> str:
    if role == "client" and int(job_id or 0) > 0:
        return f"/client/jobs/{int(job_id)}#completed-feedback"
    return "/contractor/dashboard#completed-work"


async def existing_thread_id_for_match(env, request_id: int) -> int | None:
    result = await db_run(
        env,
        """
        SELECT id
        FROM threads
        WHERE match_request_id = ?
        LIMIT 1
        """,
        request_id,
    )
    row = first_row(result)
    if not row:
        return None
    try:
        return int(row_value(row, "id"))
    except (TypeError, ValueError):
        return None


async def ensure_thread_for_match(env, match, created_at: str, *, actor_id: int) -> int | None:
    request_id = row_value(match, "id")
    thread, starter = await db_batch(env, (
        (
            """
            INSERT INTO threads (job_id, match_request_id, client_id, contractor_id, created_at)
            SELECT jobs.id, match_requests.id, jobs.client_id, match_requests.contractor_id, ?
            FROM match_requests
            JOIN jobs ON jobs.id = match_requests.job_id AND jobs.status IN ('open', 'closed')
            JOIN users AS clients ON clients.id = jobs.client_id
              AND clients.role = 'client' AND clients.status = 'active'
            JOIN users AS contractors ON contractors.id = match_requests.contractor_id
              AND contractors.role = 'contractor' AND contractors.status = 'active'
            JOIN users AS actor ON actor.id = ? AND actor.status = 'active'
            WHERE match_requests.id = ? AND match_requests.status = 'approved'
              AND jobs.id = ? AND jobs.client_id = ? AND match_requests.contractor_id = ?
              AND (actor.role = 'admin' OR (actor.role = 'client' AND actor.id = jobs.client_id))
            ON CONFLICT(match_request_id) DO NOTHING
            """,
            (
                created_at, actor_id, request_id, row_value(match, "job_id"),
                row_value(match, "client_id"), row_value(match, "contractor_id"),
            ),
        ),
        (
            """
            INSERT INTO messages (thread_id, sender_id, body, is_hidden, created_at)
            SELECT id, contractor_id, ?, 0, ?
            FROM threads WHERE match_request_id = ? AND changes() = 1
            """,
            (APPROVAL_THREAD_MESSAGE, created_at, request_id),
        ),
    ))
    thread_count = d1_change_count(thread)
    if thread_count == 0 and d1_change_count(starter) == 0:
        return await existing_thread_id_for_match(env, request_id)
    thread_id = last_insert_id(thread)
    if not thread_id or thread_count != 1 or d1_change_count(starter) != 1:
        raise ValueError("Unexpected D1 thread repair batch result.")
    return thread_id


async def message_threads_for_user(env, user_id: int) -> list[dict]:
    result = await db_run(
        env,
        """
        SELECT threads.*, jobs.title, jobs.category, jobs.city, jobs.state,
               client.display_name AS client_name,
               contractor.display_name AS contractor_name,
               last_visible.body AS last_message,
               last_visible.created_at AS last_message_at,
               last_visible.id AS last_message_id,
               last_visible.sender_id AS last_sender_id,
               (
                   SELECT COUNT(*) FROM messages
                   WHERE messages.thread_id = threads.id AND messages.is_hidden = 0
               ) AS message_count,
               (
                   SELECT COUNT(*) FROM messages
                   WHERE messages.thread_id = threads.id
                     AND messages.is_hidden = 0
                     AND messages.sender_id != ?
                     AND messages.id > COALESCE(
                         (
                             SELECT thread_reads.last_read_message_id
                             FROM thread_reads
                             WHERE thread_reads.thread_id = threads.id
                               AND thread_reads.user_id = ?
                         ),
                         0
                     )
               ) AS unread_count
        FROM threads
        JOIN jobs ON jobs.id = threads.job_id
        JOIN users AS client ON client.id = threads.client_id
        JOIN users AS contractor ON contractor.id = threads.contractor_id
        LEFT JOIN messages AS last_visible
          ON last_visible.id = (
              SELECT messages.id FROM messages
              WHERE messages.thread_id = threads.id
                AND messages.is_hidden = 0
              ORDER BY messages.id DESC
              LIMIT 1
          )
        WHERE threads.client_id = ? OR threads.contractor_id = ?
        ORDER BY COALESCE(last_visible.created_at, threads.created_at) DESC,
                 COALESCE(last_visible.id, 0) DESC
        LIMIT 50
        """,
        user_id,
        user_id,
        user_id,
        user_id,
    )
    return rows_from(result)


async def unread_message_count_for_user(env, user_id: int, role: str) -> int:
    queries = {
        "client": """
            SELECT COUNT(*) AS unread_count
            FROM threads
            JOIN messages ON messages.thread_id = threads.id
            LEFT JOIN thread_reads
              ON thread_reads.thread_id = threads.id
             AND thread_reads.user_id = ?
            WHERE threads.client_id = ?
              AND messages.is_hidden = 0
              AND messages.sender_id != ?
              AND messages.id > COALESCE(thread_reads.last_read_message_id, 0)
        """,
        "contractor": """
            SELECT COUNT(*) AS unread_count
            FROM threads
            JOIN messages ON messages.thread_id = threads.id
            LEFT JOIN thread_reads
              ON thread_reads.thread_id = threads.id
             AND thread_reads.user_id = ?
            WHERE threads.contractor_id = ?
              AND messages.is_hidden = 0
              AND messages.sender_id != ?
              AND messages.id > COALESCE(thread_reads.last_read_message_id, 0)
        """,
    }
    query = queries.get(role)
    if not query:
        return 0
    result = await db_run(
        env,
        query,
        user_id,
        user_id,
        user_id,
    )
    return positive_int(row_value(first_row(result), "unread_count", 0))


def user_with_unread_message_count(user, unread_count: int) -> dict:
    public_fields = (
        "id",
        "email",
        "role",
        "display_name",
        "company_name",
        "status",
        "auth_provider",
        "external_subject",
        "email_verified",
        "created_at",
    )
    presentation_user = {field: row_value(user, field) for field in public_fields}
    presentation_user["unread_message_count"] = max(0, int(unread_count or 0))
    return presentation_user


async def save_thread_message(env, actor_id: int, thread_id: int, request_state: dict, body: str) -> int | None:
    timestamp = utc_now()
    receipt_key = (actor_id, request_state["action"], request_state["key_hash"])
    # Each dependent write follows a successful statement in the same D1 batch.
    results = await db_batch(env, [
        (
            """
            INSERT INTO messages (thread_id, sender_id, body, is_hidden, created_at)
            SELECT threads.id, sender.id, ?, 0, ?
            FROM threads
            JOIN users AS sender ON sender.id = ? AND sender.status = 'active'
              AND ((sender.role = 'client' AND sender.id = threads.client_id)
                OR (sender.role = 'contractor' AND sender.id = threads.contractor_id))
            JOIN match_requests ON match_requests.id = threads.match_request_id
              AND match_requests.status = 'approved'
              AND match_requests.job_id = threads.job_id
              AND match_requests.contractor_id = threads.contractor_id
            JOIN jobs ON jobs.id = threads.job_id AND jobs.client_id = threads.client_id
            JOIN idempotency_requests AS receipt ON receipt.actor_id = sender.id
              AND receipt.action = ? AND receipt.key_hash = ? AND receipt.resource_type = 'message'
              AND receipt.status = 'processing' AND receipt.resource_id IS NULL AND receipt.expires_at >= ?
            WHERE threads.id = ?
            """,
            (body, timestamp, *receipt_key, timestamp, thread_id),
        ),
        (
            """
            UPDATE idempotency_requests
            SET resource_id = last_insert_rowid(), status = 'completed', completed_at = ?
            WHERE actor_id = ? AND action = ? AND key_hash = ? AND resource_type = 'message'
              AND status = 'processing' AND resource_id IS NULL AND changes() = 1
            """,
            (timestamp, *receipt_key),
        ),
        (
            """
            INSERT INTO thread_reads (thread_id, user_id, last_read_message_id, last_read_at)
            SELECT ?, actor_id, resource_id, ? FROM idempotency_requests
            WHERE actor_id = ? AND action = ? AND key_hash = ? AND resource_type = 'message'
              AND status = 'completed' AND resource_id IS NOT NULL AND changes() = 1
            ON CONFLICT(thread_id, user_id) DO UPDATE SET
                last_read_message_id = MAX(thread_reads.last_read_message_id, excluded.last_read_message_id),
                last_read_at = CASE
                    WHEN excluded.last_read_message_id >= thread_reads.last_read_message_id
                    THEN excluded.last_read_at ELSE thread_reads.last_read_at END
            """,
            (thread_id, timestamp, *receipt_key),
        ),
        (
            """
            INSERT INTO automation_events (event_type, target_type, target_id, payload_json, status, created_at)
            SELECT 'message-created', 'thread', ?, json_object('message_id', resource_id, 'sender_id', actor_id),
                'processed', ? FROM idempotency_requests
            WHERE actor_id = ? AND action = ? AND key_hash = ? AND resource_type = 'message'
              AND status = 'completed' AND resource_id IS NOT NULL AND changes() = 1
            """,
            (thread_id, timestamp, *receipt_key),
        ),
    ])
    if d1_change_count(results[0]) == 0:
        return None
    message_id = last_insert_id(results[0])
    if not message_id or any(d1_change_count(result) != 1 for result in results):
        raise ValueError("Unexpected D1 message save batch result.")
    return message_id


async def mark_message_thread_read(
    env,
    thread_id: int,
    user_id: int,
    last_read_message_id: int,
    last_read_at: str,
) -> None:
    await db_run(
        env,
        """
        INSERT INTO thread_reads
            (thread_id, user_id, last_read_message_id, last_read_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(thread_id, user_id) DO UPDATE SET
            last_read_message_id = MAX(
                thread_reads.last_read_message_id,
                excluded.last_read_message_id
            ),
            last_read_at = CASE
                WHEN excluded.last_read_message_id >= thread_reads.last_read_message_id
                THEN excluded.last_read_at
                ELSE thread_reads.last_read_at
            END
        """,
        thread_id,
        user_id,
        last_read_message_id,
        last_read_at,
    )


async def thread_for_messages(env, thread_id: int):
    result = await db_run(
        env,
        """
        SELECT threads.*, jobs.title, jobs.category, jobs.city, jobs.state,
               match_requests.price_range, match_requests.timeline,
               match_requests.availability,
               client.display_name AS client_name,
               COALESCE(
                   NULLIF(contractor_profile.business_name, ''),
                   NULLIF(contractor.company_name, ''),
                   contractor.display_name
               ) AS contractor_name,
               (
                   SELECT COUNT(*)
                   FROM match_requests AS completed_request
                   JOIN match_completions AS completed_match
                     ON completed_match.match_request_id = completed_request.id
                   WHERE completed_request.contractor_id = threads.contractor_id
                     AND completed_match.verified_at IS NOT NULL
               ) AS verified_completion_count,
               (
                   SELECT COUNT(*)
                   FROM contractor_credentials AS current_credential
                   WHERE current_credential.contractor_id = threads.contractor_id
                     AND current_credential.status = 'verified'
                     AND (
                         current_credential.expires_at IS NULL
                         OR current_credential.expires_at = ''
                         OR date(current_credential.expires_at) >= date('now')
                     )
               ) AS source_checked_credential_count,
               (
                   SELECT COUNT(*)
                   FROM contractor_credentials AS current_license
                   WHERE current_license.contractor_id = threads.contractor_id
                     AND current_license.credential_type = 'trade_license'
                     AND current_license.status = 'verified'
                     AND (
                         current_license.expires_at IS NULL
                         OR current_license.expires_at = ''
                         OR date(current_license.expires_at) >= date('now')
                     )
               ) AS source_checked_license_count
        FROM threads
        JOIN jobs ON jobs.id = threads.job_id
        JOIN match_requests ON match_requests.id = threads.match_request_id
        JOIN users AS client ON client.id = threads.client_id
        JOIN users AS contractor ON contractor.id = threads.contractor_id
        LEFT JOIN contractor_profiles AS contractor_profile
          ON contractor_profile.user_id = threads.contractor_id
        WHERE threads.id = ?
        LIMIT 1
        """,
        thread_id,
    )
    return first_row(result)


async def messages_for_thread(
    env, thread_id: int, through: int | None, *, include_hidden: bool = False,
) -> tuple[list[dict], int | None]:
    query, params = message_window_query(thread_id, through, include_hidden=include_hidden)
    return message_history_page(rows_from(await db_run(env, query, *params)))


async def verify_turnstile_for_request(env, request, body: dict, action: str) -> dict:
    token = turnstile_token_from_payload(body)
    verification_payload = siteverify_payload(
        secret=getattr(env, "WORKDOE_TURNSTILE_SECRET_KEY", ""),
        token=token,
        remoteip=remote_ip_from_headers(request.headers),
        idempotency_key=body.get("turnstile_idempotency_key", ""),
    )
    async def exchange():
        options = {}
        try:
            from js import AbortSignal
        except ImportError:  # pragma: no cover - the JS API is only available inside Workers.
            pass
        else:
            options["signal"] = AbortSignal.timeout(int(TURNSTILE_VERIFY_TIMEOUT_SECONDS * 1000))
        response = await fetch(
            TURNSTILE_VERIFY_URL,
            method="POST",
            redirect="error",
            headers={"Content-Type": "application/json"},
            body=json.dumps(verification_payload),
            **options,
        )
        return await response_json_object(response)

    try:
        result = await asyncio.wait_for(exchange(), timeout=TURNSTILE_VERIFY_TIMEOUT_SECONDS)
    except Exception as exc:
        raise TurnstileError("Turnstile verification failed.") from exc

    environment = str(getattr(env, "WORKDOE_ENV", "production") or "production").lower()
    metadata = row_value(result, "metadata", {}) or {}
    staging = is_staging_environment(env)
    is_testing_result = bool(row_value(metadata, "result_with_testing_key", False))
    if environment != "production" and not staging and is_testing_result and result.get("success") is True:
        return result
    allowed_hosts = {"workdoe.com", "www.workdoe.com"}
    if staging:
        hostname = staging_hostname(getattr(env, "WORKDOE_PUBLIC_URL", None))
        allowed_hosts = {hostname} if hostname and hostname == getattr(env, "WORKDOE_DOMAIN", None) else set()
    elif environment != "production":
        # These are Turnstile response hostnames for local preview, not bind addresses.
        allowed_hosts.update({"localhost", "127.0.0.1", "0.0.0.0"})  # nosec B104
    result_action = row_value(result, "action", "")
    action_allowed = result_action == action or (
        environment != "production" and not staging and result_action == "test"
    )
    if (staging and is_testing_result) or not turnstile_result_allowed(result, allowed_hosts) or not action_allowed:
        error_codes = result.get("error-codes", [])
        known_codes = {
            "missing-input-secret", "invalid-input-secret", "missing-input-response",
            "invalid-input-response", "bad-request", "timeout-or-duplicate", "internal-error",
        }
        print(json.dumps({
            "event": "workdoe-turnstile-verification-rejected",
            "codes": [code for code in error_codes if isinstance(code, str) and code in known_codes]
            if isinstance(error_codes, list) else [],
            "hostname_allowed": row_value(result, "hostname", "") in allowed_hosts,
            "action_allowed": action_allowed,
        }))
        raise TurnstileError("Turnstile verification failed.")
    return result


async def current_marketplace_email_body(env, body: dict) -> dict | None:
    query = marketplace_email_delivery_query(body)
    if query is None:
        return None
    sql, bindings = query
    current = first_row(await db_run(env, sql, *bindings))
    if current is None or contains_disallowed_personal_data(
        row_value(current, field, "") for field in ("job_title", "city", "state", "contractor_name")
    ):
        return None
    queued_email = body.get("to")
    current_email = row_value(current, "recipient_email", "")
    if (not isinstance(queued_email, str) or not isinstance(current_email, str)
            or not current_email or normalize_email(queued_email) != normalize_email(current_email)):
        return None
    kind = body["type"]
    payload = {
        "type": kind, "to": current_email,
        "job_title": row_value(current, "job_title", ""),
        "location": f"{row_value(current, 'city', '')}, {row_value(current, 'state', '')}",
    }
    if kind == "stale-match-reminder":
        payload.update({
            "match_request_id": body["match_request_id"],
            "contractor_name": row_value(current, "contractor_name", ""),
            "preferences_url": "https://workdoe.com/client/profile#bid-reminders",
        })
    else:
        payload["job_url"] = f"https://workdoe.com/jobs/{row_value(current, 'job_id')}"
        if kind == "contractor-new-lead":
            payload.update({
                "lead_alert_delivery_id": body["lead_alert_delivery_id"],
                "service_name": service_label(row_value(current, "service_slug", ""), row_value(current, "category", "")),
                "settings_url": "https://workdoe.com/leads#saved-lead-alerts",
            })
    return payload


async def process_email_queue_message(env, message, body: dict, queue_name: str) -> None:
    attempts = getattr(message, "attempts", 0)
    event_type = body.get("type") if isinstance(body, dict) else None
    if (
        isinstance(event_type, str) and event_type in OPTIONAL_MARKETPLACE_EMAIL_EVENTS
        and not marketplace_email_enabled(env)
    ):
        # A stale optional notice must not be replayed after delivery resumes.
        await record_event(
            env,
            "email-message-suppressed",
            target_type=queue_name,
            payload={"type": event_type, "reason": "marketplace-email-paused", "attempts": attempts},
            status="processed",
        )
        ack_message(message)
        return
    if event_type == "contractor-lead-alert-fanout":
        job_id = positive_int(body.get("job_id"))
        if not job_id:
            await record_event(
                env,
                "contractor-lead-alert-fanout-invalid",
                target_type=queue_name,
                payload={"attempts": attempts},
                status="failed",
            )
            ack_message(message)
            return
        try:
            queued_count = await process_contractor_lead_alert_fanout(env, job_id)
        except Exception as exc:  # noqa: BLE001 - alert fanout crosses Queue and D1 bindings.
            await record_event_best_effort(
                env,
                "contractor-lead-alert-fanout-failed",
                target_type="job",
                target_id=job_id,
                payload={"error_type": type(exc).__name__, "attempts": attempts},
                status="failed",
            )
            retry_message(message)
            return
        await record_event_best_effort(
            env,
            "contractor-lead-alert-fanout-processed",
            target_type="job",
            target_id=job_id,
            payload={"queued_count": queued_count, "attempts": attempts},
            status="processed",
        )
        ack_message(message)
        return
    if isinstance(event_type, str) and event_type in OPTIONAL_MARKETPLACE_EMAIL_EVENTS:
        try:
            current_body = await current_marketplace_email_body(env, body)
        except Exception as exc:  # noqa: BLE001 - D1 availability must fail closed before delivery.
            await record_event_best_effort(
                env, "email-message-eligibility-unavailable", target_type=queue_name,
                payload={"type": event_type, "error_type": type(exc).__name__, "attempts": attempts},
                status="failed",
            )
            retry_message(message)
            return
        if current_body is None:
            await record_event(
                env, "email-message-suppressed", target_type=queue_name,
                payload={"type": event_type, "reason": "notice-no-longer-eligible", "attempts": attempts},
                status="processed",
            )
            ack_message(message)
            return
        body = current_body
    audit_metadata = email_audit_metadata(
        body,
        getattr(env, "WORKDOE_SECRET_KEY", ""),
    )
    try:
        email_message = build_email_message(
            body,
            from_email=getattr(env, "WORKDOE_EMAIL_FROM", "no-reply@workdoe.com"),
            admin_email=getattr(env, "WORKDOE_ADMIN_EMAIL", ""),
        )
    except EmailPayloadError as exc:
        delivery_id = positive_int(
            body.get("lead_alert_delivery_id") if isinstance(body, dict) else 0
        )
        if delivery_id:
            await db_run(
                env,
                """
                UPDATE contractor_lead_alert_deliveries
                SET status = 'failed', updated_at = ?
                WHERE id = ?
                """,
                utc_now(),
                delivery_id,
            )
        await record_event(
            env,
            "email-message-invalid",
            target_type=queue_name,
            payload={**audit_metadata, "reason": str(exc), "attempts": attempts},
            status="failed",
        )
        ack_message(message)
        return

    if not hasattr(env, "EMAIL"):
        await record_event(
            env,
            "email-message-missing-binding",
            target_type=queue_name,
            payload={**audit_metadata, "attempts": attempts},
            status="failed",
        )
        retry_message(message)
        return

    try:
        result = await env.EMAIL.send(email_message)
    except Exception as exc:  # noqa: BLE001 - Email binding errors are JS-backed.
        await record_event(
            env,
            "email-message-send-failed",
            target_type=queue_name,
            payload={
                **audit_metadata,
                "error_type": type(exc).__name__,
                "attempts": attempts,
            },
            status="failed",
        )
        retry_message(message)
        return

    # Email delivery is irreversible. A failed audit write must not redeliver it.
    ack_message(message)
    delivery_id = positive_int(
        body.get("lead_alert_delivery_id") if isinstance(body, dict) else 0
    )
    if delivery_id:
        try:
            await db_run(
                env,
                """
                UPDATE contractor_lead_alert_deliveries
                SET status = 'sent', sent_at = ?, updated_at = ?
                WHERE id = ?
                """,
                utc_now(),
                utc_now(),
                delivery_id,
            )
        except Exception as exc:  # noqa: BLE001 - delivery audit is best effort.
            print(
                json.dumps(
                    {
                        "event": "contractor-lead-alert-delivery-write-failed",
                        "delivery_id": delivery_id,
                        "error_type": type(exc).__name__,
                    },
                    sort_keys=True,
                )
            )
    await record_event_best_effort(
        env,
        "email-message-sent",
        target_type=queue_name,
        payload={
            **audit_metadata,
            "result": email_send_result_summary(result),
            "attempts": attempts,
        },
        status="processed",
    )


async def process_media_review_queue_message(env, message, body: dict, queue_name: str) -> None:
    attempts = getattr(message, "attempts", 0)
    try:
        payload = validated_media_review_payload(body)
    except MediaUploadError:
        await record_event(
            env,
            "media-review-message-invalid",
            target_type=queue_name,
            payload={
                **queue_payload_shape(body),
                "reason": "invalid-media-review",
                "attempts": attempts,
            },
            status="failed",
        )
        ack_message(message)
        return

    await record_event(
        env,
        "media-review-message-accepted",
        target_type=f"{payload['scope']}_photo",
        target_id=payload["photo_id"],
        payload={
            "queue": queue_name,
            "content_type": payload["content_type"],
            "size_bytes": payload["size_bytes"],
            "checks": payload["checks"],
            "attempts": attempts,
        },
        status="processed",
    )
    ack_message(message)


async def send_queue_json(binding, payload: dict):
    value = normalize_json_value(payload)
    if not isinstance(value, dict):
        raise JsonDataError("Queue JSON payload must be an object.")
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_QUEUE_JSON_BODY_BYTES:
        raise JsonDataError("Queue JSON payload exceeds its byte limit.")
    if JS_JSON is not None:
        # Plain JSON avoids RPC Map encoding and preserves null.
        value = JS_JSON.parse(encoded)
    return await binding.send(value)


async def dispatch_queue_json(env, message, body, queue_name: str, handler) -> None:
    try:
        normalized = normalize_json_value(body)
    except JsonDataError:
        await record_event(
            env, "queue-message-invalid-json", target_type=queue_name,
            payload={**queue_payload_shape(body), "attempts": getattr(message, "attempts", 0)},
            status="failed",
        )
        ack_message(message)
        return
    await handler(env, message, normalized, queue_name)


async def dispatch_media_review_message(env, message, body, queue_name: str) -> None:
    await dispatch_queue_json(env, message, body, queue_name, process_media_review_queue_message)
