from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from admin_moderation import (
    AdminModerationError,
    admin_moderation_response,
    admin_target_query,
    admin_update_statement,
    can_admin_moderate,
    parse_admin_moderation_path,
)
from app_shell import (
    admin_dashboard_html,
    app_login_url,
    app_shell_headers,
    client_job_detail_html,
    client_dashboard_html,
    contractor_dashboard_html,
    contractor_job_detail_html,
    contractor_profile_html,
    dashboard_path_for_user,
    is_public_contractor_profile_route,
    is_app_shell_route,
    job_form_html,
    lead_board_html,
    message_thread_detail_html,
    message_threads_html,
    parse_app_client_job_id,
    parse_app_contractor_id,
    parse_app_job_id,
    parse_app_thread_id,
    public_contractor_profile_html,
    simple_app_html,
)
from clerk_onboarding import (
    MAX_ONBOARDING_BODY_BYTES,
    OnboardingError,
    claims_with_verified_clerk_email,
    onboarding_payload,
)
from clerk_sessions import (
    SessionVerificationError,
    authorized_parties_from_env,
    extract_clerk_session_token,
    verify_clerk_session_token,
)
from clerk_webhooks import (
    SvixVerificationError,
    clerk_user_sync_payload,
    verify_svix_signature,
)
from email_payloads import EmailPayloadError, build_email_message
from demo_projects import guest_project_rows
from email_code_auth import (
    AUTH_PROVIDER as EMAIL_CODE_AUTH_PROVIDER,
    CHALLENGE_TTL_SECONDS,
    MAX_CODE_ATTEMPTS,
    EmailCodeAuthError,
    challenge_token,
    clear_session_cookie,
    compact_spaces as compact_auth_text,
    generate_code,
    hash_code,
    hash_identifier,
    normalize_code,
    normalize_email,
    normalize_intent as normalize_auth_intent,
    role_for_intent,
    safe_next_path,
    session_cookie,
    session_from_cookie,
    session_token,
    tokens_match,
    valid_email,
    verified_token,
)
from contractor_profiles import (
    MAX_CONTRACTOR_PROFILE_BODY_BYTES,
    ContractorProfileError,
    can_update_contractor_profile,
    contractor_profile_payload,
    contractor_profile_response,
)
from contractor_public_profiles import (
    ContractorPublicProfileError,
    can_view_public_contractor_profile,
    parse_public_contractor_id,
    public_contractor_profile_payload,
)
from contractor_leads import (
    can_view_contractor_leads,
    contractor_lead_filters_from_query,
    contractor_lead_order_clause,
    contractor_leads_payload,
    normalize_contractor_lead_view,
    parse_contractor_lead_limit,
)
from contractor_bids import (
    CONTRACTOR_BID_LIMIT,
    can_view_contractor_bids,
    contractor_bids_payload,
    normalize_contractor_bid_view,
)
from client_jobs import (
    CLIENT_JOB_LIMIT,
    can_view_client_jobs,
    client_jobs_payload,
    normalize_client_job_view,
)
from entry_shell import (
    ENTRY_JOB_LIMIT,
    ENTRY_ROUTES,
    build_entry_shell_html,
    shell_headers,
)
from client_requests import (
    CLIENT_REQUEST_LIMIT,
    ClientRequestError,
    can_view_client_job_requests,
    client_job_requests_payload,
    normalize_client_request_view,
    parse_client_job_requests_path,
)
from clerk_proxy import (
    ClerkProxyError,
    clerk_proxy_request_plan,
    is_clerk_proxy_path,
)
from job_posts import (
    JOB_LOCATION_PRIVACY_NOTICE,
    MAX_JOB_POST_BODY_BYTES,
    JobPostError,
    job_post_payload,
)
from job_status import (
    JobStatusError,
    can_update_job_status,
    job_status_response,
    parse_job_status_path,
)
from job_details import (
    JobDetailError,
    can_view_job_detail,
    job_detail_payload,
    parse_job_detail_id,
    viewer_kind,
)
from match_decisions import (
    APPROVAL_THREAD_MESSAGE,
    MatchDecisionError,
    can_decide_match_request,
    match_decision_response,
    parse_match_decision_path,
)
from match_requests import (
    MAX_MATCH_REQUEST_BODY_BYTES,
    MatchRequestError,
    match_request_payload,
    parse_match_request_job_id,
)
from message_threads import (
    MAX_MESSAGE_BODY_BYTES,
    MessageThreadError,
    can_send_thread_message,
    can_view_thread,
    message_body_payload,
    message_thread_summary,
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
from media_access import (
    MediaAccessError,
    PRIVATE_MEDIA_NOTICE,
    can_view_contractor_photo,
    can_view_job_photo,
    inline_content_disposition,
    media_scope_from_path,
    safe_media_key,
)
from media_uploads import (
    MAX_UPLOAD_BYTES,
    MediaUploadError,
    build_r2_upload_key,
    can_upload_contractor_photo,
    can_upload_job_photo,
    form_file_value,
    media_review_payload,
    media_upload_scope_from_path,
    upload_http_metadata,
    uploaded_file_details,
    validated_media_review_payload,
)
from public_jobs import (
    first_query_value,
    normalize_public_target,
    parse_public_limit,
    public_job_filters_from_query,
    public_job_order_clause,
    public_jobs_payload,
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
    from pyodide.ffi import jsnull as JS_NULL
except ImportError:  # pragma: no cover - available inside the Workers runtime
    JS_NULL = None


EXPIRE_CODES_CRON = "*/15 * * * *"
STALE_MATCH_REMINDERS_CRON = "0 14 * * *"
MODERATION_DIGEST_CRON = "0 13 * * 1-5"
MAX_AUTH_BODY_BYTES = 8 * 1024
AUTH_REQUEST_WINDOW_MINUTES = 15
AUTH_REQUESTS_PER_EMAIL = 5
AUTH_REQUESTS_PER_IP = 20
PUBLIC_HTTPS_HOSTS = {"workdoe.com", "www.workdoe.com"}
HSTS_HEADER = "max-age=31536000; includeSubDomains"
STATIC_ASSET_PATHS = {
    "/clerk-entry.js",
    "/deer.svg",
    "/email-code-entry.js",
    "/field-doe.webp",
    "/map.js",
    "/site.webmanifest",
    "/styles.css",
    "/workdoe-share.png",
    "/worker-actions.js",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def json_response(payload: dict, status: int = 200, headers: dict | None = None) -> Response:
    response_headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Strict-Transport-Security": HSTS_HEADER,
    }
    response_headers.update(headers or {})
    return Response(
        json.dumps(payload),
        status=status,
        headers=response_headers,
    )


def rows_from(result) -> list[dict]:
    if isinstance(result, dict):
        return result.get("results") or result.get("result", {}).get("results") or []
    return getattr(result, "results", None) or []


async def db_run(env, sql: str, *params):
    statement = env.DB.prepare(sql)
    if params:
        d1_params = tuple(JS_NULL if value is None else value for value in params)
        statement = statement.bind(*d1_params)
    return await statement.run()


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


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
    content_length = request_header(request, "Content-Length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise ValueError
        except ValueError as exc:
            raise OnboardingError("Request body is too large.") from exc
    raw_body = await request.text()
    if len(raw_body.encode("utf-8")) > max_bytes:
        raise OnboardingError("Request body is too large.")
    try:
        data = json.loads(raw_body or "{}")
    except json.JSONDecodeError as exc:
        raise OnboardingError("Request body must be valid JSON.") from exc
    if not isinstance(data, dict):
        raise OnboardingError("Request body must be a JSON object.")
    return data


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


async def linked_workdoe_user(env, clerk_subject: str):
    lookup = await db_run(
        env,
        """
        SELECT id, role, display_name, company_name, status
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
    return getattr(env, "WORKDOE_AUTH_PROVIDER", "") == EMAIL_CODE_AUTH_PROVIDER


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
    role = row_value(user, "role")
    if requested == "/dashboard":
        return fallback
    if role == "client" and (
        requested == "/jobs/new"
        or requested.startswith("/client/")
        or requested.startswith("/messages/")
    ):
        return requested
    if role == "contractor" and (
        requested == "/leads"
        or requested.startswith("/jobs/")
        or requested.startswith("/contractor/")
        or requested.startswith("/messages/")
    ):
        return requested
    if role == "admin" and requested.startswith("/admin"):
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


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        redirect_url = public_https_redirect_url(request.url)
        if redirect_url:
            return Response(
                "",
                status=308,
                headers={
                    "Location": redirect_url,
                    "Cache-Control": "public, max-age=3600",
                },
            )

        parsed_request = urlparse(request.url)
        path = parsed_request.path

        if path.startswith("/static/"):
            asset_path = path.removeprefix("/static")
            return Response(
                "",
                status=308,
                headers={
                    "Location": parsed_request._replace(path=asset_path).geturl(),
                    "Cache-Control": "public, max-age=86400",
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
                    },
                }
            )

        if path in ENTRY_ROUTES:
            return await self.entry_shell(request, path)

        if is_clerk_proxy_path(path) and not native_email_code_enabled(self.env):
            return await self.clerk_frontend_api_proxy(request)

        if is_public_contractor_profile_route(path):
            return await self.contractor_profile_page(request, path)

        if is_app_shell_route(path):
            return await self.app_shell(request, path)

        if path == "/api/jobs/open":
            return await self.public_open_jobs(request)

        if path == "/api/client/jobs":
            return await self.client_jobs(request)

        if path.startswith("/api/client/jobs/") and path.endswith("/requests"):
            return await self.client_job_requests(request, path)

        if path == "/api/contractor/leads":
            return await self.contractor_leads(request)

        if path == "/api/contractor/bids":
            return await self.contractor_bids(request)

        if path == "/api/jobs":
            return await self.create_job(request)

        if path == "/api/contractor/profile":
            return await self.contractor_profile_api(request)

        if path.startswith("/api/contractors/"):
            return await self.public_contractor_profile(request, path)

        if path == "/api/reports":
            return await self.create_report(request)

        if path.startswith("/api/admin/"):
            return await self.admin_moderation_action(request, path)

        if path.startswith("/api/jobs/") and path.endswith("/request"):
            return await self.create_match_request(request, path)

        if path.startswith("/api/jobs/") and (
            path.endswith("/close") or path.endswith("/reopen")
        ):
            return await self.update_job_status(request, path)

        if path.startswith("/api/jobs/"):
            return await self.job_detail(request, path)

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

        if path.startswith("/media/jobs/") or path.startswith("/media/contractors/"):
            return await self.private_media(request, path)

        if path.startswith("/api/media/jobs/") or path.startswith("/api/media/contractors/"):
            return await self.upload_private_media(request, path)

        if path == "/clerk/webhook":
            return await self.handle_clerk_webhook(request)

        if is_static_asset_path(path) and hasattr(self.env, "ASSETS"):
            return await self.env.ASSETS.fetch(request)

        return json_response(
            {"ok": False, "error": "Not found."},
            status=404,
            headers={"Cache-Control": "no-store"},
        )

    async def clerk_frontend_api_proxy(self, request):
        try:
            plan = clerk_proxy_request_plan(
                request.url,
                request.headers,
                secret_key=getattr(self.env, "CLERK_SECRET_KEY", ""),
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
        return await fetch(plan["url"], **fetch_options)

    async def entry_shell(self, request, path: str):
        if request.method not in {"GET", "HEAD"}:
            return json_response(
                {"ok": False, "error": "Entry pages accept GET only."},
                status=405,
                headers={"Allow": "GET, HEAD"},
            )

        params = parse_qs(urlparse(request.url).query)
        rows = []
        filters = public_job_filters_from_query(params)
        if hasattr(self.env, "DB"):
            rows = await entry_shell_jobs(self.env, params)
        rows = guest_project_rows(rows, filters)
        auth_provider = getattr(
            self.env,
            "WORKDOE_AUTH_PROVIDER",
            EMAIL_CODE_AUTH_PROVIDER,
        )
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
        html = build_entry_shell_html(
            path,
            params,
            rows,
            clerk_publishable_key,
            clerk_frontend_api_url,
            auth_provider=auth_provider,
            turnstile_site_key=getattr(self.env, "WORKDOE_TURNSTILE_SITE_KEY", ""),
        )
        body = "" if request.method == "HEAD" else html
        return Response(
            body,
            status=200,
            headers=shell_headers(
                clerk_frontend_api_url,
                include_turnstile=native_auth
                and path in {"/start", "/login"}
                and bool(getattr(self.env, "WORKDOE_TURNSTILE_SITE_KEY", "")),
                clerk_publishable_key=clerk_publishable_key,
            ),
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

        params = parse_qs(urlparse(request.url).query)
        html = ""
        include_map = False
        include_turnstile = False
        role = row_value(user, "role")

        if path == "/client/dashboard" and role == "client":
            view = normalize_client_job_view(first_query_value(params, "view"))
            rows = await client_jobs_for_user(self.env, row_value(user, "id"))
            html = client_dashboard_html(user, client_jobs_payload(rows, view))
        elif path == "/contractor/dashboard" and role == "contractor":
            view = normalize_contractor_bid_view(first_query_value(params, "bids"))
            rows = await contractor_bids_for_user(self.env, row_value(user, "id"))
            html = contractor_dashboard_html(user, contractor_bids_payload(rows, view))
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
            html = lead_board_html(user, contractor_leads_payload(rows, filters, view))
            include_map = True
        elif path == "/jobs/new" and role == "client":
            include_turnstile = bool(getattr(self.env, "WORKDOE_TURNSTILE_SITE_KEY", ""))
            html = job_form_html(
                user,
                getattr(self.env, "WORKDOE_TURNSTILE_SITE_KEY", ""),
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
            rows = await client_requests_for_job(self.env, job_id)
            html = client_job_detail_html(
                user,
                job_detail_payload(user, job, photos),
                client_job_requests_payload(job, rows, view),
            )
        elif path.startswith("/jobs/") and role in {"contractor", "admin"}:
            job_id = parse_app_job_id(path)
            job = await job_for_detail(self.env, job_id)
            if not can_view_job_detail(user, job):
                return Response("Lead not found", status=404, headers={"Cache-Control": "no-store"})
            include_hidden = row_value(user, "role") == "admin"
            photos = await job_photos_for_detail(self.env, job_id, include_hidden=include_hidden)
            existing_request = None
            if row_value(user, "role") == "contractor":
                existing_request = await contractor_request_for_job(
                    self.env,
                    job_id,
                    row_value(user, "id"),
                )
            payload = job_detail_payload(user, job, photos, existing_request)
            include_turnstile = bool(getattr(self.env, "WORKDOE_TURNSTILE_SITE_KEY", ""))
            html = contractor_job_detail_html(
                user,
                payload,
                getattr(self.env, "WORKDOE_TURNSTILE_SITE_KEY", ""),
            )
        elif path == "/contractor/profile" and role == "contractor":
            profile = await ensure_contractor_profile(self.env, user, utc_now())
            photos = await visible_contractor_profile_photos(
                self.env,
                row_value(user, "id"),
            )
            html = contractor_profile_html(
                user,
                contractor_profile_response(profile),
                photos,
            )
        elif path == "/messages" and role in {"client", "contractor"}:
            rows = await message_threads_for_user(
                self.env,
                row_value(user, "id"),
            )
            html = message_threads_html(
                user,
                message_threads_listing_payload(rows),
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
            messages = await messages_for_thread(
                self.env,
                thread_id,
                include_hidden=row_value(user, "role") == "admin",
            )
            html = message_thread_detail_html(
                user,
                thread_detail_payload(thread, messages),
                can_reply=can_send_thread_message(user, thread),
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
                include_turnstile=include_turnstile,
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
        contractor = await public_contractor_for_profile(self.env, contractor_id)
        if not can_view_public_contractor_profile(user, contractor):
            return Response(
                "Contractor profile not found.",
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        photos = await visible_contractor_profile_photos(self.env, contractor_id)
        payload = public_contractor_profile_payload(contractor, photos, user)
        body = "" if request.method == "HEAD" else public_contractor_profile_html(user, payload)
        return Response(
            body,
            status=200,
            headers=app_shell_headers(),
        )

    async def public_open_jobs(self, request):
        if not hasattr(self.env, "DB"):
            return json_response(
                {
                    "ok": False,
                    "error": "D1 binding is required before public jobs can load.",
                },
                status=503,
                headers={"Cache-Control": "no-store"},
            )

        params = parse_qs(urlparse(request.url).query)
        limit = parse_public_limit(first_query_value(params, "limit"))
        filters = public_job_filters_from_query(params)
        target = normalize_public_target(first_query_value(params, "target"))
        sql = [
            """
            SELECT
                jobs.id,
                jobs.title,
                jobs.category,
                jobs.city,
                jobs.state,
                jobs.description,
                jobs.approx_lat,
                jobs.approx_lng,
                jobs.created_at,
                jobs.desired_date,
                COUNT(job_photos.id) AS photo_count
            FROM jobs
            LEFT JOIN job_photos
              ON job_photos.job_id = jobs.id
             AND job_photos.is_hidden = 0
            WHERE jobs.status = 'open'
            """,
        ]
        bindings: list[str | int] = []
        if filters["category"]:
            sql.append("AND jobs.category = ?")
            bindings.append(filters["category"])
        if filters["q"]:
            like = f"%{filters['q']}%"
            sql.append(
                "AND (jobs.city LIKE ? OR jobs.state LIKE ? OR jobs.zip_code LIKE ? OR jobs.title LIKE ?)"
            )
            bindings.extend([like, like, like, like])
        sql.append(f"GROUP BY jobs.id ORDER BY {public_job_order_clause(filters['sort'])} LIMIT ?")
        bindings.append(limit)

        try:
            result = await db_run(self.env, "\n".join(sql), *bindings)
        except Exception:
            return json_response(
                {
                    "ok": False,
                    "error": "Public jobs are temporarily unavailable.",
                },
                status=503,
                headers={"Cache-Control": "no-store"},
            )

        rows = guest_project_rows(rows_from(result), filters)
        return json_response(
            public_jobs_payload(rows, filters=filters, target=target, view="all"),
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
        rows = await client_requests_for_job(self.env, job_id)
        return json_response(
            client_job_requests_payload(job, rows, view),
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
        return json_response(
            contractor_leads_payload(rows, filters=filters, view=view),
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
        rows = await contractor_bids_for_user(self.env, row_value(user, "id"))
        return json_response(
            contractor_bids_payload(rows, view),
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

        created_at = utc_now()
        result = await db_run(
            self.env,
            """
            INSERT INTO jobs
                (client_id, title, category, city, state, zip_code, description,
                 desired_date, status, approx_lat, approx_lng, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)
            """,
            row_value(user, "id"),
            job["title"],
            job["category"],
            job["city"],
            job["state"],
            job["zip_code"],
            job["description"],
            job["desired_date"],
            job["approx_lat"],
            job["approx_lng"],
            created_at,
            created_at,
        )
        job_id = last_insert_id(result)
        await record_event(
            self.env,
            "job-created",
            target_type="job",
            target_id=job_id,
            payload={
                "client_id": row_value(user, "id"),
                "category": job["category"],
                "city": job["city"],
                "state": job["state"],
            },
            status="processed",
        )
        return json_response(
            {
                "ok": True,
                "job_id": job_id,
                "url": f"/client/jobs/{job_id}" if job_id else "/client/dashboard",
                "location_privacy": JOB_LOCATION_PRIVACY_NOTICE,
            },
            status=201,
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
            SELECT id, status
            FROM jobs
            WHERE id = ?
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
        result = await db_run(
            self.env,
            """
            INSERT INTO match_requests
                (job_id, contractor_id, scope_note, price_range, timeline,
                 experience, questions, availability, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            job_id,
            row_value(user, "id"),
            bid["scope_note"],
            bid["price_range"],
            bid["timeline"],
            bid["experience"],
            bid["questions"],
            bid["availability"],
            created_at,
            created_at,
        )
        request_id = last_insert_id(result)
        await record_event(
            self.env,
            "match-request-created",
            target_type="match_request",
            target_id=request_id,
            payload={
                "job_id": job_id,
                "contractor_id": row_value(user, "id"),
                "status": "pending",
            },
            status="processed",
        )
        return json_response(
            {
                "ok": True,
                "request_id": request_id,
                "job_id": job_id,
                "status": "pending",
                "message": "Mini bid sent. The client can approve it to open messaging.",
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
            return json_response(
                {
                    "ok": True,
                    "profile": contractor_profile_response(profile),
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
        saved = await contractor_profile_for_user(self.env, row_value(user, "id"))
        await record_event(
            self.env,
            "contractor-profile-updated",
            target_type="user",
            target_id=row_value(user, "id"),
            payload={
                "business_name": profile["business_name"],
                "trades": profile["trades"],
                "service_area": profile["service_area"],
            },
            status="processed",
        )
        return json_response(
            {
                "ok": True,
                "profile": contractor_profile_response(saved or profile),
                "url": f"/contractors/{row_value(user, 'id')}",
            },
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
        contractor = await public_contractor_for_profile(self.env, contractor_id)
        if not can_view_public_contractor_profile(user, contractor):
            return json_response(
                {"ok": False, "error": "Contractor profile not found."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        photos = await visible_contractor_profile_photos(self.env, contractor_id)
        return json_response(
            public_contractor_profile_payload(contractor, photos, user),
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

        if not await report_target_exists(
            self.env,
            report["target_type"],
            report["target_id"],
        ):
            return json_response(
                {"ok": False, "error": "That item is no longer available to report."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )

        created_at = utc_now()
        result = await db_run(
            self.env,
            """
            INSERT INTO reports
                (reporter_id, target_type, target_id, reason, status, created_at, resolved_at)
            VALUES (?, ?, ?, ?, 'open', ?, NULL)
            """,
            row_value(user, "id"),
            report["target_type"],
            report["target_id"],
            report["reason"],
            created_at,
        )
        report_id = last_insert_id(result)
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
        return json_response(
            report_response(report_id, report),
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

        acted_at = utc_now()
        sql, params, notes, state = admin_update_statement(action, acted_at)
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

        updated_at = utc_now()
        await db_run(
            self.env,
            """
            UPDATE jobs
            SET status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            status,
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
            },
            status="processed",
        )
        return json_response(
            job_status_response(job_id, status),
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
        job = await job_for_detail(self.env, job_id)
        if not job:
            return json_response(
                {"ok": False, "error": "Job not found."},
                status=404,
                headers={"Cache-Control": "no-store"},
            )
        if not can_view_job_detail(user, job):
            return json_response(
                {"ok": False, "error": "You cannot view this job."},
                status=403,
                headers={"Cache-Control": "no-store"},
            )
        viewer = viewer_kind(user, job)
        include_hidden_photos = viewer in {"owner", "admin"}
        photos = await job_photos_for_detail(
            self.env,
            job_id,
            include_hidden=include_hidden_photos,
        )
        existing_request = None
        if viewer == "contractor":
            existing_request = await contractor_request_for_job(
                self.env,
                job_id,
                row_value(user, "id"),
            )
        return json_response(
            job_detail_payload(
                user,
                job,
                photos=photos,
                existing_request=existing_request,
            ),
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
            request_id, action, status = parse_match_decision_path(path)
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
        if row_value(match, "status") != "pending":
            existing_thread_id = await existing_thread_id_for_match(self.env, request_id)
            return json_response(
                {
                    "ok": False,
                    "error": "This mini bid has already been reviewed.",
                    "status": row_value(match, "status"),
                    "thread_id": existing_thread_id,
                },
                status=409,
                headers={"Cache-Control": "no-store"},
            )

        updated_at = utc_now()
        await db_run(
            self.env,
            """
            UPDATE match_requests
            SET status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            status,
            updated_at,
            request_id,
        )
        thread_id = None
        if status == "approved":
            thread_id = await ensure_thread_for_match(self.env, match, updated_at)
        event_type = "match-request-approved" if status == "approved" else "match-request-rejected"
        await record_event(
            self.env,
            event_type,
            target_type="match_request",
            target_id=request_id,
            payload={
                "action": action,
                "job_id": row_value(match, "job_id"),
                "client_id": row_value(match, "client_id"),
                "contractor_id": row_value(match, "contractor_id"),
                "thread_id": thread_id,
            },
            status="processed",
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
            return json_response(
                message_threads_listing_payload(rows),
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
            created_at = utc_now()
            result = await db_run(
                self.env,
                """
                INSERT INTO messages (thread_id, sender_id, body, is_hidden, created_at)
                VALUES (?, ?, ?, 0, ?)
                """,
                thread_id,
                row_value(user, "id"),
                message_body,
                created_at,
            )
            message_id = last_insert_id(result)
            await record_event(
                self.env,
                "message-created",
                target_type="thread",
                target_id=thread_id,
                payload={"message_id": message_id, "sender_id": row_value(user, "id")},
                status="processed",
            )
            return json_response(
                {
                    "ok": True,
                    "message_id": message_id,
                    "thread_id": thread_id,
                    "url": f"/messages/{thread_id}",
                },
                status=201,
                headers={"Cache-Control": "no-store"},
            )

        messages = await messages_for_thread(
            self.env,
            thread_id,
            include_hidden=row_value(user, "role") == "admin",
        )
        return json_response(
            thread_detail_payload(thread, messages),
            headers={"Cache-Control": "no-store"},
        )

    async def verified_clerk_claims(self, request):
        token = extract_clerk_session_token(request.headers)
        if not token:
            raise SessionVerificationError("Session token not found.")
        return await verify_clerk_session_token(
            token=token,
            jwt_key=getattr(self.env, "CLERK_JWT_KEY", ""),
            authorized_parties=authorized_parties_from_env(self.env, request.url),
        )

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
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET, HEAD", "Cache-Control": "no-store"},
            )
        if not hasattr(self.env, "DB") or not hasattr(self.env, "MEDIA"):
            return Response(
                "Media storage is not configured.",
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            scope, photo_id = media_scope_from_path(path)
        except MediaAccessError:
            return Response("Media not found", status=404, headers={"Cache-Control": "no-store"})

        if scope == "job":
            return await self.private_job_photo(request, photo_id)
        return await self.private_contractor_photo(request, photo_id)

    async def private_job_photo(self, request, photo_id: int):
        user = await self.optional_workdoe_user(request)
        if not user:
            return Response("Sign in required", status=401, headers={"Cache-Control": "no-store"})

        result = await db_run(
            self.env,
            """
            SELECT
                job_photos.id,
                job_photos.job_id,
                job_photos.original_filename,
                job_photos.stored_path,
                job_photos.content_type,
                job_photos.is_hidden,
                jobs.client_id,
                jobs.status,
                CASE WHEN EXISTS (
                    SELECT 1
                    FROM match_requests
                    WHERE match_requests.job_id = jobs.id
                      AND match_requests.contractor_id = ?
                      AND match_requests.status = 'approved'
                ) THEN 1 ELSE 0 END AS has_approved_match
            FROM job_photos
            JOIN jobs ON jobs.id = job_photos.job_id
            WHERE job_photos.id = ?
            LIMIT 1
            """,
            row_value(user, "id"),
            photo_id,
        )
        rows = rows_from(result)
        if not rows:
            return Response("Media not found", status=404, headers={"Cache-Control": "no-store"})
        photo = rows[0]
        if not can_view_job_photo(user, photo):
            if row_value(photo, "is_hidden"):
                return Response(
                    "Media not found",
                    status=404,
                    headers={"Cache-Control": "no-store"},
                )
            return Response("Forbidden", status=403, headers={"Cache-Control": "no-store"})

        try:
            key = safe_media_key(row_value(photo, "stored_path"), f"jobs/{row_value(photo, 'job_id')}")
        except MediaAccessError:
            return Response("Media not found", status=404, headers={"Cache-Control": "no-store"})
        return await self.r2_media_response(request, key, photo)

    async def private_contractor_photo(self, request, photo_id: int):
        user = await self.optional_workdoe_user(request)
        result = await db_run(
            self.env,
            """
            SELECT
                contractor_photos.id,
                contractor_photos.contractor_id,
                contractor_photos.original_filename,
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
            return Response("Media not found", status=404, headers={"Cache-Control": "no-store"})
        photo = rows[0]
        if not can_view_contractor_photo(user, photo):
            return Response("Media not found", status=404, headers={"Cache-Control": "no-store"})

        try:
            key = safe_media_key(
                row_value(photo, "stored_path"),
                f"contractors/{row_value(photo, 'contractor_id')}",
            )
        except MediaAccessError:
            return Response("Media not found", status=404, headers={"Cache-Control": "no-store"})
        return await self.r2_media_response(request, key, photo)

    async def r2_media_response(self, request, key: str, photo):
        try:
            media_object = await self.env.MEDIA.get(key)
        except Exception:
            return Response(
                "Media is temporarily unavailable.",
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        if media_object is None:
            return Response("Media not found", status=404, headers={"Cache-Control": "no-store"})

        headers = {
            "Cache-Control": "private, no-store",
            "Content-Disposition": inline_content_disposition(
                row_value(photo, "original_filename", "")
            ),
            "Content-Type": row_value(photo, "content_type") or "application/octet-stream",
            "X-Content-Type-Options": "nosniff",
            "X-Workdoe-Media-Policy": PRIVATE_MEDIA_NOTICE,
        }
        http_etag = getattr(media_object, "httpEtag", "")
        if http_etag:
            headers["ETag"] = http_etag
        body = None if request.method == "HEAD" else getattr(media_object, "body", None)
        return Response(body, status=200, headers=headers)

    async def upload_private_media(self, request, path: str):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST", "Cache-Control": "no-store"},
            )
        if (
            not hasattr(self.env, "DB")
            or not hasattr(self.env, "MEDIA")
            or not hasattr(self.env, "MEDIA_QUEUE")
        ):
            return json_response(
                {"ok": False, "error": "Media upload bindings are not configured."},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        content_length = parse_request_content_length(request)
        if content_length < 0 or content_length > MAX_UPLOAD_BYTES + 4096:
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

        try:
            form_data = await request.formData()
            upload_file = form_file_value(form_data, scope)
            details = uploaded_file_details(upload_file)
            key = build_r2_upload_key(scope, owner_id, details["extension"])
            await self.env.MEDIA.put(
                key,
                upload_file,
                {
                    "httpMetadata": upload_http_metadata(details),
                    "customMetadata": {
                        "scope": scope,
                        "owner_id": str(owner_id),
                        "uploaded_by": str(row_value(user, "id")),
                        "original_filename": details["original_filename"],
                    },
                },
            )
            photo_id = await self.insert_media_metadata(scope, owner_id, user, key, details)
            payload = media_review_payload(
                scope,
                photo_id,
                owner_id,
                row_value(user, "id"),
                key,
                details,
            )
            await self.env.MEDIA_QUEUE.send(payload)
        except MediaUploadError as exc:
            return json_response(
                {"ok": False, "error": str(exc)},
                status=400,
                headers={"Cache-Control": "no-store"},
            )
        except Exception:
            await record_event(
                self.env,
                "media-upload-failed",
                target_type=scope,
                target_id=owner_id,
                status="failed",
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
            raise MediaUploadError("Uploaded media metadata was not recorded.")
        return int(row_value(row, "id"))

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
                raise EmailCodeAuthError("Add your name to create a Workdoe account.")

            role = row_value(existing, "role") if existing else requested_role
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
                await self.env.EMAIL_QUEUE.send(
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
                    payload={"reason": str(exc)},
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
        except Exception as exc:
            await record_event(
                self.env,
                "login-code-request-failed",
                payload={"reason": str(exc)},
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
                    """,
                    MAX_CODE_ATTEMPTS,
                    failed_at,
                    row_value(login_code, "id"),
                )
                raise EmailCodeAuthError("That code did not match.", 401)

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
                await db_run(
                    self.env,
                    """
                    INSERT INTO users
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
                user = await workdoe_user_by_id_from_email(
                    self.env,
                    row_value(login_code, "email"),
                )
                if not user:
                    raise EmailCodeAuthError("Workdoe could not create the account.", 500)
                user_id = row_value(user, "id")
                if row_value(user, "role") == "client":
                    await db_run(
                        self.env,
                        """
                        INSERT INTO client_profiles (user_id, organization_name, phone)
                        VALUES (?, ?, '')
                        """,
                        user_id,
                        row_value(user, "company_name", ""),
                    )
                else:
                    await db_run(
                        self.env,
                        """
                        INSERT INTO contractor_profiles
                            (user_id, business_name, trades, service_area, intro,
                             insurance_status, license_number, years_in_business,
                             website, phone, updated_at)
                        VALUES (?, ?, '', 'DMV area', '', '', '', NULL, '', '', ?)
                        """,
                        user_id,
                        row_value(user, "company_name", ""),
                        created_at,
                    )
                created = True

            if row_value(user, "status") != "active":
                raise EmailCodeAuthError("This Workdoe account is not active.", 403)
            await db_run(
                self.env,
                "UPDATE login_codes SET used_at = ?, attempt_count = attempt_count + 1 WHERE id = ?",
                utc_now(),
                row_value(login_code, "id"),
            )
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
        except Exception as exc:
            await record_event(
                self.env,
                "login-code-verification-failed",
                payload={"reason": str(exc)},
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
        if request.method not in {"GET", "POST"}:
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "GET, POST", "Cache-Control": "no-store"},
            )
        if not native_email_code_enabled(self.env):
            try:
                claims = await self.verified_clerk_claims(request)
                secret_key = str(
                    getattr(self.env, "CLERK_SECRET_KEY", "") or ""
                ).strip()
                if secret_key:
                    response = await fetch(
                        f"https://api.clerk.com/v1/sessions/{claims['sid']}/revoke",
                        method="POST",
                        headers={
                            "Accept": "application/json",
                            "Authorization": f"Bearer {secret_key}",
                        },
                    )
                    if not response.ok:
                        raise SessionVerificationError(
                            "Clerk session revocation was not accepted."
                        )
            except Exception as exc:
                print(
                    json.dumps(
                        {
                            "event": "clerk-session-revoke-failed",
                            "reason": str(exc),
                        }
                    )
                )
        headers = {
            "Cache-Control": "no-store",
            "Set-Cookie": (
                clear_session_cookie()
                if native_email_code_enabled(self.env)
                else "__session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
            ),
        }
        if request.method == "GET":
            headers["Location"] = "/"
            return Response("", status=302, headers=headers)
        return json_response({"ok": True}, headers=headers)

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
                    "workdoe_user": workdoe_user_json(user),
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
            SELECT id, role, display_name, company_name, status
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
                    "clerk_user_id": claims["sub"],
                    "session_id": claims["sid"],
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
                "clerk_user_id": claims["sub"],
                "session_id": claims["sid"],
                "onboarding_required": False,
                "workdoe_user": {
                    "id": row_value(user, "id"),
                    "role": row_value(user, "role"),
                    "display_name": row_value(user, "display_name"),
                    "company_name": row_value(user, "company_name"),
                    "status": row_value(user, "status"),
                },
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
            secret_key = str(getattr(self.env, "CLERK_SECRET_KEY", "") or "").strip()
            if not secret_key:
                raise OnboardingError("Clerk user lookup is not configured.")
            try:
                clerk_user_response = await fetch(
                    f"https://api.clerk.com/v1/users/{claims['sub']}",
                    method="GET",
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {secret_key}",
                    },
                )
            except Exception as exc:
                raise OnboardingError("Clerk user lookup failed.") from exc
            if not clerk_user_response.ok:
                raise OnboardingError("Clerk user lookup was not accepted.")
            clerk_user = await clerk_user_response.json()
            claims = claims_with_verified_clerk_email(claims, clerk_user)
            body = await request_json_object(request)
            payload = onboarding_payload(claims, body)
        except (SessionVerificationError, OnboardingError):
            return json_response(
                {"ok": False, "error": "Onboarding request was not accepted."},
                status=400,
                headers={"Cache-Control": "no-store"},
            )

        existing_link = await db_run(
            self.env,
            """
            SELECT id, role, display_name, company_name, status
            FROM users
            WHERE auth_provider = 'clerk'
              AND external_subject = ?
            LIMIT 1
            """,
            claims["sub"],
        )
        linked_rows = rows_from(existing_link)
        if linked_rows:
            user = linked_rows[0]
            return json_response(
                {
                    "ok": True,
                    "created": False,
                    "workdoe_user": {
                        "id": row_value(user, "id"),
                        "role": row_value(user, "role"),
                        "display_name": row_value(user, "display_name"),
                        "company_name": row_value(user, "company_name"),
                        "status": row_value(user, "status"),
                    },
                },
                headers={"Cache-Control": "no-store"},
            )

        email_conflict = await db_run(
            self.env,
            """
            SELECT id
            FROM users
            WHERE email = ?
            LIMIT 1
            """,
            payload["email"],
        )
        if rows_from(email_conflict):
            return json_response(
                {
                    "ok": False,
                    "error": "A Workdoe account already uses this email.",
                },
                status=409,
                headers={"Cache-Control": "no-store"},
            )

        created_at = utc_now()
        await db_run(
            self.env,
            """
            INSERT INTO users
                (email, password_hash, role, display_name, company_name,
                 status, email_verified, auth_provider, external_subject, created_at)
            VALUES (?, 'clerk-managed', ?, ?, ?, 'active', 1, 'clerk', ?, ?)
            """,
            payload["email"],
            payload["role"],
            payload["display_name"],
            payload["company_name"],
            claims["sub"],
            created_at,
        )
        created_lookup = await db_run(
            self.env,
            """
            SELECT id, role, display_name, company_name, status
            FROM users
            WHERE auth_provider = 'clerk'
              AND external_subject = ?
            LIMIT 1
            """,
            claims["sub"],
        )
        created_rows = rows_from(created_lookup)
        if not created_rows:
            return json_response(
                {"ok": False, "error": "Workdoe account could not be created."},
                status=500,
                headers={"Cache-Control": "no-store"},
            )
        user = created_rows[0]
        user_id = row_value(user, "id")
        if payload["role"] == "client":
            await db_run(
                self.env,
                """
                INSERT INTO client_profiles (user_id, organization_name, phone)
                VALUES (?, ?, '')
                """,
                user_id,
                payload["company_name"],
            )
        else:
            await db_run(
                self.env,
                """
                INSERT INTO contractor_profiles
                    (user_id, business_name, trades, service_area, intro,
                     insurance_status, license_number, years_in_business,
                     website, phone, updated_at)
                VALUES (?, ?, '', 'DMV area', '', '', '', NULL, '', '', ?)
                """,
                user_id,
                payload["company_name"],
                created_at,
            )

        await record_event(
            self.env,
            "clerk-onboarding-linked",
            target_type="user",
            target_id=user_id,
            payload={
                "clerk_user_id": claims["sub"],
                "role": payload["role"],
                "email": payload["email"],
            },
            status="processed",
        )
        return json_response(
            {
                "ok": True,
                "created": True,
                "workdoe_user": {
                    "id": user_id,
                    "role": row_value(user, "role"),
                    "display_name": row_value(user, "display_name"),
                    "company_name": row_value(user, "company_name"),
                    "status": row_value(user, "status"),
                },
            },
            status=201,
            headers={"Cache-Control": "no-store"},
        )

    async def handle_clerk_webhook(self, request):
        if request.method != "POST":
            return Response(
                "Method not allowed",
                status=405,
                headers={"Allow": "POST"},
            )
        if not getattr(self.env, "CLERK_WEBHOOK_SECRET", ""):
            return json_response(
                {
                    "ok": False,
                    "error": "CLERK_WEBHOOK_SECRET is required before Clerk webhooks are accepted.",
                },
                status=503,
            )

        raw_body = await request.text()
        try:
            event = verify_svix_signature(
                secret=getattr(self.env, "CLERK_WEBHOOK_SECRET"),
                headers=request.headers,
                raw_body=raw_body,
            )
        except SvixVerificationError as exc:
            await record_event(
                self.env,
                "clerk-webhook-rejected",
                payload={"reason": str(exc)},
                status="failed",
            )
            return json_response(
                {"ok": False, "error": "Webhook verification failed."},
                status=400,
            )

        await record_event(
            self.env,
            "clerk-webhook-verified",
            target_type=event.get("type", ""),
            payload={
                "event_id": event.get("id"),
                "event_type": event.get("type"),
                "subject_id": event.get("data", {}).get("id"),
                "sync": await sync_linked_clerk_user(self.env, event),
            },
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

    async def queue(self, batch):
        for message in batch.messages:
            body = getattr(message, "body", {})
            queue_name = getattr(batch, "queue", "unknown")
            if queue_name == "workdoe-email":
                await process_email_queue_message(self.env, message, body, queue_name)
                continue
            if queue_name == "workdoe-media-review":
                await process_media_review_queue_message(self.env, message, body, queue_name)
                continue
            await record_event(
                self.env,
                "queue-message-consumed",
                target_type=queue_name,
                payload={"body": body, "attempts": getattr(message, "attempts", 0)},
                status="processed",
            )
            ack_message(message)


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
        await db_run(
            env,
            """
            UPDATE users
            SET email = ?,
                email_verified = ?,
                status = ?
            WHERE id = ?
            """,
            email,
            sync["email_verified"],
            sync["status"],
            user_id,
        )
        return {"action": "updated", "user_id": user_id}

    await db_run(
        env,
        """
        UPDATE users
        SET status = ?
        WHERE id = ?
        """,
        sync["status"],
        user_id,
    )
    return {"action": "status-updated", "user_id": user_id}


async def queue_stale_match_reminders(env) -> None:
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
        JOIN users AS contractors ON contractors.id = match_requests.contractor_id
        WHERE match_requests.status = 'pending'
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
        }
        await env.EMAIL_QUEUE.send(payload)
        await record_event(
            env,
            "stale-match-reminder",
            target_type="match_request",
            target_id=row["id"],
            payload=payload,
        )


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
    await env.EMAIL_QUEUE.send(payload)
    await record_event(env, "moderation-digest", payload=payload)


def ack_message(message) -> None:
    ack = getattr(message, "ack", None)
    if callable(ack):
        ack()


def retry_message(message) -> None:
    retry = getattr(message, "retry", None)
    if callable(retry):
        retry()


def email_send_result_summary(result) -> dict:
    if isinstance(result, dict):
        return {str(key): json_safe_value(value) for key, value in result.items()}
    summary = {}
    for key in ("messageId", "delivered", "queued", "permanent_bounces"):
        value = getattr(result, key, None)
        if value is not None:
            summary[key] = json_safe_value(value)
    return summary or {"ok": True}


def json_safe_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe_value(item) for item in value]
    return str(value)


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


async def report_target_exists(env, target_type: str, target_id: int) -> bool:
    result = await db_run(env, report_target_query(target_type), target_id)
    return first_row(result) is not None


async def admin_target_exists(env, target_type: str, target_id: int) -> bool:
    result = await db_run(env, admin_target_query(target_type), target_id)
    return first_row(result) is not None


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
    hidden_content = first_row(
        await db_run(
            env,
            """
            SELECT
                (SELECT COUNT(*) FROM jobs WHERE status = 'hidden') +
                (SELECT COUNT(*) FROM job_photos WHERE is_hidden = 1) +
                (SELECT COUNT(*) FROM contractor_photos WHERE is_hidden = 1) +
                (SELECT COUNT(*) FROM messages WHERE is_hidden = 1) AS total
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
    return {
        "ok": True,
        "users": users,
        "jobs": jobs,
        "reports": reports,
        "messages": messages,
        "actions": actions,
        "automation_events": automation_events,
        "photos": photos,
        "contractor_photos": contractor_photos,
        "stats": {
            "open_reports": len(reports),
            "suspended_users": sum(1 for user in users if row_value(user, "status") == "suspended"),
            "hidden_content": row_value(hidden_content, "total", 0) or 0,
            "audit_actions": row_value(audit_actions, "total", 0) or 0,
            "automation_events": row_value(automation_event_count, "total", 0) or 0,
        },
    }


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


async def public_contractor_for_profile(env, contractor_id: int):
    result = await db_run(
        env,
        """
        SELECT users.id, users.display_name, users.company_name, users.status,
               contractor_profiles.business_name,
               contractor_profiles.trades,
               contractor_profiles.service_area,
               contractor_profiles.intro,
               contractor_profiles.insurance_status,
               contractor_profiles.license_number,
               contractor_profiles.years_in_business,
               contractor_profiles.updated_at
        FROM users
        JOIN contractor_profiles ON contractor_profiles.user_id = users.id
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


async def client_jobs_for_user(env, client_id: int) -> list[dict]:
    result = await db_run(
        env,
        """
        SELECT
            jobs.id,
            jobs.title,
            jobs.category,
            jobs.city,
            jobs.state,
            jobs.zip_code,
            jobs.description,
            jobs.desired_date,
            jobs.status,
            jobs.created_at,
            jobs.updated_at,
            COUNT(match_requests.id) AS request_count,
            SUM(CASE WHEN match_requests.status = 'pending' THEN 1 ELSE 0 END) AS pending_count,
            SUM(CASE WHEN match_requests.status = 'approved' THEN 1 ELSE 0 END) AS approved_count,
            SUM(CASE WHEN match_requests.status = 'rejected' THEN 1 ELSE 0 END) AS rejected_count
        FROM jobs
        LEFT JOIN match_requests ON match_requests.job_id = jobs.id
        WHERE jobs.client_id = ?
        GROUP BY jobs.id
        ORDER BY jobs.created_at DESC, jobs.id DESC
        LIMIT ?
        """,
        client_id,
        CLIENT_JOB_LIMIT,
    )
    return rows_from(result)


async def client_job_for_requests(env, job_id: int):
    result = await db_run(
        env,
        """
        SELECT id, client_id, title, status
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
            threads.id AS thread_id
        FROM match_requests
        JOIN users ON users.id = match_requests.contractor_id
        LEFT JOIN contractor_profiles ON contractor_profiles.user_id = users.id
        LEFT JOIN threads ON threads.match_request_id = match_requests.id
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


async def entry_shell_jobs(env, params: dict) -> list[dict]:
    filters = public_job_filters_from_query(params)
    sql = [
        """
        SELECT jobs.id,
               jobs.title,
               jobs.category,
               jobs.city,
               jobs.state,
               jobs.description,
               jobs.desired_date,
               jobs.approx_lat,
               jobs.approx_lng,
               COUNT(job_photos.id) AS photo_count
        FROM jobs
        LEFT JOIN job_photos ON job_photos.job_id = jobs.id AND job_photos.is_hidden = 0
        WHERE jobs.status = 'open'
        """
    ]
    bindings: list[str | int] = []
    if filters["category"]:
        sql.append("AND jobs.category = ?")
        bindings.append(filters["category"])
    if filters["q"]:
        query = f"%{filters['q']}%"
        sql.append(
            "AND (jobs.city LIKE ? OR jobs.state LIKE ? OR jobs.title LIKE ?)"
        )
        bindings.extend([query, query, query])
    sql.append(f"GROUP BY jobs.id ORDER BY {public_job_order_clause(filters['sort'])} LIMIT ?")
    bindings.append(ENTRY_JOB_LIMIT)
    result = await db_run(env, "\n".join(sql), *bindings)
    return rows_from(result)


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
            jobs.city,
            jobs.state,
            jobs.description,
            jobs.desired_date,
            jobs.approx_lat,
            jobs.approx_lng,
            jobs.created_at,
            COUNT(job_photos.id) AS photo_count,
            MAX(match_requests.status) AS request_status
        FROM jobs
        LEFT JOIN job_photos
          ON job_photos.job_id = jobs.id
         AND job_photos.is_hidden = 0
        LEFT JOIN match_requests
          ON match_requests.job_id = jobs.id
         AND match_requests.contractor_id = ?
        WHERE jobs.status = 'open'
        """,
    ]
    bindings: list[str | int] = [contractor_id]
    if filters["category"]:
        sql.append("AND jobs.category = ?")
        bindings.append(filters["category"])
    if filters["q"]:
        like = f"%{filters['q']}%"
        sql.append(
            "AND (jobs.city LIKE ? OR jobs.state LIKE ? OR jobs.zip_code LIKE ? OR jobs.title LIKE ?)"
        )
        bindings.extend([like, like, like, like])
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
            threads.id AS thread_id
        FROM match_requests
        JOIN jobs ON jobs.id = match_requests.job_id
        LEFT JOIN threads ON threads.match_request_id = match_requests.id
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
        profile["phone"],
        updated_at,
    )


async def job_for_detail(env, job_id: int):
    result = await db_run(
        env,
        """
        SELECT jobs.*, users.display_name AS client_name, users.company_name AS client_company
        FROM jobs
        JOIN users ON users.id = jobs.client_id
        WHERE jobs.id = ?
        LIMIT 1
        """,
        job_id,
    )
    return first_row(result)


async def job_photos_for_detail(env, job_id: int, include_hidden: bool = False) -> list[dict]:
    hidden_clause = "" if include_hidden else "AND is_hidden = 0"
    result = await db_run(
        env,
        f"""
        SELECT id, original_filename, is_hidden
        FROM job_photos
        WHERE job_id = ? {hidden_clause}
        ORDER BY created_at
        LIMIT 24
        """,
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


async def ensure_thread_for_match(env, match, created_at: str) -> int | None:
    existing = await existing_thread_id_for_match(env, row_value(match, "id"))
    if existing:
        return existing
    result = await db_run(
        env,
        """
        INSERT INTO threads
            (job_id, match_request_id, client_id, contractor_id, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        row_value(match, "job_id"),
        row_value(match, "id"),
        row_value(match, "client_id"),
        row_value(match, "contractor_id"),
        created_at,
    )
    thread_id = last_insert_id(result)
    if thread_id:
        await db_run(
            env,
            """
            INSERT INTO messages
                (thread_id, sender_id, body, is_hidden, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            thread_id,
            row_value(match, "contractor_id"),
            APPROVAL_THREAD_MESSAGE,
            created_at,
        )
    return thread_id


async def message_threads_for_user(env, user_id: int) -> list[dict]:
    result = await db_run(
        env,
        """
        SELECT threads.*, jobs.title, jobs.category, jobs.city, jobs.state,
               client.display_name AS client_name,
               contractor.display_name AS contractor_name,
               (
                   SELECT body FROM messages
                   WHERE messages.thread_id = threads.id AND messages.is_hidden = 0
                   ORDER BY messages.created_at DESC
                   LIMIT 1
               ) AS last_message,
               (
                   SELECT created_at FROM messages
                   WHERE messages.thread_id = threads.id AND messages.is_hidden = 0
                   ORDER BY messages.created_at DESC
                   LIMIT 1
               ) AS last_message_at,
               (
                   SELECT COUNT(*) FROM messages
                   WHERE messages.thread_id = threads.id AND messages.is_hidden = 0
               ) AS message_count
        FROM threads
        JOIN jobs ON jobs.id = threads.job_id
        JOIN users AS client ON client.id = threads.client_id
        JOIN users AS contractor ON contractor.id = threads.contractor_id
        WHERE threads.client_id = ? OR threads.contractor_id = ?
        ORDER BY COALESCE(
            (
                SELECT created_at FROM messages
                WHERE messages.thread_id = threads.id AND messages.is_hidden = 0
                ORDER BY messages.created_at DESC
                LIMIT 1
            ),
            threads.created_at
        ) DESC
        LIMIT 50
        """,
        user_id,
        user_id,
    )
    return rows_from(result)


def message_threads_listing_payload(rows: list[dict]) -> dict:
    return {
        "ok": True,
        "threads": [message_thread_summary(thread) for thread in rows],
        "stats": {
            "threads": len(rows),
            "messages": sum(row_value(thread, "message_count", 0) or 0 for thread in rows),
        },
    }


async def thread_for_messages(env, thread_id: int):
    result = await db_run(
        env,
        """
        SELECT threads.*, jobs.title, jobs.category, jobs.city, jobs.state,
               client.display_name AS client_name,
               contractor.display_name AS contractor_name
        FROM threads
        JOIN jobs ON jobs.id = threads.job_id
        JOIN users AS client ON client.id = threads.client_id
        JOIN users AS contractor ON contractor.id = threads.contractor_id
        WHERE threads.id = ?
        LIMIT 1
        """,
        thread_id,
    )
    return first_row(result)


async def messages_for_thread(env, thread_id: int, include_hidden: bool = False) -> list[dict]:
    hidden_clause = "" if include_hidden else "AND messages.is_hidden = 0"
    result = await db_run(
        env,
        f"""
        SELECT messages.*, users.display_name
        FROM messages
        JOIN users ON users.id = messages.sender_id
        WHERE messages.thread_id = ? {hidden_clause}
        ORDER BY messages.created_at
        LIMIT 100
        """,
        thread_id,
    )
    return rows_from(result)


async def verify_turnstile_for_request(env, request, body: dict, action: str) -> dict:
    token = turnstile_token_from_payload(body)
    verification_payload = siteverify_payload(
        secret=getattr(env, "WORKDOE_TURNSTILE_SECRET_KEY", ""),
        token=token,
        remoteip=remote_ip_from_headers(request.headers),
        idempotency_key=body.get("turnstile_idempotency_key", ""),
    )
    try:
        response = await fetch(
            TURNSTILE_VERIFY_URL,
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(verification_payload),
        )
        result = await response.json()
    except Exception as exc:
        raise TurnstileError("Turnstile verification failed.") from exc

    environment = str(getattr(env, "WORKDOE_ENV", "production") or "production").lower()
    metadata = row_value(result, "metadata", {}) or {}
    is_testing_result = environment != "production" and bool(
        row_value(metadata, "result_with_testing_key", False)
    )
    if is_testing_result and bool(row_value(result, "success", False)):
        return result
    allowed_hosts = {"workdoe.com", "www.workdoe.com"}
    if environment != "production":
        allowed_hosts.update({"localhost", "127.0.0.1", "0.0.0.0"})
    result_action = row_value(result, "action", "")
    action_allowed = result_action == action or (
        environment != "production" and result_action == "test"
    )
    if not turnstile_result_allowed(result, allowed_hosts) or not action_allowed:
        raise TurnstileError("Turnstile verification failed.")
    return result


async def process_email_queue_message(env, message, body: dict, queue_name: str) -> None:
    attempts = getattr(message, "attempts", 0)
    try:
        email_message = build_email_message(
            body,
            from_email=getattr(env, "WORKDOE_EMAIL_FROM", "no-reply@workdoe.com"),
            admin_email=getattr(env, "WORKDOE_ADMIN_EMAIL", ""),
        )
    except EmailPayloadError as exc:
        await record_event(
            env,
            "email-message-invalid",
            target_type=queue_name,
            payload={"body": body, "reason": str(exc), "attempts": attempts},
            status="failed",
        )
        ack_message(message)
        return

    if not hasattr(env, "EMAIL"):
        await record_event(
            env,
            "email-message-missing-binding",
            target_type=queue_name,
            payload={"body": body, "attempts": attempts},
            status="failed",
        )
        retry_message(message)
        return

    try:
        result = await env.EMAIL.send(email_message)
    except Exception as exc:
        await record_event(
            env,
            "email-message-send-failed",
            target_type=queue_name,
            payload={
                "type": body.get("type"),
                "to": email_message.get("to"),
                "reason": str(exc),
                "attempts": attempts,
            },
            status="failed",
        )
        retry_message(message)
        return

    await record_event(
        env,
        "email-message-sent",
        target_type=queue_name,
        payload={
            "type": body.get("type"),
            "to": email_message.get("to"),
            "subject": email_message.get("subject"),
            "result": email_send_result_summary(result),
            "attempts": attempts,
        },
        status="processed",
    )
    ack_message(message)


async def process_media_review_queue_message(env, message, body: dict, queue_name: str) -> None:
    attempts = getattr(message, "attempts", 0)
    try:
        payload = validated_media_review_payload(body)
    except (MediaUploadError, ValueError) as exc:
        await record_event(
            env,
            "media-review-message-invalid",
            target_type=queue_name,
            payload={"body": body, "reason": str(exc), "attempts": attempts},
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
            "stored_path": payload["stored_path"],
            "content_type": payload["content_type"],
            "size_bytes": payload["size_bytes"],
            "checks": payload["checks"],
            "attempts": attempts,
        },
        status="processed",
    )
    ack_message(message)
