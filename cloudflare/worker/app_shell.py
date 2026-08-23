from __future__ import annotations

import json
from html import escape
from urllib.parse import urlencode

from client_profiles import (
    CLIENT_ACCOUNT_TYPES,
    CLIENT_NOTIFICATION_OPTIONS,
    CLIENT_ORGANIZATION_MAX_LENGTH,
    CLIENT_PROFILE_NOTE_MAX_LENGTH,
    SAVED_LOCATION_CITY_MAX_LENGTH,
    SAVED_LOCATION_LABEL_MAX_LENGTH,
    SAVED_LOCATION_LIMIT,
)
from client_project_templates import (
    PROJECT_TEMPLATE_LIMIT,
    PROJECT_TEMPLATE_NAME_MAX_LENGTH,
)
from contractor_credentials import (
    CREDENTIAL_IDENTIFIER_MAX_LENGTH,
    CREDENTIAL_JURISDICTIONS,
    CREDENTIAL_NAME_MAX_LENGTH,
    CREDENTIAL_REVIEW_NOTE_MAX_LENGTH,
    CREDENTIAL_TYPES,
)
from contractor_preferences import AVAILABILITY_OPTIONS, LEAD_ALERT_OPTIONS
from contractor_profiles import contractor_profile_readiness
from entry_shell import (
    CLERK_CHALLENGE_ORIGIN,
    CLERK_IMAGE_ORIGIN,
    CLERK_PROTECT_ORIGIN,
    CLERK_TELEMETRY_ORIGINS,
    clerk_csp_origin,
    clerk_proxy_url,
    clerk_runtime_frontend_api_url,
)
from job_posts import (
    DMV_ZIPS,
    JOB_BUDGET_MAX,
    PROJECT_SETTINGS,
    job_field_errors,
)
from market_fit import (
    DMV_SERVICE_ZONES,
    infer_service_slugs_from_trades,
    infer_zone_slugs_from_area,
    normalize_service_slugs,
    normalize_zone_slugs,
)
from match_reviews import (
    REVIEW_COMMENT_MAX_LENGTH,
    REVIEW_DIMENSIONS,
    REVIEW_RATING_OPTIONS,
    REVIEW_REPORT_MAX_LENGTH,
    REVIEW_RESPONSE_MAX_LENGTH,
    WOULD_WORK_AGAIN_OPTIONS,
)
from service_activation import activation_is_live
from service_policy import SERVICE_POLICY_VERSION, service_policy
from service_scope import SERVICE_SCOPE_QUESTIONS
from service_taxonomy import (
    GROUP_BY_SLUG,
    SERVICE_GROUPS,
    service_icon,
    service_label,
    service_selection,
)

APP_SHELL_ROUTES = {
    "/dashboard",
    "/account",
    "/client/dashboard",
    "/client/requests",
    "/client/profile",
    "/contractor/dashboard",
    "/leads",
    "/jobs/new",
    "/contractor/profile",
    "/messages",
    "/admin",
}

PROJECT_CLOSE_REASONS = (
    {"value": "workdoe-match", "label": "Hired through Workdoe", "description": "A Workdoe contractor was selected for this project."},
    {"value": "hired-elsewhere", "label": "Hired elsewhere", "description": "The project moved forward outside Workdoe."},
    {"value": "plans-changed", "label": "Plans changed", "description": "The work is no longer moving forward right now."},
    {"value": "no-qualified-bid", "label": "No bid fit", "description": "The bids did not fit the scope, timing, or budget."},
    {"value": "scope-changed", "label": "Scope changed", "description": "The project needs to be rewritten or posted again."},
    {"value": "duplicate", "label": "Duplicate post", "description": "Another Workdoe post covers the same project."},
    {"value": "other", "label": "Other", "description": "Another reason best explains the close-out."},
)
LEAD_QUALITY_REASONS = (
    {"value": "insufficient-detail", "label": "Not enough detail"},
    {"value": "wrong-service", "label": "Wrong service"},
    {"value": "outside-service-area", "label": "Outside service area"},
    {"value": "client-unresponsive", "label": "No client response"},
    {"value": "already-hired", "label": "Already hired"},
    {"value": "duplicate", "label": "Duplicate lead"},
    {"value": "authorization-concern", "label": "Authorization concern"},
    {"value": "suspicious", "label": "Suspicious request"},
    {"value": "other", "label": "Other"},
)
PROJECT_CLOSE_REASON_LABELS = {
    option["value"]: option["label"] for option in PROJECT_CLOSE_REASONS
}
LEAD_QUALITY_REASON_LABELS = {
    option["value"]: option["label"] for option in LEAD_QUALITY_REASONS
}
OUTCOME_NOTE_MAX_LENGTH = 300


def project_close_reason_label(value: str | None) -> str:
    return PROJECT_CLOSE_REASON_LABELS.get(str(value or "").strip(), "Closed")


def lead_quality_reason_label(value: str | None) -> str:
    return LEAD_QUALITY_REASON_LABELS.get(str(value or "").strip(), "Lead feedback")


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def job_service_name(job) -> str:
    return str(
        row_value(job, "service_name", "")
        or service_label(
            row_value(job, "service_slug", ""),
            str(row_value(job, "category", "") or ""),
        )
    )


def dom_id_fragment(value: str) -> str:
    normalized = "".join(
        character.lower() if character.isalnum() else "-"
        for character in str(value)
    )
    return "-".join(part for part in normalized.split("-") if part) or "action"


def match_review_form_html(request_id: int, reviewer_role: str, success_url: str) -> str:
    dimension_fields = "".join(
        f"""
        <label for="review-{request_id}-{escape(reviewer_role)}-{escape(key)}">{escape(label)}
          <select id="review-{request_id}-{escape(reviewer_role)}-{escape(key)}" name="{escape(key)}" required>
            <option value="">Choose one</option>
            {''.join(f'<option value="{escape(value)}">{escape(option_label)}</option>' for value, option_label in REVIEW_RATING_OPTIONS)}
          </select>
        </label>"""
        for key, label in REVIEW_DIMENSIONS
    )
    again_options = "".join(
        f'<option value="{escape(value)}">{escape(label)}</option>'
        for value, label in WOULD_WORK_AGAIN_OPTIONS
    )
    return f"""
      <details class="review-composer">
        <summary>Leave completed-work feedback</summary>
        <form class="review-form" data-json-action="/api/match-requests/{request_id}/review" data-success-url-template="{escape(success_url)}" aria-label="Leave completed-work feedback" aria-describedby="match-review-{request_id}-{escape(reviewer_role)}-status">
          <div class="review-field-grid">{dimension_fields}
            <label for="review-{request_id}-{escape(reviewer_role)}-again">Work together again?
              <select id="review-{request_id}-{escape(reviewer_role)}-again" name="would_work_again" required><option value="">Choose one</option>{again_options}</select>
            </label>
          </div>
          <label for="review-{request_id}-{escape(reviewer_role)}-comment">What should the other participant know? <span class="optional-label">Optional</span>
            <textarea id="review-{request_id}-{escape(reviewer_role)}-comment" name="comment" maxlength="{REVIEW_COMMENT_MAX_LENGTH}" rows="3" autocapitalize="sentences" spellcheck="true"></textarea>
          </label>
          <p class="help-text">Based on a Workdoe-verified completion. Feedback does not create a star score or change marketplace rank.</p>
          <button class="button compact" type="submit">Submit feedback</button>
          <p id="match-review-{request_id}-{escape(reviewer_role)}-status" class="help-text" data-form-status aria-live="polite"></p>
        </form>
      </details>"""


def match_review_card_html(review: dict, user, success_url: str) -> str:
    review_id = int(review.get("id", 0) or 0)
    user_id = int(row_value(user, "id", 0) or 0)
    reviewer_id = int(review.get("reviewer_id", 0) or 0)
    subject_id = int(review.get("subject_id", 0) or 0)
    reviewer_label = (
        "Consumer feedback" if review.get("reviewer_role") == "client" else "Contractor feedback"
    )
    if review.get("is_hidden"):
        return f"""
      <article class="match-review is-hidden" aria-label="Completed-work feedback">
        <div class="section-heading review-heading"><div><span class="completion-chip verified">Workdoe-completed</span><strong>{reviewer_label}</strong></div></div>
        <p class="empty">This feedback is hidden while moderation reviews it.</p>
      </article>"""
    dimensions = "".join(
        f'<div><dt>{escape(label)}</dt><dd class="review-result {escape(review.get(key, ""))}">{escape(review.get(key + "_label", "Feedback"))}</dd></div>'
        for key, label in REVIEW_DIMENSIONS
    )
    response_html = ""
    if review.get("response"):
        response_html = f'<blockquote class="review-response"><strong>Response</strong><p>{escape(review.get("response", ""))}</p></blockquote>'
    elif user_id == subject_id:
        response_html = f"""
        <details class="review-response-form"><summary>Respond</summary>
          <form data-json-action="/api/reviews/{review_id}/response" data-success-url-template="{escape(success_url)}" aria-describedby="review-response-{review_id}-status">
            <label for="review-response-{review_id}">Response <textarea id="review-response-{review_id}" name="response" maxlength="{REVIEW_RESPONSE_MAX_LENGTH}" rows="3" required autocapitalize="sentences" spellcheck="true"></textarea></label>
            <button class="button secondary compact" type="submit">Post response</button><p id="review-response-{review_id}-status" class="help-text" data-form-status aria-live="polite"></p>
          </form>
        </details>"""
    report_html = ""
    if user_id in {reviewer_id, subject_id}:
        report_html = f"""
        <details class="review-report-form"><summary>Report feedback</summary>
          <form data-json-action="/api/reviews/{review_id}/report" data-success-url-template="{escape(success_url)}" aria-describedby="review-report-{review_id}-status">
            <label for="review-report-{review_id}">Reason <input id="review-report-{review_id}" name="reason" maxlength="{REVIEW_REPORT_MAX_LENGTH}" required autocapitalize="sentences" spellcheck="true"></label>
            <button class="button secondary compact" type="submit">Send report</button><p id="review-report-{review_id}-status" class="help-text" data-form-status aria-live="polite"></p>
          </form>
        </details>"""
    return f"""
      <article class="match-review" aria-label="Completed-work feedback">
        <div class="section-heading review-heading"><div><span class="completion-chip verified">Workdoe-completed</span><strong>{reviewer_label}</strong></div><time datetime="{escape(review.get('created_at', ''))}">{escape(str(review.get('created_at', ''))[:10])}</time></div>
        <dl class="review-dimensions">{dimensions}<div><dt>Work together again</dt><dd>{escape(review.get('would_work_again_label', 'Not stated'))}</dd></div></dl>
        {('<p class="preline review-comment">' + escape(review.get('comment', '')) + '</p>') if review.get('comment') else ''}
        {response_html}{report_html}
      </article>"""


def is_app_shell_route(path: str) -> bool:
    if path in APP_SHELL_ROUTES:
        return True
    if path.startswith("/client/jobs/"):
        raw = path.removeprefix("/client/jobs/").strip("/")
        if raw.endswith("/edit"):
            raw = raw.removesuffix("/edit").strip("/")
        return raw.isdigit() and int(raw) > 0
    if path.startswith("/messages/"):
        raw = path.removeprefix("/messages/").strip("/")
        return raw.isdigit() and int(raw) > 0
    if path.startswith("/jobs/"):
        raw = path.removeprefix("/jobs/").strip("/")
        return raw.isdigit() and int(raw) > 0
    return False


def app_login_url(path: str) -> str:
    return "/login?" + urlencode({"next": path}, safe="/")


def dashboard_path_for_user(user) -> str:
    role = row_value(user, "role")
    if role == "client":
        return "/client/dashboard"
    if role == "contractor":
        return "/contractor/dashboard"
    if role == "admin":
        return "/admin"
    return "/create-account"


def parse_app_job_id(path: str) -> int:
    raw = path.removeprefix("/jobs/").strip("/")
    return int(raw) if raw.isdigit() and int(raw) > 0 else 0


def parse_app_client_job_id(path: str) -> int:
    raw = path.removeprefix("/client/jobs/").strip("/")
    return int(raw) if raw.isdigit() and int(raw) > 0 else 0


def parse_app_client_job_edit_id(path: str) -> int:
    raw = path.removeprefix("/client/jobs/").strip("/")
    if not raw.endswith("/edit"):
        return 0
    raw = raw.removesuffix("/edit").strip("/")
    return int(raw) if raw.isdigit() and int(raw) > 0 else 0


def is_public_contractor_profile_route(path: str) -> bool:
    if not path.startswith("/contractors/"):
        return False
    raw = path.removeprefix("/contractors/").strip("/")
    return raw.isdigit() and int(raw) > 0


def parse_app_contractor_id(path: str) -> int:
    raw = path.removeprefix("/contractors/").strip("/")
    return int(raw) if raw.isdigit() and int(raw) > 0 else 0


def parse_app_thread_id(path: str) -> int:
    raw = path.removeprefix("/messages/").strip("/")
    return int(raw) if raw.isdigit() and int(raw) > 0 else 0


def app_shell_csp(
    include_map: bool = False,
    include_turnstile: bool = False,
    include_clerk: bool = False,
    clerk_publishable_key: str = "",
    clerk_frontend_api_url: str = "",
) -> str:
    script_sources = ["'self'"]
    frame_sources = []
    connect_sources = ["'self'"]
    style_sources = ["'self'"]
    style_element_sources = ["'self'"]
    worker_sources = ["'none'"]
    if include_turnstile:
        script_sources.append("https://challenges.cloudflare.com")
        frame_sources.append("https://challenges.cloudflare.com")
        connect_sources.append("https://challenges.cloudflare.com")
    img_sources = ["'self'", "data:"]
    if include_map:
        img_sources.append("https://tile.openstreetmap.org")
    if include_clerk:
        runtime_url = clerk_runtime_frontend_api_url(
            clerk_publishable_key,
            clerk_frontend_api_url,
        )
        clerk_origin = clerk_csp_origin(runtime_url)
        for source in (
            clerk_origin,
            CLERK_CHALLENGE_ORIGIN,
            CLERK_PROTECT_ORIGIN,
        ):
            if source and source not in script_sources:
                script_sources.append(source)
            if source and source not in frame_sources:
                frame_sources.append(source)
        for source in (
            clerk_origin,
            CLERK_CHALLENGE_ORIGIN,
            CLERK_PROTECT_ORIGIN,
            CLERK_IMAGE_ORIGIN,
            *CLERK_TELEMETRY_ORIGINS,
        ):
            if source and source not in connect_sources:
                connect_sources.append(source)
        for source in (clerk_origin, CLERK_IMAGE_ORIGIN):
            if source and source not in img_sources:
                img_sources.append(source)
        style_sources.append("'unsafe-inline'")
        style_element_sources.append("'unsafe-inline'")
        if clerk_origin and clerk_origin not in style_element_sources:
            style_element_sources.append(clerk_origin)
        worker_sources = ["'self'", "blob:"]
    directives = [
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "script-src " + " ".join(script_sources),
        "style-src " + " ".join(style_sources),
        "style-src-elem " + " ".join(style_element_sources),
        "style-src-attr 'unsafe-inline'",
        "img-src " + " ".join(img_sources),
        "connect-src " + " ".join(connect_sources),
        "font-src 'self'",
        "media-src 'self'",
        "worker-src " + " ".join(worker_sources),
        "manifest-src 'self'",
    ]
    if frame_sources:
        directives.append("frame-src " + " ".join(frame_sources))
    return "; ".join(directives)


def app_shell_headers(
    include_map: bool = False,
    include_turnstile: bool = False,
    include_clerk: bool = False,
    clerk_publishable_key: str = "",
    clerk_frontend_api_url: str = "",
) -> dict[str, str]:
    return {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Expires": "0",
        "Content-Security-Policy": app_shell_csp(
            include_map=include_map,
            include_turnstile=include_turnstile,
            include_clerk=include_clerk,
            clerk_publishable_key=clerk_publishable_key,
            clerk_frontend_api_url=clerk_frontend_api_url,
        ),
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    }


def safe_json_script(value) -> str:
    return (
        json.dumps(value, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def photo_count_label(value) -> str:
    try:
        count = int(value or 0)
    except (TypeError, ValueError):
        count = 0
    return f"{count} {'photo' if count == 1 else 'photos'}"


def message_count_label(value) -> str:
    try:
        count = int(value or 0)
    except (TypeError, ValueError):
        count = 0
    return f"{count} {'message' if count == 1 else 'messages'}"


def dmv_city_options_html() -> str:
    options = sorted({(city, state) for city, state, *_coords in DMV_ZIPS.values()})
    return "\n".join(
        f'<option value="{escape(city)}" label="{escape(city)}, {escape(state)}"></option>'
        for city, state in options
    )


def dmv_zip_options_html() -> str:
    return "\n".join(
        f'<option value="{escape(zip_code)}" label="{escape(city)}, {escape(state)}"></option>'
        for zip_code, (city, state, *_coords) in sorted(DMV_ZIPS.items())
    )


def nav_path_is_current(href: str, active_path: str, role: str = "") -> bool:
    if href == "/":
        return active_path == "/"
    if href == "/leads":
        return active_path == "/leads" or active_path.startswith("/jobs/")
    if href == "/client/dashboard":
        return active_path.startswith("/client/") and active_path != "/client/profile"
    if href == "/contractor/dashboard":
        return active_path == "/contractor/dashboard"
    if href == "/messages":
        return active_path == "/messages" or active_path.startswith("/messages/")
    if href == "/client/profile":
        return active_path == "/client/profile"
    if href == "/contractor/profile":
        return active_path.startswith("/contractor/profile")
    if href == "/jobs/new":
        return active_path == "/jobs/new"
    if href == "/post-project":
        return active_path == "/post-project"
    if role == "admin" and href == "/admin":
        return active_path.startswith("/admin")
    return href == active_path


def task_nav_items(user) -> list[tuple[str, str, str]]:
    role = str(row_value(user, "role", "") or "")
    if role == "client":
        return [
            ("/", "Explore", "layout-board-split.svg"),
            ("/jobs/new", "Post project", "home-up.svg"),
            ("/messages", "Messages", "dots.svg"),
            ("/client/dashboard", "Profile", "home-check.svg"),
        ]
    if role == "contractor":
        return [
            ("/leads", "Explore", "layout-board-split.svg"),
            ("/contractor/dashboard", "Bids", "tool.svg"),
            ("/messages", "Messages", "dots.svg"),
            ("/contractor/profile", "Profile", "home-check.svg"),
        ]
    if role == "admin":
        return [
            ("/", "Explore", "layout-board-split.svg"),
            ("/admin", "Admin", "lock.svg"),
            ("/account", "Account", "home-check.svg"),
        ]
    return [
        ("/", "Explore", "layout-board-split.svg"),
        ("/post-project", "Post project", "home-up.svg"),
        ("/login", "Sign in", "lock.svg"),
        ("/create-account", "Create account", "sparkles.svg"),
    ]


def account_menu_html(user, active_path: str) -> str:
    role = str(row_value(user, "role", "") or "")
    if role not in {"client", "contractor", "admin"}:
        return ""
    edit_profile = (
        '<a href="/client/profile">Edit profile</a>' if role == "client" else ""
    )
    return f"""<details class="account-menu">
        <summary aria-label="Account menu" title="Account menu"><img src="/vendor/tabler-icons/dots.svg" alt="" width="22" height="22"></summary>
        <div class="account-menu-panel">
          <a href="/safety"{" aria-current=\"page\"" if active_path == "/safety" else ""}>Safety</a>
          {edit_profile}
          <a href="/account"{" aria-current=\"page\"" if active_path == "/account" else ""}>Account settings</a>
          <form class="nav-action-form" data-json-action="/api/auth/logout" data-success-url-template="/" aria-label="Sign out">
            <button class="nav-link-button" type="submit">Sign out</button>
            <span class="sr-only" data-form-status aria-live="polite"></span>
          </form>
        </div>
      </details>"""


def nav_links(user, active_path: str) -> str:
    role = str(row_value(user, "role", "") or "")
    unread_count = int(row_value(user, "unread_message_count", 0) or 0)
    rendered = []
    for href, label, _icon in task_nav_items(user):
        current = (
            ' aria-current="page"'
            if nav_path_is_current(href, active_path, role)
            else ""
        )
        if href == "/messages":
            accessibility_label = (
                f' aria-label="Messages, {unread_count} unread"'
                if unread_count
                else ""
            )
            badge = (
                f'<span class="nav-unread-count" aria-hidden="true">{escape(unread_count_label(unread_count))}</span>'
                if unread_count
                else ""
            )
            rendered.append(
                f'<a class="nav-message-link" href="{escape(href)}"{current}{accessibility_label}>{escape(label)}{badge}</a>'
            )
        else:
            rendered.append(f'<a href="{escape(href)}"{current}>{escape(label)}</a>')
    menu = account_menu_html(user, active_path)
    if menu:
        rendered.append(menu)
    return "\n".join(rendered)


def mobile_task_nav_html(user, active_path: str) -> str:
    role = str(row_value(user, "role", "") or "")
    unread_count = int(row_value(user, "unread_message_count", 0) or 0)
    items = []
    for href, label, icon in task_nav_items(user):
        mobile_label = {"Post project": "Post", "Create account": "Join"}.get(
            label, label
        )
        current = (
            ' aria-current="page"'
            if nav_path_is_current(href, active_path, role)
            else ""
        )
        if href == "/messages":
            accessibility_label = (
                f' aria-label="Messages, {unread_count} unread"'
                if unread_count
                else ""
            )
            badge = (
                f'<span class="nav-unread-count" aria-hidden="true">{escape(unread_count_label(unread_count))}</span>'
                if unread_count
                else ""
            )
            items.append(
                f'<a class="nav-message-link" href="{escape(href)}"{current}{accessibility_label}><span class="mobile-nav-icon"><img src="/vendor/tabler-icons/{escape(icon)}" alt="">{badge}</span><span>{escape(mobile_label)}</span></a>'
            )
        else:
            items.append(
                f'<a href="{escape(href)}"{current}><img src="/vendor/tabler-icons/{escape(icon)}" alt=""><span>{escape(mobile_label)}</span></a>'
            )
    return '<nav class="mobile-task-nav" aria-label="Primary tasks">' + "".join(items) + "</nav>"


def unread_count_label(unread_count: int) -> str:
    return "99+" if unread_count > 99 else str(unread_count)


def site_dialog_html() -> str:
    return """
  <dialog class="site-dialog" data-site-dialog aria-labelledby="site-dialog-title">
    <section class="site-dialog-surface">
      <header class="site-dialog-header">
        <div><p class="eyebrow">Workdoe</p><h2 id="site-dialog-title" data-site-dialog-title>Continue</h2></div>
        <button class="icon-button" type="button" data-site-dialog-close aria-label="Close dialog" title="Close"><img src="/vendor/tabler-icons/x.svg" alt="" width="20" height="20"></button>
      </header>
      <div class="site-dialog-status" data-site-dialog-status role="status" aria-live="polite">Loading...</div>
      <div class="site-dialog-content" data-site-dialog-content></div>
    </section>
  </dialog>"""


def layout(
    user,
    active_path: str,
    title: str,
    body: str,
    *,
    include_map: bool = False,
    include_actions: bool = False,
    include_turnstile: bool = False,
    include_project_composer: bool = False,
    include_clerk: bool = False,
    clerk_publishable_key: str = "",
    clerk_frontend_api_url: str = "",
    body_class: str = "",
    main_class: str = "",
) -> str:
    scripts = []
    embedded = "dialog-fragment-body" in body_class.split()
    authenticated = row_value(user, "role") in {"client", "contractor", "admin"}
    if include_turnstile:
        scripts.append('<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>')
    if include_map:
        scripts.extend(
            [
                '<script src="/vendor/leaflet/leaflet.js"></script>',
                '<script src="/vendor/leaflet-markercluster/leaflet.markercluster.js"></script>',
                '<script src="/map.js"></script>',
            ]
        )
    if include_actions or authenticated:
        scripts.append('<script defer src="/worker-actions.js"></script>')
    if include_project_composer:
        scripts.append('<script defer src="/project-composer.js?v=workdoe-service-tiles"></script>')
    if include_clerk:
        clerk_asset_base_url = clerk_runtime_frontend_api_url(
            clerk_publishable_key,
            clerk_frontend_api_url,
        )
        proxy_url = (
            ""
            if clerk_asset_base_url.endswith(".clerk.accounts.dev")
            else clerk_proxy_url(clerk_frontend_api_url)
        )
        proxy_attribute = (
            f' data-clerk-proxy-url="{escape(proxy_url)}"' if proxy_url else ""
        )
        scripts.extend(
            [
                f'<script defer crossorigin="anonymous" src="{escape(clerk_asset_base_url)}/npm/@clerk/ui@1/dist/ui.browser.js"></script>',
                f'<script defer crossorigin="anonymous" data-clerk-publishable-key="{escape(clerk_publishable_key)}"{proxy_attribute} src="{escape(clerk_asset_base_url)}/npm/@clerk/clerk-js@6/dist/clerk.browser.js"></script>',
                '<script defer src="/clerk-account.js"></script>',
            ]
        )
    if not embedded:
        scripts.append('<script defer src="/site-dialogs.js?v=workdoe-bid-dialog"></script>')
    script_html = "\n  ".join(scripts)
    dialog_html = "" if embedded else site_dialog_html()
    mobile_nav_html = "" if embedded else mobile_task_nav_html(user, active_path)
    canonical_path = active_path if active_path in {"/safety", "/privacy", "/terms"} else "/"
    canonical_url = f"https://workdoe.com{canonical_path}"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="description" content="Post a local project or find nearby contractor work across DC, Maryland, and Virginia.">
  <meta name="theme-color" content="#1b2b22">
  <meta name="application-name" content="Workdoe">
  <meta name="mobile-web-app-capable" content="yes">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Workdoe">
  <meta property="og:locale" content="en_US">
  <meta property="og:url" content="https://workdoe.com/">
  <meta property="og:title" content="Workdoe - a local Work Exchange">
  <meta property="og:description" content="Find nearby projects and trusted local contractors across DC, Maryland, and Virginia.">
  <meta property="og:image" content="https://workdoe.com/workdoe-share.png">
  <meta property="og:image:secure_url" content="https://workdoe.com/workdoe-share.png">
  <meta property="og:image:type" content="image/png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="Workdoe deer logo with the slogan a local Work Exchange">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="Workdoe - a local Work Exchange">
  <meta name="twitter:description" content="Find nearby projects and trusted local contractors across DC, Maryland, and Virginia.">
  <meta name="twitter:image" content="https://workdoe.com/workdoe-share.png">
  <meta name="twitter:image:alt" content="Workdoe deer logo with the slogan a local Work Exchange">
  <title>{escape(title)} - Workdoe</title>
  <link rel="canonical" href="{escape(canonical_url)}">
  <link rel="icon" href="/deer.svg" type="image/svg+xml">
  <link rel="manifest" href="/site.webmanifest">
  <link rel="stylesheet" href="/styles.css?v=workdoe-bid-dialog">
  {"<link rel=\"stylesheet\" href=\"/vendor/leaflet/leaflet.css\">" if include_map else ""}
  {"<link rel=\"stylesheet\" href=\"/vendor/leaflet-markercluster/MarkerCluster.css\"><link rel=\"stylesheet\" href=\"/vendor/leaflet-markercluster/MarkerCluster.Default.css\">" if include_map else ""}
  {script_html}
</head>
<body{f' class="{escape(body_class)}"' if body_class else ''}>
  <a class="skip-link" href="#main-content">Skip to content</a>
  <header class="site-header">
    <a class="brand brand-home-button" href="/" aria-label="Workdoe home">
      <span class="brand-mark"><img class="brand-icon" src="/deer.svg" alt=""></span>
      <span><strong>Workdoe</strong><small>Local work exchange</small></span>
    </a>
    <nav class="main-nav" aria-label="Primary">
      {nav_links(user, active_path)}
    </nav>
  </header>
  <main id="main-content"{f' class="{escape(main_class)}"' if main_class else ''} tabindex="-1">
{body}
  </main>
  <footer class="site-footer">
    <span>workdoe.com</span>
    <nav class="site-footer-links" aria-label="Policies">
      <a href="/safety"{" aria-current=\"page\"" if active_path == "/safety" else ""}>Safety</a>
      <a href="/privacy"{" aria-current=\"page\"" if active_path == "/privacy" else ""}>Privacy</a>
      <a href="/terms"{" aria-current=\"page\"" if active_path == "/terms" else ""}>Terms</a>
    </nav>
    <span>Serving DC, Maryland &amp; Virginia</span>
  </footer>
  {mobile_nav_html}
{dialog_html}
</body>
</html>
"""


def account_security_html(
    user,
    clerk_publishable_key: str = "",
    clerk_frontend_api_url: str = "",
    auth_provider: str = "clerk",
) -> str:
    role = str(row_value(user, "role", "") or "")
    profile_url = {
        "client": "/client/profile",
        "contractor": "/contractor/profile",
        "admin": "/admin",
    }.get(role, "/dashboard")
    clerk_enabled = bool(
        auth_provider == "clerk"
        and str(clerk_publishable_key or "").strip()
        and str(clerk_frontend_api_url or "").strip()
    )
    if clerk_enabled:
        proxy_url = clerk_proxy_url(clerk_frontend_api_url)
        proxy_attribute = (
            f' data-clerk-proxy-url="{escape(proxy_url)}"' if proxy_url else ""
        )
        security_html = f"""
      <div id="clerk-account" class="clerk-account-mount" data-clerk-account{proxy_attribute}>
        <p class="help-text" data-clerk-account-status role="status" aria-live="polite">Loading account settings...</p>
      </div>"""
    else:
        security_html = f"""
      <div class="panel account-signin-summary">
        <strong>Your email sign-in is active</strong>
        <p>Workdoe sends a one-time code to {escape(row_value(user, 'email', 'your email'))}. There is no password to remember.</p>
      </div>"""
    body = f"""
    <section class="dashboard-header account-heading">
      <div>
        <p class="eyebrow">Account</p>
        <h1>Account &amp; security</h1>
        <p>Manage how you sign in without leaving Workdoe.</p>
      </div>
      <a class="button secondary" href="{escape(profile_url)}">Workdoe profile</a>
    </section>
    <section class="account-layout">
      <aside class="panel account-summary" aria-labelledby="account-summary-title">
        <h2 id="account-summary-title">Workdoe identity</h2>
        <dl class="profile-facts compact-facts">
          <div><dt>Email</dt><dd>{escape(row_value(user, 'email', ''))}</dd></div>
          <div><dt>Role</dt><dd>{escape(role.capitalize())}</dd></div>
        </dl>
        <p class="help-text">One account keeps one role during the DMV beta.</p>
      </aside>
      <section class="account-security-surface" aria-labelledby="account-security-title">
        <header class="panel-heading">
          <div><p class="eyebrow">Sign-in</p><h2 id="account-security-title">Security settings</h2></div>
        </header>
{security_html}
      </section>
    </section>"""
    return layout(
        user,
        "/account",
        "Account & security",
        body,
        include_clerk=clerk_enabled,
        clerk_publishable_key=clerk_publishable_key,
        clerk_frontend_api_url=clerk_frontend_api_url,
    )


def empty_state(title: str, href: str, label: str) -> str:
    return f"""
    <div class="empty-state field-empty-state">
      <img class="empty-state-visual" src="/field-doe.webp" alt="" width="180" height="180">
      <h2>{escape(title)}</h2>
      <a class="button secondary" href="{escape(href)}">{escape(label)}</a>
    </div>"""


def bid_window_html(window: dict | None, *, owner: bool = False, job_id: int = 0) -> str:
    bidding = window or {}
    if not bidding:
        return ""
    state = escape(bidding.get("state", "open"))
    extension = ""
    if owner and bidding.get("can_extend") and job_id:
        extension = f"""
      <form data-json-action="/api/jobs/{int(job_id)}/extend-bids" data-success-url-template="/client/jobs/{int(job_id)}" aria-label="Extend bidding by seven days" aria-describedby="extend-bids-status">
        <button class="button secondary compact" type="submit">Add 7 days</button>
        <p id="extend-bids-status" class="help-text" data-form-status aria-live="polite"></p>
      </form>"""
    return f"""
    <section class="bid-window bid-window-{state}" aria-label="Bid availability">
      <div><span class="bid-window-kicker">Fair bid window</span><strong>{escape(bidding.get('availability_label', ''))}</strong></div>
      <div class="bid-window-status"><span>{escape(bidding.get('usage_label', ''))}</span><span>{'Closed' if bidding.get('is_expired') else 'Closes'} {escape(bidding.get('deadline_label', ''))}</span></div>
      <progress value="{int(bidding.get('used', 0) or 0)}" max="{int(bidding.get('limit', 4) or 4)}">{escape(bidding.get('usage_label', ''))}</progress>
      {extension}
    </section>"""


def client_dashboard_html(user, payload: dict) -> str:
    jobs = payload.get("jobs", [])
    history = payload.get("history", [])
    stats = payload.get("stats", {})
    job_view = payload.get("view", "all")
    view_links = payload.get("view_links") or [
        {"value": "all", "label": "All", "url": "/client/dashboard"},
        {
            "value": "review",
            "label": "Review",
            "url": "/client/dashboard?view=review",
        },
        {"value": "open", "label": "Open", "url": "/client/dashboard?view=open"},
        {
            "value": "closed",
            "label": "Closed",
            "url": "/client/dashboard?view=closed",
        },
    ]
    view_counts = {
        "all": int(stats.get("total_jobs", 0) or 0),
        "review": int(stats.get("review_jobs", 0) or 0),
        "open": int(stats.get("open_jobs", 0) or 0),
        "closed": int(stats.get("closed_jobs", 0) or 0),
    }
    view_tabs_html = "".join(
        (
            f'<a class="work-view-tab{" is-active" if job_view == item.get("value") else ""}" '
            f'href="{escape(item.get("url", "/client/dashboard"))}"'
            f'{" aria-current=\"page\"" if job_view == item.get("value") else ""}>'
            f'<span>{escape(item.get("label", "All"))}</span>'
            f'<strong>{view_counts.get(item.get("value"), 0)}</strong></a>'
        )
        for item in view_links
    )
    rows = []
    for job in jobs:
        row_label = (
            f"Review pending bids for {job.get('title', 'job')}"
            if job.get("needs_review")
            else f"Review {job.get('title', 'job')}"
        )
        rows.append(
            f"""
    <a class="job-row link-row{' needs-review' if job.get('needs_review') else ''}" href="{escape(job.get('url', '#'))}" aria-label="{escape(row_label)}">
      <div>
        <div class="row-meta">
          <span class="status {escape(job.get('status', ''))}">{escape(job.get('status', ''))}</span>
          <span>{escape(job_service_name(job))}</span>
          <span>{escape(job.get('city', ''))}, {escape(job.get('state', ''))}</span>
          {brief_readiness_pill_html(job.get('brief_readiness'))}
          <span class="bid-availability {escape(job.get('bid_window', {}).get('state', 'open'))}">{escape(job.get('bid_window', {}).get('usage_label', ''))} - {escape(job.get('bid_window', {}).get('availability_label', ''))}</span>
        </div>
        <h2>{escape(job.get('title', ''))}</h2>
        <p class="job-summary">{escape(job.get('description', ''))}</p>
      </div>
      <div class="row-actions">
        {'<span class="count-pill attention">' + str(job.get('pending_count', 0)) + ' pending</span>' if job.get('needs_review') else ''}
        <span class="row-cue">{escape(job.get('row_cue', 'Review'))}</span>
      </div>
    </a>"""
        )
    empty_titles = {
        "review": "No bids to review",
        "open": "No open projects",
        "closed": "No closed projects",
    }
    job_html = "\n".join(rows) if rows else empty_state(
        empty_titles.get(job_view, "No projects yet"),
        "/client/dashboard" if job_view != "all" else "/jobs/new",
        "All projects" if job_view != "all" else "Post a project",
    )
    history_rows = []
    for job in history:
        completion_chip = ""
        if int(job.get("verified_completion_count", 0) or 0):
            completion_chip = '<span class="completion-chip verified">Verified complete</span>'
        elif int(job.get("approved_count", 0) or 0):
            completion_chip = '<span class="completion-chip awaiting">Completion pending</span>'
        invite_action = ""
        if job.get("repeat_invite_url"):
            invite_action = (
                f'<a class="button compact" href="{escape(job.get("repeat_invite_url", ""))}" '
                f'data-dialog-title="Invite {escape(job.get("repeat_contractor_name", "contractor"))} again">Invite again</a>'
            )
        history_rows.append(
            f"""
      <div class="history-row repeat-history-row">
        <div>
          <div class="row-meta"><span>{escape(job_service_name(job))}</span><span>{escape(job.get('city', ''))}, {escape(job.get('state', ''))}</span>{brief_readiness_pill_html(job.get('brief_readiness'))}</div>
          <h3>{escape(job.get('title', ''))}</h3>
          <p>{escape(job.get('description', ''))}</p>
          {('<span class="outcome-chip">' + escape(job.get('close_reason_label', 'Closed')) + '</span>') if job.get('close_reason') else ''}
          {completion_chip}
        </div>
        <div class="history-row-actions">
          <a class="button secondary compact" href="{escape(job.get('detail_url', '#'))}">Review</a>
          <a class="button secondary compact" href="/client/profile?source_job={int(job.get('id', 0) or 0)}#project-templates">Save template</a>
          {invite_action}
          <a class="button compact" href="{escape(job.get('repeat_url', '/jobs/new'))}" data-dialog-title="Post this project again">Post again</a>
        </div>
      </div>"""
        )
    history_html = "\n".join(history_rows) if history_rows else '<p class="empty history-empty">Closed projects will collect here as your private work history.</p>'
    body = f"""
    <section class="dashboard-header">
      <div>
        <p class="eyebrow">Consumer workspace</p>
        <h1>Your projects</h1>
      </div>
      <a class="button" href="/jobs/new">Post a project</a>
    </section>
    <nav class="work-view-tabs client-job-tabs" aria-label="Client job status">{view_tabs_html}</nav>
    <section class="job-list" aria-label="Client jobs">
{job_html}
    </section>
    <section class="work-history" aria-labelledby="consumer-history-title">
      <div class="section-heading history-heading"><div><p class="eyebrow">Project history</p><h2 id="consumer-history-title">Previous work</h2></div><span class="count-pill">{len(history)} closed</span></div>
      <div class="history-list">
{history_html}
      </div>
    </section>"""
    return layout(user, "/client/dashboard", "Projects", body)


def client_profile_html(
    user,
    profile: dict,
    locations: list[dict],
    templates: list[dict] | None = None,
    source_jobs: list[dict] | None = None,
    selected_source_job_id: int = 0,
) -> str:
    account_choices = "".join(
        f'<label><input type="radio" name="account_type" value="{escape(value)}"{' checked' if profile.get("account_type") == value else ''} required><span>{escape(label)}</span></label>'
        for value, label in CLIENT_ACCOUNT_TYPES
    )
    notification_choices = "".join(
        f'<label><input type="radio" name="notification_preference" value="{escape(value)}"{' checked' if profile.get("notification_preference") == value else ''} required><span>{escape(label)}</span></label>'
        for value, label in CLIENT_NOTIFICATION_OPTIONS
    )
    location_rows = []
    for location in locations:
        location_id = int(location.get("id", 0) or 0)
        zip_prefix = str(location.get("zip_code", ""))[:3]
        location_rows.append(
            f"""
        <article class="saved-location-row">
          <div><strong>{escape(location.get('label', ''))}</strong><span>{escape(location.get('city', ''))}, {escape(location.get('state', ''))} {escape(zip_prefix)}xx</span></div>
          <div class="saved-location-actions">
            <a class="button compact" href="/jobs/new?{urlencode({'location': location_id})}" data-dialog-title="Post a project at {escape(location.get('label', ''))}">Post here</a>
            <form data-json-action="/api/client/locations/{location_id}/delete" data-success-url-template="/client/profile#saved-project-areas" aria-label="Remove {escape(location.get('label', ''))}"><button class="button secondary compact" type="submit">Remove</button><span class="sr-only" data-form-status aria-live="polite"></span></form>
          </div>
        </article>"""
        )
    locations_html = "\n".join(location_rows) if location_rows else '<p class="empty history-empty">Saved project areas will appear here for one-click location setup.</p>'
    template_rows = []
    for template in templates or []:
        template_id = int(template.get("id", 0) or 0)
        template_rows.append(
            f"""
        <article class="project-template-row">
          <div><strong>{escape(template.get('name', ''))}</strong><span>{escape(template.get('category', 'Other'))} - {escape(template.get('title', ''))}</span></div>
          <div class="saved-location-actions">
            <a class="button compact" href="{escape(template.get('use_url', '/jobs/new'))}" data-dialog-title="Post from {escape(template.get('name', 'template'))}">Use template</a>
            <form data-json-action="/api/client/templates/{template_id}/delete" data-success-url-template="/client/profile#project-templates" aria-label="Remove {escape(template.get('name', 'project template'))}"><button class="button secondary compact" type="submit">Remove</button><span class="sr-only" data-form-status aria-live="polite"></span></form>
          </div>
        </article>"""
        )
    templates_html = "\n".join(template_rows) if template_rows else '<p class="empty history-empty">Reusable project scopes will appear here.</p>'
    source_options = ['<option value="">Choose one of your projects</option>']
    source_options.extend(
        f'<option value="{int(job.get("id", 0) or 0)}"{" selected" if int(job.get("id", 0) or 0) == selected_source_job_id else ""}>{escape(job.get("title", ""))} - {escape(job.get("status", ""))}</option>'
        for job in source_jobs or []
    )
    # Bandit B608 mistakes this HTML template for a SQL statement.
    body = f"""
    <section class="dashboard-header compact-dashboard-header">
      <div><p class="eyebrow">Consumer workspace</p><h1>Your profile</h1><p>Keep recurring project details private and ready for the next post.</p></div>
      <a class="button secondary" href="/client/dashboard">Projects</a>
    </section>
    <section class="consumer-profile-layout" aria-label="Consumer profile workspace">
      <section class="profile-tool" aria-labelledby="workspace-details-title">
        <div class="section-heading"><div><p class="eyebrow">Account</p><h2 id="workspace-details-title">Workspace details</h2></div><span class="privacy-label">Private</span></div>
        <form class="form-grid consumer-profile-form" data-json-action="/api/client/profile" data-success-url-template="/client/profile" aria-label="Consumer profile" aria-describedby="client-profile-status">
          <label class="wide" for="client-organization-name">Household or organization name <input id="client-organization-name" name="organization_name" value="{escape(profile.get('organization_name', ''))}" maxlength="{CLIENT_ORGANIZATION_MAX_LENGTH}" autocomplete="organization" autocapitalize="words" spellcheck="true" required></label>
          <fieldset class="wide option-fieldset"><legend>Workspace type</legend><div class="choice-grid compact-choice-grid">{account_choices}</div></fieldset>
          <fieldset id="bid-reminders" class="wide option-fieldset" aria-describedby="client-notification-preference-help"><legend>Bid reminders</legend><div class="choice-grid compact-choice-grid two-column">{notification_choices}</div><span id="client-notification-preference-help" class="help-text">Email reminders are optional. Choosing email and saving this profile records your consent; switch back here at any time. Account and security emails still arrive.</span></fieldset>
          <label class="wide" for="client-profile-note">Private workspace note <span class="optional-label">Optional</span><textarea id="client-profile-note" name="profile_note" rows="4" maxlength="{CLIENT_PROFILE_NOTE_MAX_LENGTH}" autocapitalize="sentences" spellcheck="true" aria-describedby="client-profile-note-help">{escape(profile.get('profile_note', ''))}</textarea><span id="client-profile-note-help" class="help-text">For recurring access, timing, or property-management context. Contractors cannot see this note.</span></label>
          <div class="form-actions wide"><button class="button" type="submit">Save profile</button><p id="client-profile-status" class="help-text" data-form-status aria-live="polite"></p></div>
        </form>
      </section>
      <section id="saved-project-areas" class="profile-tool" aria-labelledby="saved-project-areas-title">
        <div class="section-heading"><div><p class="eyebrow">Repeat work</p><h2 id="saved-project-areas-title">Saved project areas</h2></div><span class="count-pill">{len(locations)}/{SAVED_LOCATION_LIMIT}</span></div>
        <p class="section-intro">Save city and ZIP-level areas only. Exact street addresses stay out of Workdoe project posts.</p>
        <form class="saved-location-form" data-json-action="/api/client/locations" data-success-url-template="/client/profile#saved-project-areas" aria-label="Save a project area" aria-describedby="saved-location-status">
          <label for="saved-location-label">Area name <input id="saved-location-label" name="label" maxlength="{SAVED_LOCATION_LABEL_MAX_LENGTH}" autocomplete="off" placeholder="Main shop" required></label>
          <label for="saved-location-city">City <input id="saved-location-city" name="city" maxlength="{SAVED_LOCATION_CITY_MAX_LENGTH}" autocomplete="address-level2" autocapitalize="words" spellcheck="false" placeholder="Washington" required></label>
          <label for="saved-location-state">State <select id="saved-location-state" name="state" autocomplete="address-level1" required><option value="DC">DC</option><option value="MD">MD</option><option value="VA">VA</option></select></label>
          <label for="saved-location-zip-code">ZIP <input id="saved-location-zip-code" name="zip_code" pattern="[0-9]{{5}}" maxlength="5" inputmode="numeric" autocomplete="postal-code" placeholder="20003" required></label>
          <button class="button" type="submit">Save area</button>
          <p id="saved-location-status" class="help-text" data-form-status aria-live="polite"></p>
        </form>
        <div class="saved-location-list">{locations_html}</div>
      </section>
      <section id="project-templates" class="profile-tool wide-profile-tool" aria-labelledby="project-templates-title">
        <div class="section-heading"><div><p class="eyebrow">Reusable scope</p><h2 id="project-templates-title">Project templates</h2></div><span class="count-pill">{len(templates or [])}/{PROJECT_TEMPLATE_LIMIT}</span></div>
        <p class="section-intro">Save the service, scope, setting, and budget from one of your projects. Location, date, photos, bids, and messages are never copied.</p>
        <form class="project-template-form" data-json-action="/api/client/templates" data-success-url-template="/client/profile#project-templates" aria-label="Save a project template" aria-describedby="project-template-status">
          <label for="project-template-name">Template name <input id="project-template-name" name="name" maxlength="{PROJECT_TEMPLATE_NAME_MAX_LENGTH}" autocomplete="off" placeholder="Monthly storefront cleanup" required></label>
          <label for="project-template-source">Copy scope from <select id="project-template-source" name="source_job_id" required>{''.join(source_options)}</select></label>
          <button class="button" type="submit"{" disabled" if not source_jobs else ""}>Save template</button>
          <p id="project-template-status" class="help-text" data-form-status aria-live="polite"></p>
        </form>
        <div class="project-template-list">{templates_html}</div>
      </section>
    </section>"""  # nosec B608
    return layout(user, "/client/profile", "Consumer Profile", body, include_actions=True)


def client_request_inbox_html(user, payload: dict) -> str:
    jobs = payload.get("jobs", [])
    stats = payload.get("stats", {})
    rows = []
    for job in jobs:
        pending_count = int(job.get("pending_count", 0) or 0)
        rows.append(
            f"""
    <a class="job-row link-row needs-review" href="{escape(job.get('review_url', '#'))}" aria-label="Review {pending_count} pending {'bid' if pending_count == 1 else 'bids'} for {escape(job.get('title', 'project'))}">
      <div>
        <div class="row-meta">
          <span class="status {escape(job.get('status', ''))}">{escape(job.get('status', ''))}</span>
          <span>{escape(job_service_name(job))}</span>
          <span>{escape(job.get('city', ''))}, {escape(job.get('state', ''))}</span>
        </div>
        <h2>{escape(job.get('title', ''))}</h2>
        <p class="job-summary">{escape(job.get('description', ''))}</p>
      </div>
      <div class="row-actions">
        <span class="count-pill attention">{pending_count} pending</span>
        <span class="row-cue">Review bids</span>
      </div>
    </a>"""
        )
    request_html = "\n".join(rows) if rows else empty_state("No bids waiting", "/client/dashboard", "View projects")
    body = f"""
    <section class="dashboard-header">
      <div>
        <p class="eyebrow">Consumer workspace</p>
        <h1>Bid requests</h1>
        <p>Compare contractor scope, timing, and pricing before opening a private conversation.</p>
      </div>
      <a class="button" href="/jobs/new">Post a project</a>
    </section>
    <section class="dashboard-metrics" aria-label="Bid request queue">
      <div class="metric-card"><span>Pending bids</span><strong>{int(stats.get('pending_requests', 0))}</strong></div>
      <div class="metric-card"><span>Projects to review</span><strong>{int(stats.get('review_jobs', 0))}</strong></div>
      <div class="metric-card"><span>Approved bids</span><strong>{int(stats.get('approved_requests', 0))}</strong></div>
    </section>
    <section class="job-list" aria-label="Projects with pending bids">
{request_html}
    </section>"""
    return layout(user, "/client/requests", "Bid Requests", body)


def safety_page_html() -> str:
    body = """
    <section class="page-header">
      <p class="eyebrow">Work with confidence</p>
      <h1>Share only what the job needs.</h1>
      <p>Workdoe keeps early conversations focused on project scope, approximate location, and contractor fit.</p>
    </section>
    <section class="content-grid two" aria-label="Workdoe safety practices">
      <article class="panel">
        <h2>Approximate locations</h2>
        <p>Contractors see the city and a rounded ZIP area before a client approves a bid. Do not put an exact address in a public project description.</p>
      </article>
      <article class="panel">
        <h2>Private contact</h2>
        <p>A private message thread opens after the client approves a contractor's mini bid. Keep access codes, payment details, and sensitive documents out of messages.</p>
      </article>
      <article class="panel">
        <h2>Review before approval</h2>
        <p>Clients can compare the proposed scope, price range, timeline, experience, and availability before choosing who to contact.</p>
      </article>
      <article class="panel">
        <h2>Check local requirements</h2>
        <p>Workdoe does not verify provider credentials. Confirm licenses, permits, insurance, inspections, and safe-work requirements directly with the provider and the appropriate local authority.</p>
      </article>
      <article class="panel">
        <h2>Report concerns</h2>
        <p>Report suspicious projects, profiles, photos, or messages from the related Workdoe page. Workdoe moderators can review content and suspend accounts when needed.</p>
      </article>
    </section>
    <section class="trust-contact" aria-labelledby="safety-contact-title">
      <p class="eyebrow">Contact</p>
      <h2 id="safety-contact-title">Safety and account help</h2>
      <p>Email <a href="mailto:admin@workdoe.com">admin@workdoe.com</a> for account, privacy, or safety requests. Workdoe is not an emergency service; call 911 when anyone faces immediate danger.</p>
    </section>"""
    return layout(None, "/safety", "Safety", body)


def privacy_page_html() -> str:
    body = """
    <section class="page-header trust-page-header">
      <p class="eyebrow">Controlled beta</p>
      <h1>Privacy Policy</h1>
      <p>Effective August 17, 2026. This notice explains the information Workdoe uses to operate the local work exchange.</p>
    </section>
    <article class="legal-copy">
      <section><h2>Information we collect</h2><p>We collect account identity and email verification details, your fixed consumer or contractor role, profile information you choose to provide, project and bid details, approximate service areas, photos, approved-match messages, reports, and security or audit records.</p><p>Workdoe does not collect payment card details, browser geolocation, or an exact project address in this beta. Do not put an address, access code, phone number, or email address in a public project description.</p></section>
      <section><h2>How we use information</h2><p>We use information to verify accounts, publish and match local projects, show relevant contractor profiles, open messaging after a client approves a bid, prevent abuse, moderate content, send account or service messages, and maintain marketplace and security records.</p></section>
      <section><h2>Who can see it</h2><p>Public visitors receive limited project summaries and approximate map pins. Signed-in contractors can see project briefs and job photos for available work. Clients can review bids and relevant contractor profiles. Approved participants can use a private message thread. Active administrators can review records needed for moderation and security.</p><p>Service providers supporting the beta may process limited information on Workdoe's behalf. These include the identity, hosting, email, bot-protection, and map services needed to run Workdoe. We do not sell personal information or use it for third-party behavioral advertising.</p></section>
      <section><h2>Retention and choices</h2><p>We keep records only while they are reasonably needed to operate the beta, investigate abuse, meet legal obligations, and respond to requests. The controlled beta does not yet promise a fixed deletion period.</p><p>Email <a href="mailto:admin@workdoe.com">admin@workdoe.com</a> to request access, correction, or deletion. Some records may be retained when required for security, fraud prevention, dispute preservation, or legal compliance.</p></section>
      <section><h2>Age and changes</h2><p>Workdoe accounts are for adults who are at least 18 years old and able to enter a service agreement. We may update this notice as the beta changes and will revise the effective date when we do.</p></section>
    </article>"""
    return layout(None, "/privacy", "Privacy Policy", body)


def terms_page_html() -> str:
    body = """
    <section class="page-header trust-page-header">
      <p class="eyebrow">Controlled beta</p>
      <h1>Terms of Use</h1>
      <p>Effective August 17, 2026. These terms describe the boundaries of the Workdoe local work exchange.</p>
    </section>
    <article class="legal-copy">
      <section><h2>Who may use Workdoe</h2><p>You must be at least 18 years old, use accurate account information, and have authority to post or perform the work. One account keeps one marketplace role: consumers post projects and contractors respond to projects.</p></section>
      <section><h2>Marketplace role</h2><p>Workdoe helps independent consumers and contractors find each other. Workdoe is not the employer, general contractor, agent, insurer, payment processor, or party performing the project. The participants decide whether to work together and are responsible for scope, price, scheduling, permits, licenses, insurance, taxes, contracts, payment, and safe performance.</p><p>The beta does not provide payment, escrow, warranties, background checks, license verification, emergency dispatch, ratings, or dispute adjudication. Profile qualifications and project statements are self-reported unless Workdoe explicitly says otherwise.</p></section>
      <section><h2>Project and account conduct</h2><p>Post a clear and lawful scope, protect private contact and location details, communicate respectfully, and do not misrepresent identity, qualifications, availability, ownership, or authorization. Do not scrape accounts, bypass access controls, spam users, manipulate bids, or use Workdoe to commit fraud or discrimination.</p></section>
      <section><h2>Prohibited work</h2><p>Do not post or seek illegal work, emergency response, medical or personal-care services, firearms activity, hazardous-material or asbestos/mold/lead abatement, unlicensed gas or utility work, insurance-claim negotiation, illegal dumping, or work that would place an unverified minor at risk. Workdoe may restrict additional high-risk categories until the required verification and operating controls exist.</p></section>
      <section><h2>Moderation and availability</h2><p>Workdoe may hide content, limit a service area, suspend an account, preserve audit records, or report credible threats when needed for safety, policy enforcement, or legal compliance. The controlled beta may change, pause, or end without guaranteeing that a project receives bids or that a contractor receives work.</p></section>
      <section><h2>Questions</h2><p>Email <a href="mailto:admin@workdoe.com">admin@workdoe.com</a> with account, policy, privacy, or safety questions. Call 911 for immediate danger; Workdoe is not an emergency service.</p></section>
    </article>"""
    return layout(None, "/terms", "Terms of Use", body)


def public_robots_txt() -> str:
    return """User-agent: *
Allow: /
Disallow: /account
Disallow: /admin
Disallow: /api/
Disallow: /client/
Disallow: /contractor/
Disallow: /create-account
Disallow: /jobs/
Disallow: /leads
Disallow: /login
Disallow: /media/
Disallow: /messages
Disallow: /post-project
Sitemap: https://workdoe.com/sitemap.xml
"""


def public_sitemap_xml() -> str:
    paths = ("/", "/safety", "/privacy", "/terms")
    urls = "".join(
        f"<url><loc>https://workdoe.com{path}</loc></url>" for path in paths
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}</urlset>"
    )


def public_security_txt() -> str:
    return """Contact: mailto:admin@workdoe.com
Contact: https://workdoe.com/safety
Expires: 2027-08-16T23:59:59Z
Preferred-Languages: en
Canonical: https://workdoe.com/.well-known/security.txt
Policy: https://workdoe.com/safety
"""


def contractor_reputation_html(reputation: dict, title_id: str) -> str:
    if not reputation:
        return ""
    completions = int(reputation.get("verified_completions", 0) or 0)
    completion_label = "project" if completions == 1 else "projects"
    next_milestone = reputation.get("next_milestone")
    if next_milestone:
        remaining = int(next_milestone.get("remaining", 0) or 0)
        project_label = "project" if remaining == 1 else "projects"
        next_html = (
            f"Next: {escape(next_milestone.get('label', 'the next milestone'))} "
            f"in {remaining} {project_label}"
        )
        progress_label = f"Progress to {next_milestone.get('label', 'next milestone')}"
    else:
        next_html = "All current completion milestones reached"
        progress_label = "Progress through current milestone maximum"
    milestones_html = ""
    for milestone in reputation.get("milestones", []):
        state = str(milestone.get("state", "locked") or "locked")
        if state not in {"earned", "current", "next", "locked"}:
            state = "locked"
        threshold = max(1, int(milestone.get("threshold", 1) or 1))
        earned = bool(milestone.get("earned"))
        marker = (
            '<img src="/vendor/tabler-icons/sparkles.svg" alt="">'
            if earned
            else str(threshold)
        )
        status = "Earned" if earned else f"At {threshold} {'project' if threshold == 1 else 'projects'}"
        current = ' aria-current="step"' if state == "current" else ""
        milestones_html += f"""
        <li class="milestone-step is-{state}"{current}>
          <span class="milestone-marker" aria-hidden="true">{marker}</span>
          <span class="milestone-copy"><strong>{escape(milestone.get('label', 'Milestone'))}</strong><small>{status}</small></span>
        </li>"""
    signals_html = "".join(
        '<span class="trust-chip"><img src="/vendor/tabler-icons/home-check.svg" alt="">'
        + escape(signal.get("label", "Source checked"))
        + "</span>"
        for signal in reputation.get("credential_signals", [])
    )
    return f"""
    <section class="work-progress" aria-labelledby="{escape(title_id)}">
      <div class="work-progress-heading">
        <span class="work-progress-icon" aria-hidden="true"><img src="/vendor/tabler-icons/sparkles.svg" alt=""></span>
        <div><p class="eyebrow">Work milestones</p><h3 id="{escape(title_id)}">{escape(reputation.get('level_label', 'New to Workdoe'))}</h3></div>
        <span class="work-progress-score"><strong>{int(reputation.get('completion_points', 0) or 0)} pts</strong><small>{completions} verified {completion_label}</small></span>
      </div>
      <ol class="milestone-track" aria-label="Verified completion milestones">{milestones_html}</ol>
      <p class="work-progress-note">Mutually confirmed Workdoe projects only. Points never change lead or bid order.</p>
      <progress aria-label="{escape(progress_label)}" value="{int(reputation.get('progress_value', 0) or 0)}" max="{max(1, int(reputation.get('progress_max', 1) or 1))}">{int(reputation.get('progress_value', 0) or 0)} of {max(1, int(reputation.get('progress_max', 1) or 1))}</progress>
      <div class="work-progress-footer"><span>{next_html}</span>{signals_html}</div>
    </section>"""


def contractor_dashboard_html(user, payload: dict) -> str:
    bids = payload.get("bids", [])
    profile = payload.get("profile", {})
    completed_work = payload.get("completed_work", [])
    repeat_invitations = payload.get("repeat_invitations", [])
    proposal_templates = payload.get("proposal_templates", [])
    proposal_template_limit = int(payload.get("proposal_template_limit", 6) or 6)
    stats = payload.get("stats", {})
    reputation = payload.get("reputation", {})
    reviews_by_request = payload.get("reviews_by_request", {})
    bid_view = str(payload.get("view", "all") or "all")
    bid_view_links = payload.get("view_links", [])
    rows = []
    for bid in bids:
        row_cue = str(bid.get("row_cue", "View") or "View")
        row_label = (
            f"Message about {bid.get('title', 'bid')}"
            if row_cue == "Message"
            else f"View mini bid for {bid.get('title', 'bid')}"
        )
        rows.append(
            f"""
    <a class="job-row link-row" href="{escape(bid.get('url', '#'))}" aria-label="{escape(row_label)}">
      <span><strong>{escape(bid.get('title', ''))}</strong><small>{escape(bid.get('category', ''))} in {escape(bid.get('city', ''))}, {escape(bid.get('state', ''))}</small></span>
      <span class="row-actions"><span class="status {escape(bid.get('status', ''))}">{escape(bid.get('status', ''))}</span><span class="row-cue">{escape(row_cue)}</span></span>
    </a>"""
        )
    if rows:
        bid_html = "\n".join(rows)
    elif bid_view == "all":
        bid_html = '<p class="empty">No mini bids yet. <a href="/leads">Browse projects</a></p>'
    else:
        empty_label = {
            "pending": "No pending bids.",
            "approved": "No approved bids.",
            "rejected": "No rejected bids.",
        }.get(bid_view, "No mini bids yet.")
        bid_html = (
            f'<p class="empty">{empty_label} '
            '<a href="/contractor/dashboard">All bids</a></p>'
        )
    invitation_rows = []
    for invitation in repeat_invitations:
        invitation_id = int(invitation.get("id", 0) or 0)
        invitation_rows.append(
            f"""
      <article class="history-row repeat-invitation-row">
        <div>
          <div class="row-meta"><span class="completion-chip verified">Invited back</span><span>{escape(invitation.get('category', ''))}</span><span>{escape(invitation.get('city', ''))}, {escape(invitation.get('state', ''))}</span></div>
          <h3>{escape(invitation.get('project_title', 'Project'))}</h3>
          <p>A consumer from a mutually verified Workdoe project invited you to send a fresh mini bid.</p>
          <span class="help-text">{escape(invitation.get('bid_window', {}).get('availability_label', ''))} - normal bid limits still apply.</span>
        </div>
        <div class="history-row-actions">
          <a class="button compact" href="{escape(invitation.get('detail_url', '#'))}">Review and bid</a>
          <form data-json-action="/api/repeat-invitations/{invitation_id}/decline" data-success-url-template="/contractor/dashboard" aria-label="Pass on {escape(invitation.get('project_title', 'project'))}"><button class="button secondary compact" type="submit">Pass</button><span class="sr-only" data-form-status aria-live="polite"></span></form>
        </div>
      </article>"""
        )
    invitation_html = "\n".join(invitation_rows)
    completed_rows = []
    for item in completed_work:
        request_id = int(item.get("id", 0) or 0)
        completion_action = ""
        if item.get("can_confirm_completion"):
            completion_action = f"""
          <form data-json-action="/api/match-requests/{request_id}/complete" data-success-url-template="/contractor/dashboard#completed-work" aria-label="Confirm completion for {escape(item.get('title', 'project'))}" aria-describedby="match-completion-{request_id}-status">
            <button class="button compact" type="submit">Confirm complete</button>
            <p id="match-completion-{request_id}-status" class="help-text" data-form-status aria-live="polite"></p>
          </form>"""
        item_reviews = reviews_by_request.get(request_id, {})
        feedback_html = ""
        if item.get("verified_at"):
            feedback_parts = []
            if not item_reviews.get("contractor"):
                feedback_parts.append(
                    match_review_form_html(
                        request_id,
                        "contractor",
                        "/contractor/dashboard#completed-work",
                    )
                )
            feedback_parts.extend(
                match_review_card_html(
                    review,
                    user,
                    "/contractor/dashboard#completed-work",
                )
                for review in item_reviews.values()
            )
            feedback_html = (
                '<section class="completed-feedback" aria-label="Completed-work feedback">'
                + "".join(feedback_parts)
                + "</section>"
            )
        completed_rows.append(
            f"""
      <div class="history-row completed-work-row">
        <div>
          <div class="row-meta"><span>{escape(item.get('category', ''))}</span><span>{escape(item.get('city', ''))}, {escape(item.get('state', ''))}</span></div>
          <h3>{escape(item.get('title', ''))}</h3>
          <p>{escape(item.get('scope_note', ''))}</p>
          <dl class="history-facts">
            <div><dt>Timeline</dt><dd>{escape(item.get('timeline', ''))}</dd></div>
            <div><dt>Estimate</dt><dd>{escape(item.get('price_range', ''))}</dd></div>
            <div><dt>Availability</dt><dd>{escape(item.get('availability', ''))}</dd></div>
          </dl>
          <div class="completion-status {escape(item.get('completion_state', 'awaiting'))}">
            <strong>{escape(item.get('completion_label', 'Awaiting both confirmations'))}</strong>
            <span>{'Both participants confirmed this Workdoe project.' if item.get('verified_at') else 'Both participants confirm independently. No rating or payment is created.'}</span>
          </div>
          {feedback_html}
        </div>
        <div class="history-row-actions">
          <a class="button secondary compact" href="{escape(item.get('url', '#'))}">Details</a>
          {completion_action}
        </div>
      </div>"""
        )
    completed_html = "\n".join(completed_rows) if completed_rows else '<p class="empty history-empty">Work matched on Workdoe appears here after the consumer closes the project.</p>'
    proposal_template_rows = []
    for template in proposal_templates:
        template_id = int(template.get("id", 0) or 0)
        proposal_template_rows.append(
            f"""
      <article class="project-template-row">
        <div><strong>{escape(template.get('name', ''))}</strong><span>{escape(template.get('timeline', ''))} - {escape(template.get('availability', ''))}</span></div>
        <div class="saved-location-actions"><form data-json-action="/api/contractor/proposal-templates/{template_id}/delete" data-success-url-template="/contractor/dashboard#proposal-templates" aria-label="Remove {escape(template.get('name', 'proposal template'))}"><button class="button secondary compact" type="submit">Remove</button><span class="sr-only" data-form-status aria-live="polite"></span></form></div>
      </article>"""
        )
    proposal_template_html = (
        "".join(proposal_template_rows)
        if proposal_template_rows
        else '<p class="empty history-empty">After sending a mini bid, save its reusable wording here.</p>'
    )
    business_name = (
        profile.get("business_name")
        or row_value(user, "company_name")
        or row_value(user, "display_name")
        or "Contractor profile"
    )
    profile_intro = profile.get("intro") or (
        "Complete your profile so clients can understand your services before approving a match."
    )
    bid_tabs = []
    for item in bid_view_links:
        value = str(item.get("value", "") or "")
        count = {
            "all": int(stats.get("total_requests", 0)),
            "pending": int(stats.get("pending_requests", 0)),
            "approved": int(stats.get("approved_requests", 0)),
            "rejected": int(stats.get("rejected_requests", 0)),
        }.get(value, 0)
        current = ' aria-current="page"' if value == bid_view else ""
        active_class = " is-active" if value == bid_view else ""
        bid_tabs.append(
            f'<a class="work-view-tab{active_class}" href="{escape(item.get("url", "/contractor/dashboard"))}"{current}><span>{escape(item.get("label", value.title()))}</span><strong>{count}</strong></a>'
        )
    bid_tabs_html = "".join(bid_tabs)
    body = f"""
    <section class="dashboard-header">
      <div>
        <p class="eyebrow">Contractor workspace</p>
        <h1>Your bids</h1>
      </div>
      <a class="button" href="/leads">Browse projects</a>
    </section>
    <section class="work-history contractor-bid-workspace" aria-label="Contractor mini bids">
      <nav class="work-view-tabs bid-view-tabs contractor-bid-tabs" aria-label="Contractor mini bid status">{bid_tabs_html}</nav>
      <div class="job-list compact-list" aria-label="Contractor mini bids">
{bid_html}
      </div>
    </section>
    {contractor_reputation_html(reputation, 'dashboard-reputation-title')}
    {(
        '<section class="work-history" aria-labelledby="repeat-invitations-title"><div class="section-heading history-heading"><div><p class="eyebrow">Prior clients</p><h2 id="repeat-invitations-title">Invited back</h2></div><span class="count-pill">'
        + str(len(repeat_invitations))
        + ' open</span></div><div class="history-list">'
        + invitation_html
        + '</div></section>'
    ) if invitation_html else ''}
    <section class="contractor-workspace-context" aria-label="Contractor profile summary">
      <div class="contractor-workspace-identity">
        <p class="eyebrow">Profile signal</p>
        <h2>{escape(business_name)}</h2>
        <p>{escape(profile_intro)}</p>
      </div>
      <dl class="contractor-snapshot-facts">
        <div><dt>Trades</dt><dd>{escape(profile.get('trades') or 'Not set')}</dd></div>
        <div><dt>Service area</dt><dd>{escape(profile.get('service_area') or 'DMV area')}</dd></div>
        <div><dt>Insurance</dt><dd>{escape(profile.get('insurance_status') or 'Not set')}</dd></div>
      </dl>
      <a class="button secondary compact" href="/contractor/profile">Edit profile</a>
    </section>
    <section id="proposal-templates" class="work-history" aria-labelledby="proposal-templates-title">
      <div class="section-heading history-heading"><div><p class="eyebrow">Faster responses</p><h2 id="proposal-templates-title">Proposal templates</h2></div><span class="count-pill">{len(proposal_templates)}/{proposal_template_limit}</span></div>
      <p class="section-intro">Save reusable wording from a mini bid, then apply it to another lead. Every project still requires a fresh price.</p>
      <div class="project-template-list">{proposal_template_html}</div>
    </section>
    <section id="completed-work" class="work-history" aria-labelledby="completed-work-title">
      <div class="section-heading history-heading"><div><p class="eyebrow">Work outcomes</p><h2 id="completed-work-title">Matched work</h2></div><span class="count-pill">{int(stats.get('verified_completions', 0))} verified</span></div>
      <div class="history-list">
{completed_html}
      </div>
      <p class="help-text history-privacy">Closed work shows the project and general service area only. Specific addresses stay private.</p>
    </section>"""
    return layout(user, "/contractor/dashboard", "Bids", body)


def service_family_filter_html(
    filters: dict,
    *,
    path: str = "/leads",
    view: str = "all",
) -> str:
    shared: dict[str, str] = {}
    if filters.get("q"):
        shared["q"] = filters["q"]
    if filters.get("sort", "newest") != "newest":
        shared["sort"] = filters["sort"]
    if view != "all":
        shared["view"] = view
    current = filters.get("family", "")
    options = [
        {
            "slug": "",
            "number": "00",
            "name": "All work",
            "description": "Every open service",
            "icon": "",
        },
        *[
            {
                "slug": group["slug"],
                "number": f"{index:02d}",
                "name": group["name"],
                "description": group["description"],
                "icon": group["icon"],
            }
            for index, group in enumerate(SERVICE_GROUPS, start=1)
        ],
    ]
    links = []
    for option in options:
        args = dict(shared)
        if option["slug"]:
            args["family"] = option["slug"]
        href = path + (f"?{urlencode(args)}" if args else "")
        active = current == option["slug"]
        icon = (
            f'<img src="/vendor/tabler-icons/{escape(option["icon"])}" alt="" width="24" height="24">'
            if option["icon"]
            else ""
        )
        links.append(
            f'<a class="service-family-filter-link{" is-active" if active else ""}" href="{escape(href)}"{' aria-current="page"' if active else ""}>'
            f'<span class="service-family-filter-visual" aria-hidden="true"><span>{option["number"]}</span>{icon}</span>'
            f'<span class="service-family-filter-copy"><strong>{escape(option["name"])}</strong><small>{escape(option["description"])}</small></span></a>'
        )
    return '<nav class="service-family-filter" aria-label="Filter projects by work family">' + "".join(links) + "</nav>"


def lead_board_html(user, payload: dict) -> str:
    jobs = payload.get("jobs", [])
    filters = payload.get("filters", {})
    preferences = payload.get("preferences", {})
    lead_alert_choices = "".join(
        f'<label><input type="radio" name="lead_alert_preference" value="{escape(value)}"{' checked' if preferences.get("lead_alert_preference", "workdoe") == value else ''} required><span>{escape(label)}</span></label>'
        for value, label in LEAD_ALERT_OPTIONS
    )
    selected = jobs[0] if jobs else None
    rows = []
    for job in jobs:
        row_cue = str(job.get("row_cue", "View") or "View")
        icon_name = service_icon(job.get("service_slug") or job.get("category"))
        row_label = (
            f"Open sent bid for {job.get('title', 'lead')}"
            if row_cue == "Sent"
            else f"View {job.get('title', 'lead')}"
        )
        rows.append(
            f"""
      <a class="project-result{' is-map-active' if job is selected else ''}" role="listitem" data-job-id="{escape(str(job.get('id', '')))}" href="{escape(job.get('url', '#'))}" aria-label="{escape(row_label)}"{' aria-current="true"' if job is selected else ''}>
        <span class="project-result-topline">
          {('<span class="lead-fit fit-' + str(int(job.get('fit_score', 0) or 0)) + '">' + escape(job.get('fit_label', '')) + '</span>') if job.get('fit_label') else ''}
          <span class="job-service-chip"><img src="/vendor/tabler-icons/{escape(icon_name)}" alt="" width="16" height="16">{escape(job_service_name(job))}</span>
          {('<span class="status ' + escape(job.get('request_status', '')) + '">Bid ' + escape(job.get('request_status', '')) + '</span>') if job.get('request_status') else ''}
        </span>
        <strong>{escape(job.get('title', ''))}</strong>
        <span class="project-result-facts">
          <span>{escape(job.get('city', ''))}, {escape(job.get('state', ''))}</span>
          <span>{escape(job.get('bid_window', {}).get('availability_label', ''))}</span>
          {brief_readiness_pill_html(job.get('brief_readiness'))}
          <span>{escape(row_cue)}</span>
        </span>
      </a>"""
        )
    list_html = "\n".join(rows) if rows else '<div class="market-list-empty"><strong>No matching projects</strong><span>Clear filters to widen the map.</span></div>'
    map_jobs = payload.get("map_jobs", [])
    list_role = ' role="list"' if rows else ""
    selected_family = GROUP_BY_SLUG.get(filters.get("family", ""))
    task_filter_html = ""
    if selected_family:
        service_options = [
            f'<option value="">All {escape(selected_family["name"].lower())} tasks</option>'
        ]
        service_options.extend(
            f'<option value="{escape(service_slug)}"{" selected" if filters.get("service") == service_slug else ""}>{escape(service_name)}</option>'
            for service_slug, service_name, _category in selected_family["services"]
        )
        task_filter_html = (
            '<label for="market-service">Task</label>'
            f'<select id="market-service" name="service" data-market-service>{"".join(service_options)}</select>'
        )
    sort_options = "".join(
        f'<option value="{value}"{" selected" if filters.get("sort", "newest") == value else ""}>{label}</option>'
        for value, label in (("newest", "Newest"), ("soonest", "Soonest"), ("city", "City"))
    )
    if preferences.get("has_saved_lead_view"):
        saved_query_label = (
            f' near {escape(preferences.get("saved_query", ""))}'
            if preferences.get("saved_query")
            else ""
        )
        saved_view_html = (
            f'<a class="button secondary compact" href="{escape(payload.get("saved_lead_view_url", "/leads"))}">Use saved view</a>'
            f'<span>{escape(preferences.get("saved_service_label") or preferences.get("saved_family_label") or preferences.get("saved_category") or "All work")}{saved_query_label}{" - Email alerts on" if preferences.get("lead_alert_enabled") else ""}</span>'
        )
    else:
        saved_view_html = '<span>Keep a useful task, area, or sort for your next visit.</span>'
    if selected:
        desired_date = escape(selected.get("desired_date", "") or "Flexible")
        action_label = (
            "View bid status"
            if selected.get("request_status")
            else "Review and bid"
        )
        detail_html = f"""
        <article class="market-project-detail" data-project-detail-content data-job-id="{escape(str(selected.get('id', '')))}">
          <div class="project-detail-heading"><span class="live-badge">Open project</span><span>{escape(selected.get('category', ''))}</span></div>
          <h2>{escape(selected.get('title', ''))}</h2>
          <p class="project-detail-location">{escape(selected.get('city', ''))}, {escape(selected.get('state', ''))}</p>
          <dl class="project-facts">
            <div><dt>Estimated budget</dt><dd>{escape(selected.get('budget', '') or 'Budget not provided')}</dd></div>
            <div><dt>Desired date</dt><dd>{desired_date}</dd></div>
            <div><dt>Mini bids</dt><dd>{escape(selected.get('bid_window', {}).get('usage_label', ''))}</dd></div>
          </dl>
          <div class="project-description"><h3>Field brief</h3><p>{escape(selected.get('description', ''))}</p></div>
          <p class="project-privacy-note">Location is intentionally approximate until a match is approved.</p>
          <div class="project-detail-actions"><a class="button primary" href="{escape(selected.get('url', '#'))}" data-dialog-title="{escape(action_label)}">{escape(action_label)}</a></div>
        </article>"""
    else:
        detail_html = """
        <div class="market-detail-empty" data-project-detail-content>
          <img src="/field-doe.webp" alt="" width="160" height="160">
          <h2>No projects match</h2><p>Adjust the filters to widen the map.</p>
        </div>"""
    body = f"""
    <div class="market-mobile-tabs" role="tablist" aria-label="Marketplace view">
      <button type="button" role="tab" data-mobile-panel-target="filters">Projects</button>
      <button type="button" role="tab" data-mobile-panel-target="map">Map</button>
      <button type="button" role="tab" data-mobile-panel-target="details">Details</button>
    </div>
    <section class="signed-in-market-heading">
      <div>
        <p class="eyebrow">Area scan // DMV</p>
        <h1>Work near you</h1>
      </div>
    </section>
    <section class="market-workspace signed-in-market-workspace" data-market-workspace data-mobile-panel="map">
      <aside class="market-filter-rail" data-market-panel="filters" aria-label="Project search and filters">
        <div class="market-rail-heading"><h2>Available projects</h2><p>Dispatch view with approximate locations until a client approves your bid.</p></div>
        {service_family_filter_html(filters, view=payload.get('view', 'all'))}
        <form class="market-filter-form" method="get" action="/leads" data-market-filters>
          {f'<input type="hidden" name="family" value="{escape(filters.get("family", ""))}">' if filters.get('family') else ''}
          <label for="market-search">Search projects</label>
          <input id="market-search" name="q" type="search" value="{escape(filters.get('q', ''))}" maxlength="80" placeholder="Try painting or Arlington" autocomplete="off" data-market-search>
          {task_filter_html}
          <label for="market-sort">Sort</label>
          <select id="market-sort" name="sort" data-market-sort>{sort_options}</select>
          <div class="filter-actions"><button class="button compact" type="submit">Filter</button><a class="button secondary compact" href="/leads" data-clear-market-filters>Clear</a></div>
        </form>
        <div id="saved-lead-alerts" class="saved-lead-toolbar" aria-label="Saved lead view and alerts">
          <form data-json-action="/api/contractor/preferences/lead-view" data-success-url-template="/leads" aria-describedby="saved-lead-view-status">
            <input type="hidden" name="saved_service_group_slug" value="{escape(filters.get('family', ''))}">
            <input type="hidden" name="saved_service_slug" value="{escape(filters.get('service', ''))}">
            <input type="hidden" name="saved_query" value="{escape(filters.get('q', ''))}">
            <input type="hidden" name="saved_category" value="{escape(filters.get('category', ''))}">
            <input type="hidden" name="saved_sort" value="{escape(filters.get('sort', 'newest'))}">
            <fieldset class="lead-alert-choice">
              <legend>New matching projects</legend>
              <div class="lead-alert-options">{lead_alert_choices}</div>
              <small>Email uses this saved view plus your selected services and DMV zones. Change it here at any time.</small>
            </fieldset>
            <button class="button secondary compact" type="submit">Save this view</button>
            <span id="saved-lead-view-status" class="sr-only" data-form-status aria-live="polite"></span>
          </form>
          {saved_view_html}
        </div>
        <div class="project-results-heading"><strong data-project-result-count>{len(jobs)} projects</strong><span>Ready to review</span></div>
        <div class="project-results" data-project-results aria-label="Open leads"{list_role}>
{list_html}
        </div>
      </aside>
      <section class="market-map-stage" data-market-panel="map" aria-label="Project map workspace">
        <div class="map-stage-toolbar"><div><span class="map-live-indicator" aria-hidden="true"></span><strong data-map-result-count>{len(map_jobs)} projects mapped</strong></div><span>Approximate pins</span></div>
        <div class="market-map-frame">
          <div id="lead-map" data-map data-map-workspace data-tile-url="https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png" data-tile-attribution='&amp;copy; &lt;a href="https://www.openstreetmap.org/copyright"&gt;OpenStreetMap&lt;/a&gt;' role="region" tabindex="0" aria-label="Approximate DMV job map" aria-describedby="lead-map-status">
            <p id="lead-map-loading" class="map-fallback" aria-hidden="true">Map loading. Project list is ready.</p>
            <p id="lead-map-status" class="sr-only" aria-live="polite" aria-atomic="true">Map loading. Project list is ready.</p>
          </div>
        </div>
      </section>
      <aside class="market-detail-rail" data-market-panel="details" aria-label="Selected project">{detail_html}</aside>
    </section>
    <script id="map-jobs-data" type="application/json">{safe_json_script(map_jobs)}</script>"""
    return layout(
        user,
        "/leads",
        "Find Work",
        body,
        include_map=True,
        include_actions=True,
        body_class="app-market-body",
        main_class="app-market-main",
    )


def turnstile_html(site_key: str, action: str) -> str:
    if not site_key:
        return ""
    return f"""
        <div class="turnstile-field">
          <div class="cf-turnstile" data-sitekey="{escape(site_key)}" data-action="{escape(action)}" data-theme="light"></div>
        </div>"""


def scope_questions_html(
    selected_service: str,
    answers: dict | None = None,
    *,
    all_services: bool = False,
) -> str:
    answers = answers or {}
    services = (
        SERVICE_SCOPE_QUESTIONS.items()
        if all_services
        else ((selected_service, SERVICE_SCOPE_QUESTIONS.get(selected_service, ())),)
    )
    panels = []
    for service_slug, questions in services:
        if not questions:
            continue
        active = service_slug == selected_service
        fields = []
        for question in questions:
            selected = str(answers.get(question["key"]) or "")
            options = ['<option value="">Open</option>']
            options.extend(
                f'<option value="{escape(option["value"])}"{' selected' if selected == option["value"] else ''}>{escape(option["label"])}</option>'
                for option in question["options"]
            )
            help_html = (
                f'<span class="help-text">{escape(question["help"])}</span>'
                if question.get("help")
                else ""
            )
            fields.append(
                f'<label for="scope-{escape(service_slug)}-{escape(question["key"])}">'
                f'{escape(question["label"])} <span class="optional-label">Optional</span>'
                f'<select id="scope-{escape(service_slug)}-{escape(question["key"])}" '
                f'name="{escape(question["field_name"])}" data-scope-select'
                f'{' disabled' if not active else ''}>{"".join(options)}</select>{help_html}</label>'
            )
        complete = sum(1 for question in questions if answers.get(question["key"]))
        open_attr = " open" if complete else ""
        panels.append(
            f'<details class="service-scope-panel" data-service-scope-set="{escape(service_slug)}"'
            f'{' hidden' if not active else ''}{open_attr}>'
            '<summary class="service-scope-head"><span class="service-scope-summary-content">'
            '<span class="service-scope-title">'
            '<span class="eyebrow">Quote-ready details</span>'
            '<strong>Add details <span class="optional-label">Optional</span></strong></span>'
            f'<span class="scope-readiness" data-scope-readiness>{complete} of {len(questions)} details ready</span>'
            '</span></summary>'
            '<div class="service-scope-body"><p class="help-text">Answer what you know to help contractors compare the same scope.</p>'
            f'<div class="scope-question-grid">{"".join(fields)}</div></div></details>'
        )
    return "".join(panels)


def quote_ready_details_html(scope_answers: list[dict] | None) -> str:
    if not scope_answers:
        return ""
    rows = "".join(
        f'<div><dt>{escape(answer.get("question_label", ""))}</dt><dd>{escape(answer.get("answer_label", ""))}</dd></div>'
        for answer in scope_answers
    )
    return f"""
        <section class="quote-ready-details" aria-label="Quote-ready details">
          <div class="section-heading compact-heading"><p class="eyebrow">Project signals</p><h3>Quote-ready details</h3></div>
          <dl class="scope-answer-list">{rows}</dl>
        </section>"""


def brief_readiness_pill_html(readiness: dict | None) -> str:
    if not readiness:
        return ""
    return (
        f'<span class="brief-pill {escape(readiness.get("state", "thin"))}">'
        f'{escape(readiness.get("label", "Brief 0 of 6"))}</span>'
    )


def brief_readiness_html(readiness: dict | None) -> str:
    if not readiness:
        return ""
    state = str(readiness.get("state", "thin") or "thin")
    state_label = {
        "ready": "Ready to quote",
        "building": "Useful start",
        "thin": "Needs detail",
    }.get(state, "Needs detail")
    items = "".join(
        '<li class="{status}"><span class="brief-signal-number">{number:02d}</span>'
        '<span>{label}</span><small>{detail}</small></li>'.format(
            status="complete" if signal.get("complete") else "pending",
            number=index,
            label=escape(signal.get("label", "Project detail")),
            detail="Included" if signal.get("complete") else "Missing",
        )
        for index, signal in enumerate(readiness.get("signals", []), start=1)
    )
    return f"""
        <section class="brief-readiness" aria-label="Project brief readiness">
          <div class="brief-readiness-heading">
            <div><p class="eyebrow">Brief readiness</p><h3>{escape(readiness.get('label', 'Brief 0 of 6'))}</h3></div>
            <span class="brief-readiness-state {escape(state)}">{escape(state_label)}</span>
          </div>
          <ol class="brief-signal-list">{items}</ol>
        </section>"""


def project_composer_fields_html(
    form: dict,
    *,
    errors: list[str] | None = None,
    include_photos: bool,
    submit_label: str,
    cancel_url: str,
    turnstile: str = "",
) -> str:
    fields = job_field_errors(errors or [])
    selection = service_selection(
        str(form.get("service_slug") or ""),
        str(form.get("service_group_slug") or ""),
        str(form.get("category") or ""),
    )
    form = {**form, **selection}
    selected_group = str(form.get("service_group_slug") or "")
    selected_service = str(form.get("service_slug") or "")
    selected_policy = service_policy(selected_service)
    selected_state = str(form.get("state") or "DC")
    selected_setting = str(form.get("project_setting") or "")
    scope_panels = scope_questions_html(
        selected_service,
        form.get("scope_answers", {}),
        all_services=True,
    )

    family_options = "".join(
        f"""
      <label class="service-family-option" for="service-family-{escape(group['slug'])}">
        <input id="service-family-{escape(group['slug'])}" type="radio" name="service_group_slug" value="{escape(group['slug'])}" data-group-name="{escape(group['name'])}" data-group-description="{escape(group['description'])}" data-group-icon="/vendor/tabler-icons/{escape(group['icon'])}"{' checked' if selected_group == group['slug'] else ''} required>
        <span class="service-family-visual" aria-hidden="true"><span class="service-family-number">{index:02d}</span><img src="/vendor/tabler-icons/{escape(group['icon'])}" alt=""></span>
        <span class="service-family-copy"><strong>{escape(group['name'])}</strong><small>{escape(group['description'])}</small></span>
      </label>"""
        for index, group in enumerate(SERVICE_GROUPS, start=1)
    )
    service_options = ['<option value="">Choose a service</option>']
    for group in SERVICE_GROUPS:
        option_rows = []
        for service in group["services"]:
            policy = service_policy(service[0])
            option_rows.append(
                f'<option value="{escape(service[0])}" data-group="{escape(group["slug"])}" '
                f'data-category="{escape(service[2])}" data-policy-tier="{escape(policy["risk_tier"])}" '
                f'data-policy-version="{escape(policy["version"])}" '
                f'data-policy-advisory="{escape(policy["advisory"])}" '
                f'data-policy-required="{str(policy["acknowledgement_required"]).lower()}" '
                f'data-policy-disabled="{str(policy["emergency_disabled"]).lower()}"'
                f'{' selected' if selected_service == service[0] else ''}>{escape(service[1])}</option>'
            )
        options = "".join(option_rows)
        service_options.append(
            f'<optgroup label="{escape(group["name"])}" data-service-group="{escape(group["slug"])}">{options}</optgroup>'
        )
    service_options_html = "".join(service_options)

    def service_choice_html(group: dict, service: tuple, index: int) -> str:
        return (
            f'<label class="service-option" for="service-choice-{escape(service[0])}">'
            f'<input id="service-choice-{escape(service[0])}" type="radio" name="service_choice" value="{escape(service[0])}" '
            f'data-group="{escape(group["slug"])}" data-category="{escape(service[2])}"'
            f'{' checked' if selected_service == service[0] else ''}>'
            f'<span class="service-option-visual" aria-hidden="true"><span>{index:02d}</span>'
            f'<img src="/vendor/tabler-icons/{escape(service_icon(service[0], group["icon"]))}" alt=""></span>'
            f'<span class="service-option-copy"><strong>{escape(service[1])}</strong>'
            f'<small>{escape(group["name"])}</small></span></label>'
        )

    def service_choice_group_html(group: dict) -> str:
        services = tuple(group["services"])
        quick_count = max(1, min(int(group.get("quick_count", 6)), len(services)))
        primary = "".join(
            service_choice_html(group, service, index)
            for index, service in enumerate(services[:quick_count], start=1)
        )
        additional = services[quick_count:]
        more = ""
        if additional:
            additional_cards = "".join(
                service_choice_html(group, service, quick_count + index)
                for index, service in enumerate(additional, start=1)
            )
            open_attr = " open" if any(selected_service == service[0] for service in additional) else ""
            more = (
                f'<details class="service-option-more"{open_attr}>'
                f'<summary>More {escape(group["name"].lower())} services</summary>'
                f'<div class="service-option-grid service-option-grid-more">{additional_cards}</div></details>'
            )
        hidden = " hidden" if selected_group != group["slug"] else ""
        return (
            f'<div class="service-option-group" data-service-option-group="{escape(group["slug"])}"{hidden}>'
            f'<p class="service-option-heading">Common tasks</p>'
            f'<div class="service-option-grid">{primary}</div>{more}</div>'
        )

    service_choice_groups = "".join(
        service_choice_group_html(group) for group in SERVICE_GROUPS
    )
    setting_options = "".join(
        f"""
        <label class="project-setting-option" for="project-setting-{escape(setting['value'])}">
          <input id="project-setting-{escape(setting['value'])}" type="radio" name="project_setting" value="{escape(setting['value'])}" data-setting-label="{escape(setting['label'])}"{' checked' if selected_setting == setting['value'] else ''}>
          <span class="project-setting-number" aria-hidden="true">{index:02d}</span>
          <span><strong>{escape(setting['label'])}</strong><small>{escape(setting['description'])}</small></span>
        </label>"""
        for index, setting in enumerate(PROJECT_SETTINGS, start=1)
    )

    def invalid(name: str, error_id: str) -> str:
        return f' aria-invalid="true" aria-describedby="{error_id}"' if fields.get(name) else ""

    def field_error(name: str, error_id: str) -> str:
        messages = fields.get(name) or []
        return f'<span id="{error_id}" class="field-error">{escape(messages[0])}</span>' if messages else ""

    service_error = (fields.get("service_slug") or fields.get("category") or [])
    service_error_html = (
        f'<span id="job-service-slug-error" class="field-error">{escape(service_error[0])}</span>'
        if service_error
        else ""
    )
    photos_html = (
        """
      <label for="job-photos">Photos <span class="optional-label">Optional</span>
        <input id="job-photos" name="photos" type="file" accept="image/png,image/jpeg,image/gif,image/webp" multiple aria-describedby="job-photos-help">
        <span id="job-photos-help" class="help-text">Private uploads. PNG, JPG, GIF, or WebP.</span>
      </label>"""
        if include_photos
        else '<p class="help-text">Photos stay private and can be added after email verification.</p>'
    )
    policy_hidden = (
        ""
        if selected_policy["acknowledgement_required"]
        or selected_policy["emergency_disabled"]
        else " hidden"
    )
    policy_required = (
        " required" if selected_policy["acknowledgement_required"] else " disabled"
    )
    policy_checked = (
        " checked"
        if str(form.get("service_policy_acknowledgement") or "")
        == selected_policy["version"]
        else ""
    )
    policy_invalid = invalid(
        "service_policy_acknowledgement",
        "job-service-policy-acknowledgement-error",
    )
    policy_panel = f"""
        <section class="service-policy-advisory" data-service-policy-advisory data-policy-service="{escape(selected_service)}"{policy_hidden}>
          <div><span class="eyebrow" data-service-policy-tier>{'Local rules check' if selected_policy['risk_tier'] == 'regulated' else 'Safety check'}</span><strong>Confirm before posting</strong><p data-service-policy-copy>{escape(selected_policy['advisory'])}</p></div>
          <label class="service-policy-confirmation" for="job-service-policy-acknowledgement"><input id="job-service-policy-acknowledgement" type="checkbox" name="service_policy_acknowledgement" value="{escape(selected_policy['version'])}" data-service-policy-checkbox{policy_required}{policy_checked}{policy_invalid}><span>I understand that I must confirm qualifications, insurance, permits, and a safe work plan directly.</span></label>
          {field_error('service_policy_acknowledgement', 'job-service-policy-acknowledgement-error')}
        </section>"""
    return f"""
      <div class="project-composer-head wide">
        <div><p class="eyebrow" data-project-step-label>Step 1 of 6</p><h2 data-project-step-title>Choose a work family</h2></div>
        <progress value="1" max="6" data-project-progress aria-label="Project posting progress">1 of 6</progress>
      </div>
      <fieldset class="project-composer-step wide" data-project-step="1" data-step-title="Choose a work family">
        <legend>What kind of work is this?</legend>
        <p class="help-text" id="service-family-help">Start broad. The next step narrows the project into a clean service bucket.</p>
        <div class="service-family-grid" aria-describedby="service-family-help">{family_options}</div>
        {field_error('service_group_slug', 'job-service-group-slug-error')}
        <div class="project-step-actions"><a class="button secondary" href="{escape(cancel_url)}">Cancel</a><button class="button" type="button" data-project-next>Continue</button></div>
      </fieldset>
      <fieldset class="project-composer-step wide" data-project-step="2" data-step-title="Pick the service">
        <legend>What should be done?</legend>
        <p class="help-text">Choose one task. Your description can handle the details.</p>
        <div class="service-family-context" data-selected-service-family hidden><img data-selected-service-family-icon alt="" aria-hidden="true"><span><small>Selected family</small><strong data-selected-service-family-name></strong><small data-selected-service-family-description></small></span></div>
        <div class="service-option-groups" data-service-option-groups>{service_choice_groups}</div>
        <label class="service-select-control" for="job-service-slug">Service <select id="job-service-slug" name="service_slug" required{' aria-invalid="true" aria-describedby="job-service-slug-error"' if service_error else ''}>{service_options_html}</select></label>
        <input id="job-category" type="hidden" name="category" value="{escape(str(form.get('category') or ''))}">
        {service_error_html}
        <div class="project-step-actions"><button class="button secondary" type="button" data-project-back>Back</button><button class="button" type="button" data-project-next>Continue</button></div>
      </fieldset>
      <fieldset class="project-composer-step wide" data-project-step="3" data-step-title="Describe the work">
        <legend>What does a contractor need to know?</legend>
        {scope_panels}
        <label for="job-title">Project title <input id="job-title" name="title" value="{escape(str(form.get('title') or ''))}" maxlength="90" autocomplete="off" autocapitalize="sentences" spellcheck="true" enterkeyhint="next" placeholder="Power wash front steps and patio" required{invalid('title', 'job-title-error')}>{field_error('title', 'job-title-error')}</label>
        <label for="job-description">Description <textarea id="job-description" name="description" rows="6" minlength="20" maxlength="1200" autocapitalize="sentences" spellcheck="true" enterkeyhint="done" placeholder="Describe the size, current condition, access, and desired outcome." required aria-describedby="job-description-help{' job-description-error' if fields.get('description') else ''}"{' aria-invalid="true"' if fields.get('description') else ''}>{escape(str(form.get('description') or ''))}</textarea><span id="job-description-help" class="help-text">Do not include an exact street address, email, or phone number.</span>{field_error('description', 'job-description-error')}</label>
        <fieldset class="project-setting-fieldset"{' aria-describedby="job-project-setting-error"' if fields.get('project_setting') else ''}>
          <legend>Where is the work happening? <span class="optional-label">Optional</span></legend>
          <p class="help-text">Choose the setting only. Do not add a building name, unit, or street address.</p>
          <div class="project-setting-grid">{setting_options}</div>
          {field_error('project_setting', 'job-project-setting-error')}
        </fieldset>
        <div class="project-step-actions"><button class="button secondary" type="button" data-project-back>Back</button><button class="button" type="button" data-project-next>Continue</button></div>
      </fieldset>
      <fieldset class="project-composer-step wide" data-project-step="4" data-step-title="Set the area">
        <legend>Where is the project?</legend><p class="help-text">Only an approximate city or ZIP pin is shown before a match is approved.</p>
        <div class="project-field-grid three">
          <label for="job-city">City <input id="job-city" name="city" value="{escape(str(form.get('city') or ''))}" maxlength="80" autocomplete="address-level2" autocapitalize="words" spellcheck="false" list="job-city-options" enterkeyhint="next" placeholder="Washington" required{invalid('city', 'job-city-error')}>{field_error('city', 'job-city-error')}</label>
          <label for="job-state">State <select id="job-state" name="state" autocomplete="address-level1" required{invalid('state', 'job-state-error')}><option value="DC"{' selected' if selected_state == 'DC' else ''}>DC</option><option value="MD"{' selected' if selected_state == 'MD' else ''}>MD</option><option value="VA"{' selected' if selected_state == 'VA' else ''}>VA</option></select>{field_error('state', 'job-state-error')}</label>
          <label for="job-zip-code">ZIP <input id="job-zip-code" name="zip_code" value="{escape(str(form.get('zip_code') or ''))}" pattern="[0-9]{{5}}" maxlength="5" inputmode="numeric" autocomplete="postal-code" list="job-zip-options" enterkeyhint="next" placeholder="20003" required{invalid('zip_code', 'job-zip-code-error')}>{field_error('zip_code', 'job-zip-code-error')}</label>
        </div>
        <datalist id="job-city-options">{dmv_city_options_html()}</datalist><datalist id="job-zip-options">{dmv_zip_options_html()}</datalist>
        <div class="project-step-actions"><button class="button secondary" type="button" data-project-back>Back</button><button class="button" type="button" data-project-next>Continue</button></div>
      </fieldset>
      <fieldset class="project-composer-step wide" data-project-step="5" data-step-title="Set timing and budget">
        <legend>When and around how much?</legend><p class="help-text">A budget is optional, but a realistic range helps contractors respond with a better fit.</p>
        <div class="project-field-grid three">
          <label for="job-desired-date">Desired date <span class="optional-label">Optional</span> <input id="job-desired-date" name="desired_date" type="date" value="{escape(str(form.get('desired_date') or ''))}"{invalid('desired_date', 'job-desired-date-error')}>{field_error('desired_date', 'job-desired-date-error')}</label>
          <label for="job-budget-min">Budget minimum <span class="optional-label">Optional</span> <input id="job-budget-min" name="budget_min" type="number" value="{escape(str(form.get('budget_min') or ''))}" min="0" max="{JOB_BUDGET_MAX}" step="1" inputmode="numeric" placeholder="500"{invalid('budget_min', 'job-budget-min-error')}>{field_error('budget_min', 'job-budget-min-error')}</label>
          <label for="job-budget-max">Budget maximum <span class="optional-label">Optional</span> <input id="job-budget-max" name="budget_max" type="number" value="{escape(str(form.get('budget_max') or ''))}" min="0" max="{JOB_BUDGET_MAX}" step="1" inputmode="numeric" placeholder="1000"{invalid('budget_max', 'job-budget-max-error')}>{field_error('budget_max', 'job-budget-max-error')}</label>
        </div>
        <div class="project-step-actions"><button class="button secondary" type="button" data-project-back>Back</button><button class="button" type="button" data-project-next>Review project</button></div>
      </fieldset>
      <fieldset class="project-composer-step wide" data-project-step="6" data-step-title="Review the project">
        <legend>Ready to send the signal?</legend>
        <dl class="project-review" aria-label="Project summary"><div><dt>Work</dt><dd data-review-service>Choose a service</dd></div><div><dt>Project</dt><dd data-review-title>Add a title</dd></div><div><dt>Setting</dt><dd data-review-setting>Not specified</dd></div><div><dt>Scope</dt><dd data-review-scope>Description only</dd></div><div><dt>Brief</dt><dd data-review-brief>Brief 0 of 6</dd></div><div><dt>Area</dt><dd data-review-location>Add a city and ZIP</dd></div><div><dt>Timing</dt><dd data-review-timing>Flexible</dd></div><div><dt>Budget</dt><dd data-review-budget>Open</dd></div></dl>
        {policy_panel}{photos_html}{turnstile}
        <div class="project-step-actions"><button class="button secondary" type="button" data-project-back>Back</button><button class="button" type="submit" aria-label="{escape(submit_label)}">{escape(submit_label)}</button></div>
      </fieldset>"""


def job_form_html(
    user,
    site_key: str = "",
    job=None,
    mode: str = "new",
    embedded: bool = False,
    saved_locations: list[dict] | None = None,
    repeat_invitation: dict | None = None,
) -> str:
    is_edit = mode == "edit" and job is not None
    job_id = int(row_value(job, "id", 0) or 0) if is_edit else 0
    if not is_edit:
        form = {
            "title": str(row_value(job, "title", "") or ""),
            "category": str(row_value(job, "category", "") or ""),
            "service_group_slug": str(row_value(job, "service_group_slug", "") or ""),
            "service_slug": str(row_value(job, "service_slug", "") or ""),
            "project_setting": str(row_value(job, "project_setting", "") or ""),
            "desired_date": str(row_value(job, "desired_date", "") or ""),
            "city": str(row_value(job, "city", "") or ""),
            "state": str(row_value(job, "state", "DC") or "DC"),
            "zip_code": str(row_value(job, "zip_code", "") or ""),
            "description": str(row_value(job, "description", "") or ""),
            "budget_min": str(row_value(job, "budget_min", "") or ""),
            "budget_max": str(row_value(job, "budget_max", "") or ""),
            "scope_answers": dict(row_value(job, "scope_answers", {}) or {}),
        }
        composer = project_composer_fields_html(
            form,
            include_photos=True,
            submit_label="Post project",
            cancel_url="/client/dashboard",
            turnstile=turnstile_html(site_key, "job-post"),
        )
        location_shortcuts = "".join(
            f'<a class="button secondary compact" href="/jobs/new?{urlencode({"location": int(location.get("id", 0) or 0)})}">{escape(location.get("label", ""))}</a>'
            for location in saved_locations or []
            if int(location.get("id", 0) or 0) > 0
        )
        location_launcher = (
            f"""
    <section class="saved-location-launcher" aria-labelledby="saved-location-launcher-title">
      <div><strong id="saved-location-launcher-title">Start with a saved area</strong><p class="help-text">Prefill the city and ZIP in step 4.</p></div>
      <div class="saved-location-shortcuts">{location_shortcuts}</div>
    </section>"""
            if location_shortcuts
            else ""
        )
        invitation_banner = ""
        invitation_fields = ""
        if repeat_invitation:
            invitation_banner = f"""
    <section class="repeat-invitation-banner" aria-label="Repeat provider invitation">
      <div><strong>Invite {escape(repeat_invitation.get('contractor_name', 'this contractor'))} again</strong><p>Post the same service as a new project. They may pass or send a fresh mini bid; no slot or approval is reserved.</p></div>
    </section>"""
            invitation_fields = f"""
      <input type="hidden" name="repeat_source_job_id" value="{int(repeat_invitation.get('source_job_id', 0) or 0)}">
      <input type="hidden" name="repeat_match_request_id" value="{int(repeat_invitation.get('source_match_request_id', 0) or 0)}">"""
        posting_intro = "" if embedded else """
    <section class="dashboard-header"><div><p class="eyebrow">Consumer workspace</p><h1>Post a project</h1></div><a class="button secondary" href="/client/dashboard">Projects</a></section>
    <ul class="form-checklist" aria-label="Posting safeguards"><li>City/ZIP pin</li><li>Private photos</li><li>Approve before chat</li></ul>"""
        body = f"""
    {posting_intro}
    {invitation_banner}
    {location_launcher}
    <form class="form-grid" data-dialog-fragment data-project-composer data-project-initial-step="{'3' if form.get('service_slug') else ('2' if form.get('service_group_slug') else '1')}" data-json-action="/api/jobs" data-upload-after-json-template="/api/media/jobs/{{job_id}}/upload" data-success-url-template="/client/jobs/{{id}}" aria-label="Post a project." aria-describedby="worker-form-status">
      {invitation_fields}
      {composer}
      <p id="worker-form-status" class="help-text wide" data-form-status aria-live="polite"></p>
    </form>"""
        return layout(
            user,
            "/jobs/new",
            "Post Project",
            body,
            include_actions=True,
            include_turnstile=bool(site_key),
            include_project_composer=True,
            body_class="dialog-fragment-body" if embedded else "",
        )
    selected_state = str(row_value(job, "state", "DC") or "DC")
    selected_setting = str(row_value(job, "project_setting", "") or "")
    project_setting_options = "\n".join(
        [
            '<option value="">Not specified</option>',
            *(
                f'<option value="{escape(setting["value"])}"{' selected' if setting["value"] == selected_setting else ''}>{escape(setting["label"])}</option>'
                for setting in PROJECT_SETTINGS
            ),
        ]
    )
    city_options = dmv_city_options_html()
    zip_options = dmv_zip_options_html()
    edit_scope_html = scope_questions_html(
        str(row_value(job, "service_slug", "") or ""),
        dict(row_value(job, "scope_answers", {}) or {}),
    )
    edit_policy = service_policy(str(row_value(job, "service_slug", "") or ""))
    edit_service_slug = str(row_value(job, "service_slug", "") or "")
    edit_service_group_slug = str(
        row_value(job, "service_group_slug", "") or ""
    )
    edit_category = str(row_value(job, "category", "") or "")
    edit_service_name = service_label(edit_service_slug, edit_category)
    edit_policy_html = ""
    if edit_policy["acknowledgement_required"] or edit_policy["emergency_disabled"]:
        edit_policy_html = f"""
      <section class="service-policy-advisory wide">
        <div><span class="eyebrow">{'Local rules check' if edit_policy['risk_tier'] == 'regulated' else 'Safety check'}</span><strong>Confirm before updating</strong><p>{escape(edit_policy['advisory'])}</p></div>
        <label class="service-policy-confirmation" for="job-service-policy-acknowledgement"><input id="job-service-policy-acknowledgement" type="checkbox" name="service_policy_acknowledgement" value="{escape(SERVICE_POLICY_VERSION)}" required><span>I understand that I must confirm qualifications, insurance, permits, and a safe work plan directly.</span></label>
      </section>"""
    body = f"""
    <section class="dashboard-header">
      <div>
        <p class="eyebrow">Consumer workspace</p>
        <h1>{'Edit project' if is_edit else 'Post a project'}</h1>
      </div>
      <a class="button secondary" href="{'/client/jobs/' + str(job_id) if is_edit else '/client/dashboard'}">{'Back to project' if is_edit else 'Projects'}</a>
    </section>
    <ul class="form-checklist" aria-label="Posting safeguards">
      <li>City/ZIP pin</li>
      <li>Private photos</li>
      <li>Approve before chat</li>
    </ul>
    <form class="form-grid" data-dialog-fragment data-json-action="{'/api/jobs/' + str(job_id) + '/update' if is_edit else '/api/jobs'}" data-upload-after-json-template="/api/media/jobs/{{job_id}}/upload" data-success-url-template="/client/jobs/{{id}}" aria-label="{'Edit project' if is_edit else 'Post a project.'}" aria-describedby="worker-form-status">
      <label class="wide" for="job-title">Project title <input id="job-title" name="title" value="{escape(str(row_value(job, 'title', '') or ''))}" maxlength="90" autocomplete="off" autocapitalize="sentences" spellcheck="true" enterkeyhint="next" placeholder="Power wash front steps and patio" required></label>
      <div class="service-family-context"><span><small>Service</small><strong>{escape(edit_service_name)}</strong><small>Post a new project to change the service bucket.</small></span></div>
      <input type="hidden" name="category" value="{escape(edit_category)}">
      <input type="hidden" name="service_group_slug" value="{escape(edit_service_group_slug)}">
      <input type="hidden" name="service_slug" value="{escape(edit_service_slug)}">
      <div class="wide">{edit_scope_html}</div>
      <label for="job-project-setting">Project setting <span class="optional-label">Optional</span> <select id="job-project-setting" name="project_setting">{project_setting_options}</select></label>
      <label for="job-desired-date">Desired date <input id="job-desired-date" name="desired_date" type="date" value="{escape(str(row_value(job, 'desired_date', '') or ''))}"></label>
      <label for="job-city">City <input id="job-city" name="city" value="{escape(str(row_value(job, 'city', '') or ''))}" maxlength="80" autocomplete="address-level2" autocapitalize="words" spellcheck="false" list="job-city-options" enterkeyhint="next" placeholder="Washington" required></label>
      <label for="job-state">State <select id="job-state" name="state" autocomplete="address-level1" required><option value="DC"{' selected' if selected_state == 'DC' else ''}>DC</option><option value="MD"{' selected' if selected_state == 'MD' else ''}>MD</option><option value="VA"{' selected' if selected_state == 'VA' else ''}>VA</option></select></label>
      <label for="job-zip-code">ZIP <input id="job-zip-code" name="zip_code" value="{escape(str(row_value(job, 'zip_code', '') or ''))}" pattern="[0-9]{{5}}" maxlength="5" inputmode="numeric" autocomplete="postal-code" list="job-zip-options" enterkeyhint="next" placeholder="20003" required></label>
      <datalist id="job-city-options">
{city_options}
      </datalist>
      <datalist id="job-zip-options">
{zip_options}
      </datalist>
      <label for="job-budget-min">Budget minimum <span class="optional-label">Optional</span> <input id="job-budget-min" name="budget_min" type="number" value="{escape(str(row_value(job, 'budget_min', '') if row_value(job, 'budget_min') is not None else ''))}" min="0" max="{JOB_BUDGET_MAX}" step="1" inputmode="numeric" placeholder="500"></label>
      <label for="job-budget-max">Budget maximum <span class="optional-label">Optional</span> <input id="job-budget-max" name="budget_max" type="number" value="{escape(str(row_value(job, 'budget_max', '') if row_value(job, 'budget_max') is not None else ''))}" min="0" max="{JOB_BUDGET_MAX}" step="1" inputmode="numeric" placeholder="1000"></label>
      <label class="wide" for="job-description">Description <textarea id="job-description" name="description" rows="5" minlength="20" maxlength="1200" autocapitalize="sentences" spellcheck="true" enterkeyhint="done" placeholder="Scope, access, timing, and desired outcome." aria-describedby="job-description-help" required>{escape(str(row_value(job, 'description', '') or ''))}</textarea><span id="job-description-help" class="help-text">Do not include an exact street address, email, or phone number.</span></label>
      {edit_policy_html}
      <label class="wide" for="job-photos">Photos <input id="job-photos" name="photos" type="file" accept="image/png,image/jpeg,image/gif,image/webp" multiple aria-describedby="job-photos-help"></label>
      <p id="job-photos-help" class="help-text wide">Private uploads. PNG, JPG, GIF, or WebP.</p>
      {turnstile_html(site_key, "job-post")}
      <div class="form-actions wide">
        <button class="button" type="submit" aria-label="{'Save project changes' if is_edit else 'Post project'}">{'Save changes' if is_edit else 'Post project'}</button>
        <p id="worker-form-status" class="help-text" data-form-status aria-live="polite"></p>
      </div>
    </form>"""
    return layout(
        user,
        f"/client/jobs/{job_id}/edit" if is_edit else "/jobs/new",
        "Edit Project" if is_edit else "Post Project",
        body,
        include_actions=True,
        include_turnstile=bool(site_key),
        body_class="dialog-fragment-body" if embedded else "",
    )


def public_job_draft_html(
    form: dict | None = None,
    errors: list[str] | None = None,
    site_key: str = "",
    embedded: bool = False,
) -> str:
    form = form or {}
    errors = errors or []
    summary = ""
    if errors:
        items = "".join(f"<li>{escape(message)}</li>" for message in errors)
        summary = f'<section id="job-form-errors" class="form-error-summary wide" role="alert"><h2>Fix {len(errors)} item{"" if len(errors) == 1 else "s"}</h2><ul>{items}</ul></section>'
    composer = project_composer_fields_html(
        form,
        errors=errors,
        include_photos=False,
        submit_label="Save draft and verify email",
        cancel_url="/",
        turnstile=turnstile_html(site_key, "job-draft"),
    )
    posting_intro = "" if embedded else """
    <section class="page-header"><p class="eyebrow">Consumer workspace</p><h1>What needs doing?</h1><p>Start the project now. Verify your email before it goes live.</p></section>
    <ul class="form-checklist" aria-label="Project draft steps"><li>Save scope</li><li>Verify email</li><li>Add private photos</li></ul>"""
    body = f"""
    {posting_intro}
    <form class="form-grid" method="post" action="/post-project" aria-label="Project draft" data-dialog-fragment data-project-composer data-project-initial-step="{'3' if form.get('service_slug') else ('2' if form.get('service_group_slug') else '1')}">
      {summary}{composer}
    </form>"""
    return layout(
        None,
        "/post-project",
        "Post Project",
        body,
        include_turnstile=bool(site_key),
        include_project_composer=True,
        body_class="dialog-fragment-body" if embedded else "",
    )


def contractor_profile_html(
    user,
    profile: dict,
    photos: list[dict] | None = None,
    credentials: list[dict] | None = None,
    preferences: dict | None = None,
) -> str:
    preferences = preferences or {}
    selected_services = set(normalize_service_slugs(profile.get("service_slugs")))
    selected_zones = set(normalize_zone_slugs(profile.get("service_zone_slugs")))
    if not selected_services:
        selected_services = set(infer_service_slugs_from_trades(profile.get("trades")))
    if not selected_zones:
        selected_zones = set(infer_zone_slugs_from_area(profile.get("service_area")))
    service_group_rows = []
    service_index = 0
    for group_index, group in enumerate(SERVICE_GROUPS, start=1):
        service_options = []
        group_selected = any(
            service[0] in selected_services for service in group["services"]
        )
        open_attribute = " open" if group_selected or (not selected_services and group_index == 1) else ""
        for service_slug, service_name, _category in group["services"]:
            service_index += 1
            service_options.append(
                f'<label for="profile-trade-{service_index}"><input id="profile-trade-{service_index}" type="checkbox" name="service_slugs" value="{escape(service_slug)}"{" checked" if service_slug in selected_services else ""}><span>{escape(service_name)}</span></label>'
            )
        service_group_rows.append(
            f"""
        <details class="profile-service-family"{open_attribute}>
          <summary class="profile-service-family-heading">
            <span class="profile-service-family-summary">
              <span class="profile-service-family-icon" aria-hidden="true"><span>{group_index:02d}</span><img src="/vendor/tabler-icons/{escape(group['icon'])}" alt="" width="28" height="28"></span>
              <span><strong id="profile-service-family-{escape(group['slug'])}">{escape(group['name'])}</strong><small>{escape(group['description'])}</small></span>
            </span>
          </summary>
          <div class="profile-service-options">{''.join(service_options)}</div>
        </details>"""
        )
    zone_options = "".join(
        f'<label for="profile-zone-{index}"><input id="profile-zone-{index}" type="checkbox" name="service_zone_slugs" value="{escape(zone["slug"])}"{" checked" if zone["slug"] in selected_zones else ""}><span><strong>{escape(zone["short_name"])}</strong><small>{escape(zone["state"])}</small></span></label>'
        for index, zone in enumerate(DMV_SERVICE_ZONES, start=1)
    )
    years = profile.get("years_in_business")
    years_value = "" if years is None else str(years)
    contractor_id = int(row_value(user, "id", 0) or 0)
    readiness = contractor_profile_readiness(profile, photos)
    readiness_steps = "".join(
        f'<li class="{"complete" if item["complete"] else ""}"><a href="#{escape(item["target"])}"><span>{index:02d}</span>{escape(item["label"])}</a></li>'
        for index, item in enumerate(readiness["items"], start=1)
    )
    photo_html = "\n".join(
        f'<figure><img src="/media/contractors/{int(photo.get("id", 0) or 0)}" alt="Portfolio photo"><figcaption>{escape(photo.get("original_filename", ""))}</figcaption></figure>'
        for photo in photos or []
    )
    if not photo_html:
        photo_html = """
        <div class="empty-state">
          <h2>No portfolio photos yet</h2>
          <p class="help-text">Add one clear example of recent work when R2 uploads are configured.</p>
        </div>"""
    credential_type_options = "".join(
        f'<option value="{escape(value)}">{escape(label)}</option>'
        for value, label in CREDENTIAL_TYPES
    )
    credential_jurisdiction_options = "".join(
        f'<option value="{escape(value)}">{escape(label)}</option>'
        for value, label in CREDENTIAL_JURISDICTIONS
    )
    credential_rows = []
    for credential in credentials or []:
        credential_id = int(credential.get("id", 0) or 0)
        expiry = credential.get("expires_at", "")
        expiry_text = f" - expires {escape(str(expiry))}" if expiry else ""
        note = credential.get("review_note", "")
        note_html = f'<small>{escape(note)}</small>' if note else ""
        if credential.get("status") in {"self_reported", "pending", "rejected"}:
            action_html = f"""
            <form data-json-action="/api/contractor/credentials/{credential_id}/remove" data-success-url-template="/contractor/profile#credential-claims" aria-label="Remove credential claim" aria-describedby="credential-remove-status-{credential_id}">
              <button class="button secondary compact" type="submit">Remove</button>
              <span id="credential-remove-status-{credential_id}" class="sr-only" data-form-status aria-live="polite"></span>
            </form>"""
        else:
            action_html = f'<span class="status {escape(credential.get("status", ""))}">{escape(credential.get("status_label", ""))}</span>'
        credential_rows.append(
            f"""
            <div class="admin-row credential-row">
              <span><strong>{escape(credential.get('credential_type_label', 'Credential'))} - {escape(credential.get('jurisdiction_label', ''))}</strong><small>{escape(credential.get('claimed_identifier', ''))} - {escape(credential.get('status_label', 'Awaiting review'))}{expiry_text}</small>{note_html}</span>
              {action_html}
            </div>"""
        )
    if not credential_rows:
        credential_rows.append('<p class="empty">No credential claims submitted.</p>')
    availability_options = "".join(
        f'<option value="{escape(value)}"{" selected" if preferences.get("availability_status", "available") == value else ""}>{escape(label)}</option>'
        for value, label in AVAILABILITY_OPTIONS
    )
    # Bandit B608 mistakes this HTML template for a SQL statement.
    body = f"""
    <section class="dashboard-header">
      <div>
        <p class="eyebrow">Contractor profile</p>
        <h1>Profile setup</h1>
        <p>Clients see this when they review your mini bid.</p>
      </div>
      <a class="button secondary" href="/contractors/{contractor_id}">Preview</a>
    </section>
    <nav class="profile-task-links" aria-label="Profile tasks">
      <a href="#work-availability"><img src="/static/vendor/tabler-icons/home-up.svg" alt="">Availability</a>
      <a href="#profile-details"><img src="/static/vendor/tabler-icons/tool.svg" alt="">Profile details</a>
      <a href="#credential-claims"><img src="/static/vendor/tabler-icons/home-check.svg" alt="">Credentials</a>
    </nav>
    <section class="profile-readiness" aria-labelledby="profile-readiness-title">
      <details{' open' if readiness['percent'] < 100 else ''}>
        <summary class="profile-readiness-head">
          <div><p class="eyebrow">Storefront readiness</p><h2 id="profile-readiness-title">{readiness['complete_count']} of {readiness['total_count']} ready</h2></div>
          <strong>{readiness['percent']}%</strong>
        </summary>
        <div class="profile-readiness-body">
          <progress value="{readiness['complete_count']}" max="{readiness['total_count']}">{readiness['percent']}%</progress>
          <ol class="profile-readiness-steps">{readiness_steps}</ol>
        </div>
      </details>
    </section>
    <section id="work-availability" class="preference-band" aria-labelledby="work-availability-title">
      <div><p class="eyebrow">Work status</p><h2 id="work-availability-title">Availability</h2><p class="help-text">This self-reported status is shown on your contractor profile. Update it whenever your schedule changes.</p></div>
      <form class="preference-form" data-json-action="/api/contractor/preferences/availability" data-success-url-template="/contractor/profile#work-availability" aria-describedby="availability-form-status">
        <label for="availability-status">Status <select id="availability-status" name="availability_status">{availability_options}</select></label>
        <label for="available-from">Next available date (optional) <input id="available-from" name="available_from" type="date" value="{escape(preferences.get('available_from', ''))}"></label>
        <button class="button secondary" type="submit">Update availability</button>
        <span id="availability-form-status" class="sr-only" data-form-status aria-live="polite"></span>
      </form>
    </section>
    <section id="credential-claims" class="detail-grid credential-management" aria-labelledby="credential-claims-title">
      <form class="panel stack-form" data-json-action="/api/contractor/credentials" data-success-url-template="/contractor/profile#credential-claims" aria-label="Submit credential claim" aria-describedby="credential-claim-status">
        <div><p class="eyebrow">Trust record</p><h2 id="credential-claims-title">Submit a credential claim</h2><p class="help-text">Workdoe shows a public label only after an administrator checks the linked source. This is not an endorsement of skill, safety, or legal eligibility.</p></div>
        <label for="credential-type">Credential <select id="credential-type" name="credential_type" required><option value="">Choose one</option>{credential_type_options}</select></label>
        <label for="credential-jurisdiction">Jurisdiction <select id="credential-jurisdiction" name="jurisdiction" required><option value="">Choose one</option>{credential_jurisdiction_options}</select></label>
        <label for="credential-identifier">Record identifier <input id="credential-identifier" name="claimed_identifier" maxlength="{CREDENTIAL_IDENTIFIER_MAX_LENGTH}" autocomplete="off" spellcheck="false" required></label>
        <label for="credential-name">Name on record (optional) <input id="credential-name" name="claimed_name" maxlength="{CREDENTIAL_NAME_MAX_LENGTH}" autocomplete="organization" autocapitalize="words"></label>
        <label for="credential-source">Public source (optional) <input id="credential-source" name="source_url" type="url" maxlength="300" placeholder="https://..." autocomplete="url" autocapitalize="off" spellcheck="false"><span class="help-text">A regulator, insurer, or public registry page helps the review.</span></label>
        <label for="credential-expiry">Expiration (optional) <input id="credential-expiry" name="expires_at" type="date"></label>
        <button class="button" type="submit">Send for review</button>
        <p id="credential-claim-status" class="help-text" data-form-status aria-live="polite"></p>
      </form>
      <section class="panel" aria-labelledby="credential-status-title"><h2 id="credential-status-title">Your claims</h2>{''.join(credential_rows)}</section>
    </section>
    <form id="profile-details" class="form-grid" data-json-action="/api/contractor/profile" data-success-url-template="/contractor/profile" aria-label="Contractor profile" aria-describedby="profile-form-status">
      <input type="hidden" name="market_fit_version" value="1">
      <label class="wide" for="profile-business-name">Business name <input id="profile-business-name" name="business_name" value="{escape(profile.get('business_name', ''))}" maxlength="120" autocomplete="organization" autocapitalize="words" spellcheck="false" enterkeyhint="next" required></label>
      <fieldset class="wide profile-service-selector" id="profile-trades">
        <legend>Services you take on</legend>
        <p class="help-text">Choose the specific work you want Workdoe to match.</p>
        <div class="profile-service-groups">{''.join(service_group_rows)}</div>
      </fieldset>
      <fieldset class="wide profile-zone-selector" id="profile-service-area">
        <legend>Where you work</legend>
        <p class="help-text">Pick practical DMV coverage areas. Exact project addresses stay private until a match is approved.</p>
        <div class="profile-zone-options">{zone_options}</div>
      </fieldset>
      <label for="profile-years-in-business">Years in business <input id="profile-years-in-business" name="years_in_business" type="number" min="0" max="100" value="{escape(years_value)}" inputmode="numeric" enterkeyhint="next"></label>
      <label for="profile-insurance-status">Insurance note (self-reported) <input id="profile-insurance-status" name="insurance_status" value="{escape(profile.get('insurance_status', ''))}" maxlength="120" autocapitalize="sentences" spellcheck="true" enterkeyhint="next" placeholder="Available on request"></label>
      <label for="profile-license-number">License note (self-reported) <input id="profile-license-number" name="license_number" value="{escape(profile.get('license_number', ''))}" maxlength="80" autocapitalize="characters" spellcheck="false" enterkeyhint="next" placeholder="Optional for the local beta"></label>
      <label for="profile-website">Website <input id="profile-website" name="website" type="url" value="{escape(profile.get('website', ''))}" maxlength="200" autocomplete="url" autocapitalize="off" spellcheck="false" enterkeyhint="next" placeholder="https://example.com" aria-describedby="profile-website-help"><span id="profile-website-help" class="help-text">Visible to clients reviewing your bid. Public HTTPS websites only.</span></label>
      <label class="wide" for="profile-intro">Intro <textarea id="profile-intro" name="intro" rows="5" minlength="20" maxlength="900" autocapitalize="sentences" spellcheck="true" enterkeyhint="done" placeholder="Describe your crew, service style, and ideal jobs." required>{escape(profile.get('intro', ''))}</textarea></label>
      <div class="form-actions wide">
        <button class="button" type="submit">Save profile</button>
        <p id="profile-form-status" class="help-text" data-form-status aria-live="polite"></p>
      </div>
    </form>
    <section class="detail-grid">
      <form class="panel stack-form" data-file-action="/api/media/contractors/{contractor_id}/upload" data-success-url-template="/contractor/profile" enctype="multipart/form-data" aria-label="Upload portfolio photo" aria-describedby="profile-upload-status">
        <h2>Portfolio photo</h2>
        <label for="profile-photos">Image <input id="profile-photos" name="portfolio_photo" type="file" accept="image/png,image/jpeg,image/gif,image/webp" aria-describedby="profile-photos-help" required></label>
        <p id="profile-photos-help" class="help-text">Private uploads. PNG, JPG, GIF, or WebP.</p>
        <button class="button secondary" type="submit" aria-label="Upload portfolio photo">Upload photo</button>
        <p id="profile-upload-status" class="help-text" data-form-status aria-live="polite"></p>
      </form>
      <section class="photo-grid profile-photos" aria-label="Portfolio photos">
{photo_html}
      </section>
    </section>"""  # nosec B608
    return layout(user, "/contractor/profile", "Contractor Profile", body, include_actions=True)


def public_contractor_profile_html(user, payload: dict) -> str:
    contractor = payload.get("contractor", {})
    photos = contractor.get("photos", [])
    services = contractor.get("services", [])
    service_zones = contractor.get("service_zones", [])
    contractor_id = int(contractor.get("id", 0) or 0)
    photo_html = "\n".join(
        f'<figure><img src="{escape(photo.get("url", ""))}" alt="Portfolio photo {index}"><figcaption>Portfolio photo {index}</figcaption></figure>'
        for index, photo in enumerate(photos, start=1)
    )
    years = contractor.get("years_in_business")
    year_label = "Not listed" if years in {"", None} else str(years)
    status_html = (
        f'<span class="status {escape(contractor.get("status", ""))}">{escape(contractor.get("status", ""))}</span>'
        if contractor.get("status")
        else ""
    )
    service_summary = ", ".join(
        str(service.get("name", "")) for service in services if service.get("name")
    ) or contractor.get("trades", "DMV contractor")
    service_tags = "".join(
        f'<span>{escape(service.get("name", ""))}</span>'
        for service in services
        if service.get("name")
    )
    service_block = (
        f'<section class="profile-capability-block" aria-labelledby="profile-services-title"><h3 id="profile-services-title">Services</h3><div class="profile-tag-list">{service_tags}</div></section>'
        if service_tags
        else ""
    )
    zone_tags = "".join(
        f'<span>{escape(zone.get("short_name", ""))}</span>'
        for zone in service_zones
        if zone.get("short_name")
    )
    if not zone_tags:
        zone_tags = f'<span>{escape(contractor.get("service_area", "DMV area"))}</span>'
    coverage_label = (
        f"{len(service_zones)} service areas" if service_zones else "Service area"
    )
    coverage_html = (
        f'<details class="profile-coverage"><summary>{coverage_label}</summary>'
        f'<div class="profile-tag-list">{zone_tags}</div></details>'
    )
    availability = contractor.get("availability", {})
    website_html = ""
    if contractor.get("website") and contractor.get("website_label"):
        website_html = (
            f'<p class="profile-website"><a href="{escape(contractor["website"])}" '
            f'target="_blank" rel="noopener noreferrer nofollow external" '
            f'aria-label="Visit {escape(contractor["website_label"])} (opens in a new tab)">'
            f'Visit {escape(contractor["website_label"])}</a>'
            '<span>Contractor-provided website</span></p>'
        )
    credential_rows = []
    for credential in contractor.get("credentials", []):
        checked_at = str(credential.get("checked_at", ""))[:10]
        expires_at = credential.get("expires_at", "")
        expiry_text = f" - expires {escape(str(expires_at))}" if expires_at else ""
        source_html = (
            f'<a href="{escape(credential.get("source_url", ""))}" target="_blank" rel="noopener noreferrer nofollow external">Public source</a>'
            if credential.get("source_url")
            else ""
        )
        credential_rows.append(
            f'<div class="admin-row credential-row"><span><strong>{escape(credential.get("credential_type_label", "Credential"))} - {escape(credential.get("jurisdiction_label", ""))}</strong><small>Source checked {escape(checked_at)}{expiry_text}</small></span>{source_html}</div>'
        )
    credentials_html = (
        '<section class="profile-capability-block public-credential-records" aria-labelledby="public-credentials-title"><h3 id="public-credentials-title">Source-checked records</h3>'
        + (
            "".join(credential_rows)
            if credential_rows
            else '<p class="empty compact-empty">No current source-checked record is shown.</p>'
        )
        + "</section>"
    )
    reputation = contractor.get("reputation", {})
    reviewed_records = ", ".join(
        str(signal.get("label", ""))
        for signal in reputation.get("credential_signals", [])
        if signal.get("label")
    ) or "None shown"
    completed_count = int(contractor.get("verified_completions", 0) or 0)
    completed_label = f"{completed_count} project{'s' if completed_count != 1 else ''}"
    choice_context = contractor.get("choice_context") or {}
    role = str(row_value(user, "role", "") or "")
    include_actions = False
    if choice_context:
        decision_action = ""
        if choice_context.get("can_choose"):
            include_actions = True
            decision_action = f"""
          <form data-json-action="/api/match-requests/{int(choice_context.get('request_id', 0) or 0)}/approve" data-success-url-template="/client/jobs/{int(choice_context.get('job_id', 0) or 0)}" aria-describedby="profile-choice-status">
            <button class="button" type="submit" aria-label="Choose {escape(contractor.get('business_name', 'contractor'))} for {escape(choice_context.get('job_title', 'project'))}">Choose contractor</button>
            <span id="profile-choice-status" class="form-status" role="status" aria-live="polite"></span>
          </form>"""
        elif choice_context.get("thread_url"):
            decision_action = f'<a class="button" href="{escape(choice_context.get("thread_url", ""))}">Message contractor</a>'
        profile_actions_html = f"""
    <section class="profile-decision-bar" aria-labelledby="profile-decision-title">
      <div><p class="eyebrow">Project choice</p><h2 id="profile-decision-title">{escape(choice_context.get('job_title', 'Project'))}</h2><p>Review this contractor's profile without losing your place in the offers.</p></div>
      <div class="profile-decision-actions"><a class="button secondary" href="{escape(choice_context.get('back_url', '/client/dashboard'))}">Back to offers</a>{decision_action}</div>
    </section>"""
    else:
        if not user:
            action_url = f"/login?next=/contractors/{contractor_id}"
            action_label = "Sign in"
            action_class = "button"
        elif role == "client":
            action_url = "/client/dashboard"
            action_label = "Back to projects"
            action_class = "button secondary"
        elif role == "contractor" and int(row_value(user, "id", 0) or 0) == contractor_id:
            action_url = "/contractor/profile"
            action_label = "Edit profile"
            action_class = "button"
        elif role == "contractor":
            action_url = "/leads"
            action_label = "Back to leads"
            action_class = "button secondary"
        else:
            action_url = "/admin"
            action_label = "Back to moderation"
            action_class = "button secondary"
        profile_actions_html = f'<div class="lead-action-bar public-profile-actions"><a class="{action_class}" href="{action_url}">{action_label}</a></div>'
    portfolio_html = ""
    if photo_html:
        portfolio_html = f"""
    <section class="work-history profile-portfolio" aria-labelledby="profile-portfolio-title">
      <div class="section-heading"><div><p class="eyebrow">Past work</p><h2 id="profile-portfolio-title">Portfolio</h2></div><span class="count-pill">{len(photos)}</span></div>
      <div class="photo-grid profile-photos">{photo_html}</div>
    </section>"""
    completed_work_reviews = contractor.get("completed_work_reviews", [])
    reviews_html = ""
    if completed_work_reviews:
        review_rows = "".join(
            f'<p class="row-meta"><span>{escape(review.get("service_name", "Completed project"))}</span></p>'
            + match_review_card_html(
                review,
                user,
                f"/contractors/{contractor_id}#completed-feedback",
            )
            for review in completed_work_reviews
        )
        reviews_html = f"""
    <section id="completed-feedback" class="work-history completed-feedback-profile" aria-labelledby="completed-feedback-title">
      <div class="section-heading history-heading"><div><p class="eyebrow">Verified projects</p><h2 id="completed-feedback-title">Completed-work feedback</h2></div><span class="count-pill">{len(completed_work_reviews)}</span></div>
      <p class="help-text">Structured feedback from Workdoe-completed projects. No star score or paid ranking is created.</p>
      <div class="review-list">{review_rows}</div>
    </section>"""
    body = f"""
    <section class="dashboard-header public-profile-header">
      <div>
        <p class="eyebrow">Contractor profile</p>
        <h1>{escape(contractor.get('business_name', 'Workdoe contractor'))}</h1>
        <p>{escape(service_summary)}</p>
      </div>
      {status_html}
    </section>
    {profile_actions_html}
    <section class="public-profile-trust" aria-labelledby="public-trust-title">
      <div class="section-heading"><div><p class="eyebrow">Contractor signals</p><h2 id="public-trust-title">Work history and records</h2></div></div>
      <dl class="profile-facts public-profile-facts">
        <div><dt>Availability</dt><dd><span class="availability-label {escape(availability.get('status', 'available'))}">{escape(availability.get('label', 'Available for new work'))}</span><small>Self-reported</small></dd></div>
        <div><dt>Workdoe-completed</dt><dd>{escape(completed_label)}<small>Both sides confirmed</small></dd></div>
        <div><dt>Years active</dt><dd>{escape(year_label)}<small>Self-reported</small></dd></div>
        <div><dt>Reviewed records</dt><dd>{escape(reviewed_records)}<small>Current public sources only</small></dd></div>
      </dl>
      {contractor_reputation_html(reputation, 'public-reputation-title')}
      {credentials_html}
      <p class="help-text">Profile details are self-reported. A source-checked record means Workdoe reviewed the linked public source on the date shown; it is not a guarantee of skill, safety, coverage, or legal eligibility.</p>
    </section>
    <section class="detail-grid public-profile-details">
      <article class="panel">
        <h2>About</h2>
        <p class="preline">{escape(contractor.get('intro', ''))}</p>
        {website_html}
        {service_block}
        {coverage_html}
      </article>
      <aside class="panel">
        <h2>Contact policy</h2>
        <p>{escape(contractor.get('contact_policy', 'Clients approve a mini bid before messaging opens.'))}</p>
      </aside>
    </section>
    {reviews_html}
    {portfolio_html}"""
    return layout(
        user,
        f"/contractors/{contractor_id}",
        contractor.get("business_name", "Contractor Profile"),
        body,
        include_actions=include_actions,
    )


def message_threads_html(user, payload: dict) -> str:
    threads = payload.get("threads", [])
    stats = payload.get("stats", {})
    thread_view = payload.get("view", "all")
    role = str(row_value(user, "role", "") or "")
    rows = []
    for thread in threads:
        unread_count = int(thread.get("unread_count", 0) or 0)
        unread_label = f", {unread_count} unread" if unread_count else ""
        unread_chip = (
            f'<span class="unread-chip">{unread_count} new</span>'
            if unread_count
            else ""
        )
        other_name = (
            thread.get("contractor_name", "Contractor")
            if role == "client"
            else thread.get("client_name", "Client")
        )
        rows.append(
            f"""
    <a class="job-row link-row{' has-unread' if unread_count else ''}" href="{escape(thread.get('url', '#'))}" aria-label="Open message thread for {escape(thread.get('title', 'message thread'))}{unread_label}">
      <span>
        <span class="row-meta">
          <span>{escape(thread.get('category', ''))}</span>
          <span>{escape(thread.get('city', ''))}, {escape(thread.get('state', ''))}</span>
          <span>{escape(message_count_label(thread.get('message_count', 0)))}</span>
          {unread_chip}
        </span>
        <strong>{escape(thread.get('title', 'Message thread'))}</strong>
        <small class="thread-participants">With {escape(other_name)}</small>
        <small class="thread-preview">{escape(thread.get('last_message') or 'No messages yet')}</small>
      </span>
      <span class="button secondary compact">{'Read' if unread_count else 'Open'}</span>
    </a>"""
        )
    thread_html = "\n".join(rows) if rows else (
        empty_state("No unread messages", "/messages", "View all messages")
        if thread_view == "unread"
        else empty_state("No message threads yet", "/dashboard", "Back to dashboard")
    )
    tabs_html = "".join(
        (
            f'<a class="work-view-tab{" is-active" if thread_view == value else ""}" '
            f'href="{href}"{" aria-current=\"page\"" if thread_view == value else ""}>'
            f'<span>{label}</span><strong>{count}</strong></a>'
        )
        for value, label, href, count in (
            ("all", "All", "/messages", int(stats.get("threads", 0))),
            (
                "unread",
                "Unread",
                "/messages?view=unread",
                int(stats.get("unread_threads", 0)),
            ),
        )
    )
    body = f"""
    <section class="page-header">
      <p class="eyebrow">Approved matches</p>
      <h1>Messages</h1>
    </section>
    <nav class="work-view-tabs message-view-tabs" aria-label="Message thread view">{tabs_html}</nav>
    <section class="job-list" aria-label="Message threads">
{thread_html}
    </section>"""
    return layout(user, "/messages", "Messages", body)


def message_thread_detail_html(user, payload: dict, can_reply: bool = True) -> str:
    thread = payload.get("thread", {})
    messages = payload.get("messages", [])
    thread_id = int(thread.get("id", 0) or 0)
    user_id = int(row_value(user, "id", 0) or 0)
    role = str(row_value(user, "role", "") or "")
    job_id = int(thread.get("job_id", 0) or 0)
    project_href = (
        f"/client/jobs/{job_id}" if role == "client" else f"/jobs/{job_id}"
    )
    project_link = (
        f'<a class="button secondary compact" href="{project_href}">View project</a>'
        if can_reply and job_id
        else ""
    )
    message_rows = []
    for message in messages:
        is_mine = int(message.get("sender_id", 0) or 0) == user_id
        is_hidden = bool(message.get("is_hidden"))
        message_rows.append(
            f"""
      <article class="message{' mine' if is_mine else ''}{' is-hidden' if is_hidden else ''}">
        <div class="message-meta">
          <strong>{escape(message.get('sender_name', 'Workdoe user'))}</strong>
          <span>{'<span class="status hidden">hidden</span>' if is_hidden else ''} {escape(message.get('created_at', ''))}</span>
        </div>
        <p class="preline">{escape(message.get('body', ''))}</p>
      </article>"""
        )
    messages_html = "\n".join(message_rows) if message_rows else '<p class="empty">No messages yet.</p>'
    reply_html = ""
    if can_reply:
        reply_html = f"""
    <form class="message-form thread-message-form" data-json-action="/api/messages/threads/{thread_id}" data-success-url-template="/messages/{thread_id}" aria-label="New message" aria-describedby="message-reply-status">
      <label for="message-body">New message <textarea id="message-body" name="body" rows="4" maxlength="1000" placeholder="Share timing, access, or next steps." autocapitalize="sentences" spellcheck="true" enterkeyhint="send" required></textarea></label>
      <button class="button full" type="submit" aria-label="Send message">Send</button>
      <p id="message-reply-status" class="help-text" data-form-status aria-live="polite"></p>
    </form>"""
    body = f"""
    <section class="dashboard-header">
      <div>
        <p class="eyebrow">Private thread</p>
        <h1>{escape(thread.get('title', 'Message thread'))}</h1>
        <div class="row-meta thread-meta">
          <span>{escape(thread.get('client_name', 'Client'))} and {escape(thread.get('contractor_name', 'Contractor'))}</span>
          <span>{escape(thread.get('category', ''))}</span>
          <span>{escape(thread.get('city', ''))}, {escape(thread.get('state', ''))}</span>
          <span>{escape(message_count_label(len(messages)))}</span>
        </div>
      </div>
      <a class="button secondary" href="/messages">All messages</a>
    </section>
    <section class="message-shell thread-message-shell">
      <aside class="thread-match-context" aria-label="Approved match summary">
        <p class="eyebrow">Approved match</p>
        {project_link}
        <dl class="thread-match-facts">
          <div><dt>Price</dt><dd>{escape(thread.get('price_range') or 'Not provided')}</dd></div>
          <div><dt>Timeline</dt><dd>{escape(thread.get('timeline') or 'Not provided')}</dd></div>
          <div><dt>Availability</dt><dd>{escape(thread.get('availability') or 'Not provided')}</dd></div>
        </dl>
      </aside>
      <div class="message-list thread-message-list">
{messages_html}
      </div>
      {reply_html}
    </section>"""
    return layout(user, f"/messages/{thread_id}", "Message Thread", body, include_actions=can_reply)


def admin_action_form(action_url: str, label: str) -> str:
    status_id = f"admin-action-{dom_id_fragment(action_url)}-status"
    return f"""
        <form data-json-action="{escape(action_url)}" data-success-url-template="/admin" aria-label="{escape(label)}" aria-describedby="{status_id}">
          <button class="button secondary compact" type="submit">{escape(label)}</button>
          <span id="{status_id}" class="sr-only" data-form-status aria-live="polite"></span>
        </form>"""


def admin_row(title: str, meta: str, action_url: str = "", action_label: str = "", review_url: str = "") -> str:
    actions = []
    if review_url:
        actions.append(f'<a class="button secondary compact" href="{escape(review_url)}">Review</a>')
    if action_url and action_label:
        actions.append(admin_action_form(action_url, action_label))
    action_html = f'<div class="row-actions">{"".join(actions)}</div>' if actions else ""
    return f"""
      <div class="admin-row">
        <span><strong>{escape(title)}</strong><small>{escape(meta)}</small></span>
        {action_html}
      </div>"""


def admin_panel(title: str, rows: list[str], empty_message: str) -> str:
    content = "\n".join(rows) if rows else f'<p class="empty">{escape(empty_message)}</p>'
    return f"""
    <article class="panel admin-panel">
      <h2>{escape(title)}</h2>
{content}
    </article>"""


def admin_report_label(report: dict) -> tuple[str, str]:
    target_type = report.get("target_type", "")
    target_id = report.get("target_id", "")
    if target_type == "job" and report.get("job_title"):
        return f"Job: {report.get('job_title')}", f"{report.get('reason', '')} - {report.get('reporter_email', '')}"
    if target_type == "message" and report.get("message_job_title"):
        return f"Message: {report.get('message_job_title')}", f"{report.get('reason', '')} - {report.get('reporter_email', '')}"
    if target_type == "profile" and report.get("profile_business_name"):
        return f"Profile: {report.get('profile_business_name')}", f"{report.get('reason', '')} - {report.get('reporter_email', '')}"
    return f"{target_type} #{target_id}", f"{report.get('reason', '')} - {report.get('reporter_email', '')}"


def admin_report_review_url(report: dict) -> str:
    target_type = report.get("target_type", "")
    if target_type == "job":
        return f"/jobs/{int(report.get('target_id', 0) or 0)}"
    if target_type == "message" and report.get("message_thread_id"):
        return f"/messages/{int(report.get('message_thread_id', 0) or 0)}"
    if target_type == "profile":
        return f"/contractors/{int(report.get('target_id', 0) or 0)}"
    return ""


def admin_dashboard_html(user, payload: dict) -> str:
    stats = payload.get("stats", {})
    marketplace = payload.get("marketplace_metrics", {})
    pilot = payload.get("pilot_metrics", {})
    pilot_summary = pilot.get("summary", {})
    repeat_work = payload.get("repeat_work_metrics", {})
    lead_alerts = payload.get("lead_alert_metrics", {})
    match_reviews = payload.get("match_review_metrics", {})
    pilot_rows = []
    allowed_pilot_states = {
        "supply-gap",
        "needs-response",
        "verified",
        "matched",
        "receiving-bids",
        "no-demand",
    }
    for cell in pilot.get("cells", []):
        state = str(cell.get("state", "receiving-bids"))
        if state not in allowed_pilot_states:
            state = "receiving-bids"
        pilot_rows.append(
            f"""
            <article class="pilot-cell-row" role="listitem">
              <header class="pilot-cell-heading">
                <div>
                  <p class="pilot-cell-week">Week of {escape(cell.get('week_start', ''))}</p>
                  <h3>{escape(cell.get('service_name', 'Unclassified service'))}</h3>
                  <p>{escape(cell.get('zone_name', 'Unclassified zone'))}</p>
                </div>
                <span class="pilot-state pilot-state--{state}">{escape(cell.get('state_label', 'Receiving bids'))}</span>
              </header>
              <dl class="pilot-cell-facts">
                <div><dt>Published</dt><dd>{int(cell.get('published_projects', 0) or 0)}</dd></div>
                <div><dt>Brief ready</dt><dd>{int(cell.get('brief_ready_projects', 0) or 0)}/{int(cell.get('published_projects', 0) or 0)} <small>{int(cell.get('brief_ready_rate', 0) or 0)}%</small></dd></div>
                <div><dt>With bids</dt><dd>{int(cell.get('projects_with_bids', 0) or 0)}/{int(cell.get('published_projects', 0) or 0)} <small>{int(cell.get('total_bids', 0) or 0)} total</small></dd></div>
                <div><dt>Matched</dt><dd>{int(cell.get('matched_projects', 0) or 0)} <small>{int(cell.get('qualified_match_rate', 0) or 0)}%</small></dd></div>
                <div><dt>Verified</dt><dd>{int(cell.get('verified_completions', 0) or 0)} <small>{int(cell.get('verified_completion_rate', 0) or 0)}%</small></dd></div>
                <div><dt>First bid</dt><dd>{escape(cell.get('median_first_bid_label', 'No bids'))} <small>{int(cell.get('first_bid_samples', 0) or 0)} projects</small></dd></div>
                <div><dt>Closed</dt><dd>{int(cell.get('closed_projects', 0) or 0)} <small>{int(cell.get('workdoe_match_closures', 0) or 0)} Workdoe</small></dd></div>
                <div><dt>Cancelled / no fit</dt><dd>{int(cell.get('no_match_or_cancelled_projects', 0) or 0)}</dd></div>
                <div><dt>Open reports</dt><dd>{int(cell.get('open_report_projects', 0) or 0)}</dd></div>
                <div><dt>Current supply</dt><dd>{int(cell.get('current_eligible_contractors', 0) or 0)}/{int(cell.get('minimum_eligible_contractors', 3) or 3)}</dd></div>
              </dl>
            </article>"""
        )
    pilot_cell_body = (
        '<div class="pilot-cell-list" role="list" aria-label="Weekly service-zone operations">'
        + "".join(pilot_rows)
        + "</div>"
        if pilot_rows
        else '<p class="empty">No tracked service-zone cells in the last 12 weeks.</p>'
    )
    report_rows = []
    for report in payload.get("reports", []):
        title, meta = admin_report_label(report)
        report_rows.append(
            admin_row(
                title,
                meta,
                action_url=f"/api/admin/reports/{int(report.get('id', 0) or 0)}/resolve",
                action_label="Resolve",
                review_url=admin_report_review_url(report),
            )
        )
    user_rows = []
    for item in payload.get("users", []):
        if item.get("role") == "admin":
            action_url = ""
            action_label = ""
        else:
            action = "suspend" if item.get("status") == "active" else "activate"
            action_url = f"/api/admin/users/{int(item.get('id', 0) or 0)}/{action}"
            action_label = "Suspend" if action == "suspend" else "Activate"
        user_rows.append(
            admin_row(
                item.get("display_name", "Workdoe user"),
                f"{item.get('email', '')} - {item.get('role', '')} - {item.get('status', '')}",
                action_url=action_url,
                action_label=action_label,
            )
        )
    job_rows = []
    for job in payload.get("jobs", []):
        action = "restore" if job.get("status") == "hidden" else "hide"
        job_rows.append(
            admin_row(
                job.get("title", "Job"),
                f"{job_service_name(job)} - {job.get('city', '')}, {job.get('state', '')} - {job.get('status', '')}",
                action_url=f"/api/admin/jobs/{int(job.get('id', 0) or 0)}/{action}",
                action_label="Restore" if action == "restore" else "Hide",
                review_url=f"/jobs/{int(job.get('id', 0) or 0)}",
            )
        )
    photo_rows = []
    for photo in payload.get("photos", []):
        action = "restore" if int(photo.get("is_hidden", 0) or 0) else "hide"
        photo_rows.append(
            admin_row(
                photo.get("original_filename", "Job photo"),
                f"{photo.get('title', '')} - {'hidden' if action == 'restore' else 'visible'}",
                action_url=f"/api/admin/photos/job/{int(photo.get('id', 0) or 0)}/{action}",
                action_label="Restore" if action == "restore" else "Hide",
            )
        )
    contractor_photo_rows = []
    for photo in payload.get("contractor_photos", []):
        action = "restore" if int(photo.get("is_hidden", 0) or 0) else "hide"
        contractor_photo_rows.append(
            admin_row(
                photo.get("original_filename", "Portfolio photo"),
                f"{photo.get('business_name', '')} - {'hidden' if action == 'restore' else 'visible'}",
                action_url=f"/api/admin/photos/contractor/{int(photo.get('id', 0) or 0)}/{action}",
                action_label="Restore" if action == "restore" else "Hide",
            )
        )
    credential_rows = []
    for credential in payload.get("credentials", []):
        credential_id = int(credential.get("id", 0) or 0)
        credential_rows.append(
            f"""
            <div class="credential-review-row">
              <div class="admin-row"><span><strong>{escape(credential.get('business_name', 'Contractor'))} - {escape(credential.get('credential_type_label', 'Credential'))}</strong><small>{escape(credential.get('jurisdiction_label', ''))} - {escape(credential.get('claimed_identifier', ''))} - {escape(credential.get('status_label', ''))} - {escape(credential.get('contractor_email', ''))}</small></span></div>
              <form class="stack-form credential-review-form" data-json-action="/api/admin/credentials/{credential_id}/verify" data-success-url-template="/admin#credential-review" aria-label="Review contractor credential" aria-describedby="credential-review-status-{credential_id}">
                <label for="credential-source-{credential_id}">Public source <input id="credential-source-{credential_id}" name="source_url" type="url" maxlength="300" value="{escape(credential.get('source_url', ''))}" placeholder="https://..."></label>
                <label for="credential-expiry-{credential_id}">Expiration <input id="credential-expiry-{credential_id}" name="expires_at" type="date" value="{escape(credential.get('expires_at', ''))}"></label>
                <label class="wide" for="credential-note-{credential_id}">Review note <input id="credential-note-{credential_id}" name="review_note" maxlength="{CREDENTIAL_REVIEW_NOTE_MAX_LENGTH}" value="{escape(credential.get('review_note', ''))}" placeholder="Required for needs info or not confirmed"></label>
                <div class="row-actions wide">
                  <button class="button compact" type="submit">Source checked</button>
                  <button class="button secondary compact" type="submit" data-json-action="/api/admin/credentials/{credential_id}/pending">Needs info</button>
                  <button class="button secondary compact" type="submit" data-json-action="/api/admin/credentials/{credential_id}/reject">Not confirmed</button>
                  <button class="button secondary compact" type="submit" data-json-action="/api/admin/credentials/{credential_id}/expire">Expired</button>
                </div>
                <p id="credential-review-status-{credential_id}" class="help-text wide" data-form-status aria-live="polite"></p>
              </form>
            </div>"""
        )
    message_rows = []
    for message in payload.get("messages", []):
        action = "restore" if int(message.get("is_hidden", 0) or 0) else "hide"
        message_rows.append(
            admin_row(
                message.get("sender_email", "Workdoe user"),
                f"{message.get('job_title', '')} - {str(message.get('body', ''))[:90]} - {'hidden' if action == 'restore' else 'visible'}",
                action_url=f"/api/admin/messages/{int(message.get('id', 0) or 0)}/{action}",
                action_label="Restore" if action == "restore" else "Hide",
                review_url=f"/messages/{int(message.get('thread_id', 0) or 0)}" if message.get("thread_id") else "",
            )
        )
    action_rows = [
        admin_row(
            f"{action.get('action_type', '')} {action.get('target_type', '')} #{action.get('target_id', '')}",
            f"{action.get('notes', '')} - {action.get('created_at', '')}",
        )
        for action in payload.get("actions", [])
    ]
    automation_rows = []
    for event in payload.get("automation_events", []):
        target = event.get("target_type") or "system"
        if event.get("target_id") is not None:
            target = f"{target} #{event.get('target_id')}"
        automation_rows.append(
            admin_row(
                event.get("event_type", "automation-event"),
                f"{event.get('status', '')} - {target} - {event.get('created_at', '')}",
            )
        )
    close_outcome_rows = [
        admin_row(
            project_close_reason_label(item.get("close_reason")),
            f"{item.get('close_reason', '')} - {int(item.get('total', 0) or 0)} projects",
        )
        for item in payload.get("close_outcomes", [])
    ]
    lead_quality_outcome_rows = [
        admin_row(
            lead_quality_reason_label(item.get("reason_code")),
            f"{item.get('reason_code', '')} - {int(item.get('total', 0) or 0)} signals",
        )
        for item in payload.get("lead_quality_outcomes", [])
    ]
    lead_feedback_rows = [
        admin_row(
            item.get("job_title", "Project"),
            " - ".join(
                part
                for part in (
                    lead_quality_reason_label(item.get("reason_code")),
                    item.get("contractor_email", ""),
                    item.get("note", ""),
                )
                if part
            ),
            review_url=f"/jobs/{int(item.get('job_id', 0) or 0)}",
        )
        for item in payload.get("lead_feedback", [])
    ]
    service_activation_rows = [
        admin_row(
            f"{item.get('service_name', 'Service')} - {item.get('zone_name', 'Zone')}",
            (
                f"{item.get('status', 'candidate')} - "
                f"{int(item.get('eligible_contractors', 0) or 0)} of "
                f"{int(item.get('minimum_eligible_contractors', 3) or 3)} eligible contractors - "
                f"{'open' if activation_is_live(item) else 'closed'}"
            ),
        )
        for item in payload.get("service_activations", [])
    ]
    repeat_invitation_rows = [
        admin_row(
            item.get("project_title", "Project"),
            " - ".join(
                part
                for part in (
                    item.get("contractor_name", "Contractor"),
                    f"{item.get('city', '')}, {item.get('state', '')}",
                    str(item.get("status", "pending")).replace("_", " "),
                    "verified complete" if item.get("verified_complete") else "",
                )
                if part
            ),
            review_url=f"/jobs/{int(item.get('job_id', 0) or 0)}",
        )
        for item in payload.get("repeat_invitations", [])
    ]
    lead_alert_rows = [
        admin_row(
            item.get("project_title", "Project"),
            " - ".join(
                part
                for part in (
                    item.get("contractor_name", "Contractor"),
                    f"{item.get('city', '')}, {item.get('state', '')}",
                    item.get("status", "pending"),
                )
                if part
            ),
            review_url=f"/jobs/{int(item.get('job_id', 0) or 0)}",
        )
        for item in payload.get("recent_lead_alerts", [])
    ]
    match_review_report_rows = [
        admin_row(
            item.get("project_title", "Completed project"),
            f"{item.get('reporter_email', '')} - {item.get('reason', '')}",
            action_url=f"/api/admin/review-reports/{int(item.get('id', 0) or 0)}/resolve",
            action_label="Resolve",
        )
        for item in payload.get("match_review_reports", [])
    ]
    recent_match_review_rows = []
    for item in payload.get("recent_match_reviews", []):
        action = "restore" if item.get("is_hidden") else "hide"
        recent_match_review_rows.append(
            admin_row(
                item.get("project_title", "Completed project"),
                (
                    f"{item.get('reviewer_role', '')} - "
                    f"{item.get('reviewer_email', '')} to {item.get('subject_email', '')} - "
                    f"{'hidden' if item.get('is_hidden') else 'visible'}"
                ),
                action_url=f"/api/admin/reviews/{int(item.get('id', 0) or 0)}/{action}",
                action_label="Restore" if action == "restore" else "Hide",
            )
        )
    body = f"""
    <section class="page-header">
      <p class="eyebrow">Admin</p>
      <h1>Moderation console</h1>
    </section>
    <section class="marketplace-outcomes" aria-labelledby="marketplace-outcomes-title">
      <div class="section-heading">
        <div><p class="eyebrow">Marketplace truth</p><h2 id="marketplace-outcomes-title">Pilot outcomes</h2></div>
        <span class="privacy-label">Operational</span>
      </div>
      <div class="dashboard-metrics compact-metrics" aria-label="Marketplace outcomes">
        <div class="metric-card"><span>Published</span><strong>{int(marketplace.get('published_projects', 0))}</strong></div>
        <div class="metric-card"><span>With bids</span><strong>{int(marketplace.get('projects_with_bids', 0))}</strong></div>
        <div class="metric-card"><span>Matched</span><strong>{int(marketplace.get('matched_projects', 0))}</strong><small>{int(marketplace.get('qualified_match_rate', 0))}% of published</small></div>
        <div class="metric-card"><span>Completion signals</span><strong>{int(marketplace.get('completion_signals', 0))}</strong></div>
        <div class="metric-card"><span>Verified complete</span><strong>{int(marketplace.get('verified_completions', 0))}</strong><small>{int(marketplace.get('verified_completion_rate', 0))}% of approved matches</small></div>
        <div class="metric-card"><span>Closed</span><strong>{int(marketplace.get('closed_projects', 0))}</strong></div>
        <div class="metric-card"><span>Workdoe outcomes</span><strong>{int(marketplace.get('workdoe_match_outcomes', 0))}</strong><small>{int(marketplace.get('workdoe_close_rate', 0))}% of closed</small></div>
        <div class="metric-card"><span>Lead signals</span><strong>{int(marketplace.get('lead_quality_signals', 0))}</strong></div>
      </div>
    </section>
    <section class="marketplace-outcomes" aria-labelledby="pilot-cell-title">
      <div class="section-heading">
        <div><p class="eyebrow">Last 12 weeks</p><h2 id="pilot-cell-title">Service-zone pulse</h2></div>
        <span class="privacy-label">Aggregate only</span>
      </div>
      <div class="dashboard-metrics compact-metrics" aria-label="Service-zone summary">
        <div class="metric-card"><span>Tracked cells</span><strong>{int(pilot_summary.get('tracked_cells', 0) or 0)}</strong><small>{int(pilot_summary.get('observed_cells', 0) or 0)} with projects</small></div>
        <div class="metric-card"><span>Active, no projects</span><strong>{int(pilot_summary.get('active_zero_project_cells', 0) or 0)}</strong></div>
        <div class="metric-card"><span>Supply gaps</span><strong>{int(pilot_summary.get('supply_gap_cells', 0) or 0)}</strong></div>
        <div class="metric-card"><span>Zero-bid projects</span><strong>{int(pilot_summary.get('zero_bid_projects', 0) or 0)}</strong></div>
        <div class="metric-card"><span>Median first bid</span><strong>{escape(pilot_summary.get('median_first_bid_label', 'No bids'))}</strong><small>{int(pilot_summary.get('first_bid_samples', 0) or 0)} responding projects</small></div>
        <div class="metric-card"><span>Qualified match</span><strong>{int(pilot_summary.get('qualified_match_rate', 0) or 0)}%</strong><small>{int(pilot_summary.get('matched_projects', 0) or 0)} of {int(pilot_summary.get('published_projects', 0) or 0)} published</small></div>
        <div class="metric-card"><span>Verified complete</span><strong>{int(pilot_summary.get('verified_completions', 0) or 0)}</strong><small>{int(pilot_summary.get('verified_completion_rate', 0) or 0)}% of matched</small></div>
        <div class="metric-card"><span>Cancelled / no fit</span><strong>{int(pilot_summary.get('no_match_or_cancelled_projects', 0) or 0)}</strong></div>
        <div class="metric-card"><span>Open project reports</span><strong>{int(pilot_summary.get('open_report_projects', 0) or 0)}</strong><small>{int(pilot_summary.get('open_report_rate', 0) or 0)}% of published</small></div>
      </div>
      {pilot_cell_body}
    </section>
    <section class="marketplace-outcomes" aria-labelledby="repeat-work-outcomes-title">
      <div class="section-heading">
        <div><p class="eyebrow">Repeat work</p><h2 id="repeat-work-outcomes-title">Invitation funnel</h2></div>
        <span class="privacy-label">Project-level only</span>
      </div>
      <div class="dashboard-metrics compact-metrics" aria-label="Repeat work outcomes">
        <div class="metric-card"><span>Invited</span><strong>{int(repeat_work.get('invitations_created', 0))}</strong></div>
        <div class="metric-card"><span>Waiting</span><strong>{int(repeat_work.get('invitations_pending', 0))}</strong></div>
        <div class="metric-card"><span>Fresh bids</span><strong>{int(repeat_work.get('invitations_bid_sent', 0))}</strong><small>{int(repeat_work.get('invitation_bid_rate', 0))}% of invitations</small></div>
        <div class="metric-card"><span>Passed</span><strong>{int(repeat_work.get('invitations_declined', 0))}</strong></div>
        <div class="metric-card"><span>Withdrawn</span><strong>{int(repeat_work.get('invitations_withdrawn', 0))}</strong></div>
        <div class="metric-card"><span>Verified repeats</span><strong>{int(repeat_work.get('verified_repeat_projects', 0))}</strong><small>{int(repeat_work.get('verified_repeat_rate', 0))}% of fresh bids</small></div>
      </div>
    </section>
    <section class="marketplace-outcomes" aria-labelledby="lead-alert-outcomes-title">
      <div class="section-heading">
        <div><p class="eyebrow">Contractor response</p><h2 id="lead-alert-outcomes-title">Matching project alerts</h2></div>
        <span class="privacy-label">Opt-in only</span>
      </div>
      <div class="dashboard-metrics compact-metrics" aria-label="Contractor lead alert outcomes">
        <div class="metric-card"><span>Contractors on</span><strong>{int(lead_alerts.get('opted_in_contractors', 0))}</strong></div>
        <div class="metric-card"><span>Local pending</span><strong>{int(lead_alerts.get('pending_alerts', 0))}</strong></div>
        <div class="metric-card"><span>Queued</span><strong>{int(lead_alerts.get('queued_alerts', 0))}</strong></div>
        <div class="metric-card"><span>Sent</span><strong>{int(lead_alerts.get('sent_alerts', 0))}</strong></div>
        <div class="metric-card"><span>Failed</span><strong>{int(lead_alerts.get('failed_alerts', 0))}</strong></div>
      </div>
    </section>
    <section class="marketplace-outcomes" aria-labelledby="review-outcomes-title">
      <div class="section-heading"><div><p class="eyebrow">Completed work</p><h2 id="review-outcomes-title">Participant feedback</h2></div><span class="privacy-label">No star score</span></div>
      <div class="dashboard-metrics compact-metrics" aria-label="Completed-work feedback outcomes">
        <div class="metric-card"><span>Total</span><strong>{int(match_reviews.get('total_reviews', 0))}</strong></div>
        <div class="metric-card"><span>From consumers</span><strong>{int(match_reviews.get('client_reviews', 0))}</strong></div>
        <div class="metric-card"><span>From contractors</span><strong>{int(match_reviews.get('contractor_reviews', 0))}</strong></div>
        <div class="metric-card"><span>Responses</span><strong>{int(match_reviews.get('responses', 0))}</strong></div>
        <div class="metric-card"><span>Open reports</span><strong>{int(match_reviews.get('open_reports', 0))}</strong></div>
        <div class="metric-card"><span>Hidden</span><strong>{int(match_reviews.get('hidden_reviews', 0))}</strong></div>
      </div>
    </section>
    <section class="dashboard-metrics compact-metrics" aria-label="Moderation summary">
      <div class="metric-card"><span>Open reports</span><strong>{int(stats.get('open_reports', 0))}</strong></div>
      <div class="metric-card"><span>Suspended</span><strong>{int(stats.get('suspended_users', 0))}</strong></div>
      <div class="metric-card"><span>Hidden</span><strong>{int(stats.get('hidden_content', 0))}</strong></div>
      <div class="metric-card"><span>Audit</span><strong>{int(stats.get('audit_actions', 0))}</strong></div>
      <div class="metric-card"><span>Automation</span><strong>{int(stats.get('automation_events', 0))}</strong></div>
    </section>
    <section class="admin-grid">
      {admin_panel("Feedback reports", match_review_report_rows, "No open feedback reports.")}
      {admin_panel("Recent completed-work feedback", recent_match_review_rows, "No completed-work feedback yet.")}
      {admin_panel("Recent matching alerts", lead_alert_rows, "No matching project alerts yet.")}
      {admin_panel("Recent repeat invitations", repeat_invitation_rows, "No repeat invitations yet.")}
      {admin_panel("Service launch gates", service_activation_rows, "No service launch candidates configured.")}
      {admin_panel("Project close outcomes", close_outcome_rows, "No structured close outcomes yet.")}
      {admin_panel("Lead quality signals", lead_quality_outcome_rows, "No contractor quality signals yet.")}
      {admin_panel("Recent lead feedback", lead_feedback_rows, "No lead feedback recorded.")}
      {admin_panel("Open reports", report_rows, "No open reports.")}
      {admin_panel("Users", user_rows, "No users yet.")}
      {admin_panel("Jobs", job_rows, "No jobs yet.")}
      {admin_panel("Job photos", photo_rows, "No uploaded job photos yet.")}
      {admin_panel("Portfolio photos", contractor_photo_rows, "No portfolio photos yet.")}
      <article id="credential-review" class="panel admin-panel"><h2>Credential review</h2>{''.join(credential_rows) if credential_rows else '<p class="empty">No credential claims awaiting review.</p>'}</article>
      {admin_panel("Recent messages", message_rows, "No messages yet.")}
      {admin_panel("Audit trail", action_rows, "No moderation actions yet.")}
      {admin_panel("Automation", automation_rows, "No automation events yet.")}
    </section>"""
    return layout(user, "/admin", "Admin", body, include_actions=True)


def contractor_job_detail_html(
    user,
    payload: dict,
    site_key: str = "",
    *,
    embedded: bool = False,
) -> str:
    job = payload.get("job", {})
    job_policy = service_policy(job.get("service_slug"))
    existing = payload.get("existing_request")
    repeat_invitation = payload.get("repeat_invitation")
    photos = payload.get("photos", [])
    bidding = job.get("bid_window", {})
    lead_feedback = payload.get("lead_feedback", {})
    proposal_templates = payload.get("proposal_templates", [])
    proposal_template_limit = int(payload.get("proposal_template_limit", 6) or 6)
    proposal_template_name_max = int(
        payload.get("proposal_template_name_max", 60) or 60
    )
    selected_proposal_template = payload.get("selected_proposal_template")
    bid_form = payload.get("bid_form", {})
    scope_html = quote_ready_details_html(payload.get("scope_answers", []))
    brief_html = brief_readiness_html(job.get("brief_readiness"))
    photo_html = "\n".join(
        f'<figure><img src="{escape(photo.get("url", ""))}" alt="Job photo"><figcaption>{escape(photo.get("original_filename", ""))}</figcaption></figure>'
        for photo in photos
    )
    if existing:
        feedback_options = [
            '<option value="">Choose an issue</option>'
        ]
        feedback_options.extend(
            '<option value="{value}"{selected}>{label}</option>'.format(
                value=escape(option["value"]),
                selected=(
                    " selected"
                    if lead_feedback.get("reason_code") == option["value"]
                    else ""
                ),
                label=escape(option["label"]),
            )
            for option in LEAD_QUALITY_REASONS
        )
        close_outcome = (
            f'<p class="outcome-chip">{escape(project_close_reason_label(job.get("close_reason")))}</p>'
            if job.get("status") == "closed" and job.get("close_reason")
            else ""
        )
        side = f"""
        <h2>Mini bid sent</h2>
        <p>Your request is currently <strong>{escape(existing.get('status', ''))}</strong>.</p>
        {close_outcome}
        <dl class="profile-facts compact-facts">
          <div><dt>Price</dt><dd>{escape(existing.get('price_range', ''))}</dd></div>
          <div><dt>Timeline</dt><dd>{escape(existing.get('timeline', ''))}</dd></div>
          <div><dt>Availability</dt><dd>{escape(existing.get('availability', ''))}</dd></div>
        </dl>
        <a class="button secondary full" href="/leads">Back to leads</a>
        {(
            '<details id="save-proposal-template" class="quality-feedback"><summary>Save as proposal template</summary>'
            + f'<form class="stack-form" data-json-action="/api/contractor/proposal-templates" data-success-url-template="/jobs/{int(job.get("id", 0))}#mini-bid" aria-label="Save proposal template" aria-describedby="proposal-template-save-status">'
            + f'<input type="hidden" name="source_match_request_id" value="{int(existing.get("id", 0) or 0)}">'
            + f'<label for="proposal-template-name">Template name <input id="proposal-template-name" name="name" maxlength="{proposal_template_name_max}" autocomplete="off" placeholder="Exterior wash response" required></label>'
            + '<button class="button secondary compact" type="submit">Save template</button><p class="help-text">Scope, timeline, experience, questions, and availability are copied. Price is never reused.</p><p id="proposal-template-save-status" class="help-text" data-form-status aria-live="polite"></p></form></details>'
        ) if len(proposal_templates) < proposal_template_limit else ''}
        <details id="lead-quality" class="quality-feedback"{' open' if lead_feedback else ''}>
          <summary>Lead quality feedback</summary>
          <form class="stack-form" data-json-action="/api/jobs/{int(job.get('id', 0))}/quality-feedback" data-success-url-template="/jobs/{int(job.get('id', 0))}#lead-quality" aria-label="Record lead quality feedback" aria-describedby="lead-quality-status">
            <label for="lead-quality-reason">Issue <select id="lead-quality-reason" name="reason_code" required>{''.join(feedback_options)}</select></label>
            <label for="lead-quality-note">Private note (optional) <textarea id="lead-quality-note" name="note" rows="2" maxlength="{OUTCOME_NOTE_MAX_LENGTH}" placeholder="Concise operational detail">{escape(lead_feedback.get('note', ''))}</textarea></label>
            <button class="button secondary compact" type="submit">Save feedback</button>
            <p id="lead-quality-status" class="help-text" data-form-status aria-live="polite">This improves matching operations. Use the report form for safety or policy concerns.</p>
          </form>
        </details>"""
    elif job.get("can_request_match"):
        template_links = "".join(
            f'<a class="button secondary compact" href="/jobs/{int(job.get("id", 0))}?proposal_template={int(template.get("id", 0) or 0)}#mini-bid">{escape(template.get("name", ""))}</a>'
            for template in proposal_templates
        )
        template_picker = (
            '<section class="proposal-template-picker" aria-labelledby="proposal-template-picker-title"><strong id="proposal-template-picker-title">Start from a saved proposal</strong><div class="saved-location-shortcuts">'
            + template_links
            + '</div><p class="help-text">Reusable wording only. Enter a fresh price for this project.</p></section>'
            if template_links
            else ""
        )
        selected_template_note = (
            '<div class="repeat-invitation-note proposal-template-applied"><span class="eyebrow">Template applied</span><strong>'
            + escape(selected_proposal_template.get("name", ""))
            + '</strong><p>Review every field and add a project-specific price before sending.</p></div>'
            if selected_proposal_template
            else ""
        )
        price_placeholder = (
            "Add a fresh estimate" if selected_proposal_template else "$450-$650"
        )
        bid_policy_html = ""
        if (
            job_policy["acknowledgement_required"]
            or job_policy["emergency_disabled"]
        ):
            bid_policy_checked = (
                " checked"
                if str(bid_form.get("service_policy_acknowledgement") or "")
                == job_policy["version"]
                else ""
            )
            bid_policy_html = f"""
          <section class="service-policy-advisory compact-policy">
            <div><span class="eyebrow">{'Local rules check' if job_policy['risk_tier'] == 'regulated' else 'Safety check'}</span><strong>Confirm before bidding</strong><p>{escape(job_policy['advisory'])}</p></div>
            <label class="service-policy-confirmation" for="bid-service-policy-acknowledgement"><input id="bid-service-policy-acknowledgement" type="checkbox" name="service_policy_acknowledgement" value="{escape(job_policy['version'])}" required{bid_policy_checked}><span>I understand that I am responsible for the qualifications, permits, insurance, and safe work plan required for this project.</span></label>
          </section>"""
        side = f"""
        <h2>Send mini bid</h2>
        {template_picker}
        {selected_template_note}
        <form class="stack-form bid-form" data-json-action="/api/jobs/{int(job.get('id', 0))}/request" data-success-url-template="/jobs/{int(job.get('id', 0))}" aria-label="Send mini bid" aria-describedby="bid-form-status">
          <label for="bid-scope-note">Scope note <textarea id="bid-scope-note" name="scope_note" rows="4" minlength="20" maxlength="800" placeholder="Work included, assumptions, access needs." autocapitalize="sentences" spellcheck="true" enterkeyhint="next" required>{escape(bid_form.get('scope_note', ''))}</textarea></label>
          <div class="bid-quick-grid">
            <label for="bid-price-range">Price range <input id="bid-price-range" name="price_range" value="{escape(bid_form.get('price_range', ''))}" maxlength="80" inputmode="text" placeholder="{price_placeholder}" list="bid-price-options" enterkeyhint="next" required></label>
            <label for="bid-timeline">Timeline <input id="bid-timeline" name="timeline" value="{escape(bid_form.get('timeline', ''))}" maxlength="120" placeholder="Next week" list="bid-timeline-options" autocapitalize="sentences" spellcheck="true" enterkeyhint="next" required></label>
            <label for="bid-availability">Availability <input id="bid-availability" name="availability" value="{escape(bid_form.get('availability', ''))}" maxlength="120" placeholder="Tue/Thu PM" list="bid-availability-options" autocapitalize="sentences" spellcheck="true" enterkeyhint="next" required></label>
          </div>
          <label for="bid-experience">Relevant experience <textarea id="bid-experience" name="experience" rows="3" minlength="20" maxlength="800" placeholder="Similar work or crew capability." autocapitalize="sentences" spellcheck="true" enterkeyhint="next" required>{escape(bid_form.get('experience', ''))}</textarea></label>
          <datalist id="bid-price-options">
            <option value="$250-$500"></option>
            <option value="$500-$1,000"></option>
            <option value="On-site estimate needed"></option>
          </datalist>
          <datalist id="bid-timeline-options">
            <option value="Same week"></option>
            <option value="Next week"></option>
            <option value="Two business days after approval"></option>
          </datalist>
          <datalist id="bid-availability-options">
            <option value="Weekday mornings"></option>
            <option value="Weekday afternoons"></option>
            <option value="Weekend available"></option>
          </datalist>
          <details class="optional-field"{' open' if bid_form.get('questions') else ''}><summary>Questions (optional)</summary><label class="sr-only" for="bid-questions">Questions</label><textarea id="bid-questions" name="questions" rows="2" maxlength="500" placeholder="Optional" autocapitalize="sentences" spellcheck="true" enterkeyhint="done">{escape(bid_form.get('questions', ''))}</textarea></details>
          {bid_policy_html}
          {turnstile_html(site_key, "match-request")}
          <button class="button full" type="submit" aria-label="Send mini bid">Send bid</button>
          <p id="bid-form-status" class="help-text" data-form-status aria-live="polite"></p>
        </form>"""
    else:
        side = f'<h2>{escape(bidding.get("availability_label", "Lead unavailable"))}</h2><p class="help-text">This project is not accepting another mini bid. No contractor can pay to move ahead of the queue.</p><a class="button secondary full" href="/leads">Back to leads</a>'
    if embedded:
        side = f"""
        <dl class="dialog-project-snapshot" aria-label="Project snapshot">
          <div><dt>Budget</dt><dd>{escape(job.get('budget', '') or 'Not provided')}</dd></div>
          <div><dt>Target</dt><dd>{escape(job.get('desired_date', '') or 'Flexible')}</dd></div>
          <div><dt>Area</dt><dd>{escape(job.get('area_label', ''))}</dd></div>
        </dl>
        {side}"""
    if row_value(user, "role") == "contractor":
        side += f"""
        <form class="report-form" data-json-action="/api/reports" data-success-url-template="/jobs/{int(job.get('id', 0))}" aria-label="Report lead" aria-describedby="lead-report-status">
          <input type="hidden" name="target_type" value="job">
          <input type="hidden" name="target_id" value="{int(job.get('id', 0))}">
          <label for="lead-report-reason">Report this lead <input id="lead-report-reason" name="reason" maxlength="500" placeholder="Why should moderation review it?" required></label>
          {turnstile_html(site_key, "report")}
          <button class="button secondary compact" type="submit">Report</button>
          <p id="lead-report-status" class="help-text" data-form-status aria-live="polite"></p>
        </form>"""
    invitation_note = ""
    if repeat_invitation:
        invitation_note = f"""
    <section class="repeat-invitation-note" aria-label="Repeat provider invitation">
      <div><strong>Invited back</strong><p>This consumer previously completed mutually verified Workdoe work with you. Any bid here is new and follows the normal deadline and bid limit.</p></div>
      <span class="status {escape(repeat_invitation.get('status', 'pending'))}">{escape(repeat_invitation.get('status_label', 'Waiting for contractor'))}</span>
    </section>"""
    body = f"""
    <div class="contractor-lead-flow" data-dialog-fragment data-bid-flow>
    <section class="dashboard-header" data-dialog-focus tabindex="-1">
      <div>
        <p class="eyebrow">Contractor lead</p>
        <h1>{escape(job.get('title', 'Lead'))}</h1>
        <p>{escape(job_service_name(job))} in {escape(job.get('area_label', ''))}</p>
      </div>
      <span class="status {escape(job.get('status', ''))}">{escape(job.get('status', ''))}</span>
    </section>
    {bid_window_html(bidding)}
    {invitation_note}
    <section class="detail-grid">
      <article class="panel">
        <h2>Job details</h2>
        <dl class="job-facts">
          <div><dt>Service</dt><dd>{escape(job_service_name(job))}</dd></div>
          <div><dt>Setting</dt><dd>{escape(job.get('project_setting_label', 'Not specified'))}</dd></div>
          <div><dt>Area</dt><dd>{escape(job.get('area_label', ''))}</dd></div>
          <div><dt>Photos</dt><dd>{len(photos)}</dd></div>
          <div><dt>Bids</dt><dd>{escape(bidding.get('usage_label', ''))}</dd></div>
        </dl>
        {brief_html}
        {scope_html}
        <p class="preline">{escape(job.get('description', ''))}</p>
        <p class="help-text">{escape(job.get('location_privacy', ''))}</p>
        <div class="photo-grid">{photo_html}</div>
      </article>
      <aside class="panel">{side}</aside>
    </section>
    </div>"""
    return layout(
        user,
        "/leads",
        job.get("title", "Lead"),
        body,
        include_actions=True,
        include_turnstile=bool(site_key),
        body_class="dialog-fragment-body" if embedded else "",
    )


def bid_comparison_html(comparison: dict, job_id: int = 0) -> str:
    offers = comparison.get("offers", [])
    if not offers and not comparison.get("pending_count"):
        return ""
    offer_cards = []
    for offer in offers:
        offer_id = int(offer.get("id", 0) or 0)
        reputation = offer.get("reputation", {})
        credential_signals = reputation.get("credential_signals", [])
        credential_signal_html = "".join(
            '<span class="bid-credential-signal">'
            '<img src="/static/vendor/tabler-icons/home-check.svg" alt="">'
            f'<span><strong>{escape(signal.get("label", "Source checked"))}</strong>'
            f'<small>{escape(signal.get("qualifier", "Current public record"))}</small></span></span>'
            for signal in credential_signals
        ) or (
            '<span class="bid-credential-signal bid-credential-signal--empty">'
            '<span><strong>No source-checked record</strong>'
            '<small>Review profile details</small></span></span>'
        )
        provider_facts = "".join(
            f"""
            <div>
              <dt>{escape(fact.get('label', 'Provider fact'))}</dt>
              <dd>{escape(fact.get('value', 'Not provided'))}<small>{escape(fact.get('qualifier', ''))}</small></dd>
            </div>"""
            for fact in offer.get("provider_facts", [])
        )
        offer_cards.append(
            f"""
        <article class="bid-compare-card" aria-labelledby="compare-offer-{offer_id}">
          <header>
            <div>
              <p class="bid-offer-label">{escape(offer.get('offer_label', 'Offer'))}</p>
              <h4 id="compare-offer-{offer_id}">{escape(offer.get('contractor_name', 'Contractor'))}</h4>
              <p>{escape(offer.get('trades', 'Contractor profile'))}</p>
            </div>
          </header>
          <div class="bid-reputation-strip">
            <img src="/static/vendor/tabler-icons/sparkles.svg" alt="">
            <span><strong>{escape(reputation.get('level_label', 'New to Workdoe'))}</strong><small>{int(reputation.get('completion_points', 0) or 0)} completion points</small></span>
          </div>
          <div class="bid-credential-signals" aria-label="Reviewed credential signals">{credential_signal_html}</div>
          <dl class="bid-compare-terms">
            <div><dt>Price</dt><dd>{escape(offer.get('price_range', 'Not provided'))}</dd></div>
            <div><dt>Timeline</dt><dd>{escape(offer.get('timeline', 'Not provided'))}</dd></div>
            <div><dt>Availability</dt><dd>{escape(offer.get('availability', 'Not provided'))}</dd></div>
          </dl>
          <dl class="bid-provider-facts">{provider_facts}</dl>
          <div class="bid-compare-actions">
            <a class="button secondary compact" href="{escape(offer.get('profile_url', '#'))}">Profile</a>
            <a class="button secondary compact" href="#bid-title-{offer_id}">Full offer</a>
          </div>
          <form class="bid-choose-form" method="post" data-json-action="/api/match-requests/{offer_id}/approve" data-success-url-template="/client/jobs/{job_id}">
            <button class="button compact" type="submit" aria-label="Choose {escape(offer.get('contractor_name', 'contractor'))}" aria-describedby="compare-offer-{offer_id}-status">Choose contractor</button>
            <span class="form-status" id="compare-offer-{offer_id}-status" role="status" aria-live="polite"></span>
          </form>
        </article>"""
        )
    count = min(4, max(1, len(offers)))
    active_filter = comparison.get("credential_filter", "all")
    filter_tabs = "".join(
        f'<a href="{escape(option.get("url", "#"))}"'
        + (' aria-current="page"' if option.get("value") == active_filter else "")
        + f'><span>{escape(option.get("label", "Filter"))}</span><strong>{int(option.get("count", 0) or 0)}</strong></a>'
        for option in comparison.get("credential_filter_options", [])
    )
    comparison_grid = (
        f'<div class="bid-comparison-grid bid-comparison-grid--{count}">{"".join(offer_cards)}</div>'
        if offers
        else '<p class="empty comparison-empty">No pending offers match this record filter. All pending offers remain below.</p>'
    )
    return f"""
    <section class="bid-comparison" aria-labelledby="bid-comparison-title">
      <div class="section-heading">
        <div><p class="eyebrow">Contractor choice</p><h3 id="bid-comparison-title">Compare offers</h3></div>
        <span class="privacy-label">{escape(comparison.get('order_label', 'Received order'))}</span>
      </div>
      <p class="bid-comparison-note">Compare scope, price, timing, and reviewed records. Offers stay in received order; there is no paid ranking.</p>
      <nav class="comparison-filter-tabs" aria-label="Filter comparison by source-checked records">{filter_tabs}</nav>
      <p class="comparison-filter-note">Filters change these cards only. Every offer remains in the full list below.</p>
      {comparison_grid}
      <p class="help-text">A source-checked record means Workdoe reviewed a current public source. It does not guarantee skill, safety, insurance coverage, or legal eligibility.</p>
    </section>"""


def client_job_detail_html(user, detail_payload: dict, requests_payload: dict) -> str:
    job = detail_payload.get("job", {})
    repeat_invitation = detail_payload.get("repeat_invitation")
    requests = requests_payload.get("requests", [])
    approved_request = requests_payload.get("approved_request")
    stats = requests_payload.get("stats", {})
    bidding = job.get("bid_window", requests_payload.get("job", {}).get("bid_window", {}))
    view_links = requests_payload.get("view_links", [])
    photos = detail_payload.get("photos", [])
    view = requests_payload.get("view", "all")
    job_id = int(job.get("id", 0) or 0)
    comparison_html = bid_comparison_html(
        requests_payload.get("comparison", {}), job_id=job_id
    )
    reviews_by_request = requests_payload.get("reviews_by_request", {})
    scope_html = quote_ready_details_html(detail_payload.get("scope_answers", []))
    brief_html = brief_readiness_html(job.get("brief_readiness"))
    photo_html = "\n".join(
        f'<figure><img src="{escape(photo.get("url", ""))}" alt="Job photo"><figcaption>{escape(photo.get("original_filename", ""))}</figcaption></figure>'
        for photo in photos
    )
    link_html = "\n".join(
        f'<a href="{escape(link.get("url", "#"))}"{" aria-current=\"page\"" if link.get("value") == view else ""}>{escape(link.get("label", ""))}</a>'
        for link in view_links
    )
    status = job.get("status", "")
    job_title = job.get("title", "job")
    completion_started = any(
        request.get("client_confirmed_at") or request.get("contractor_confirmed_at")
        for request in requests
    ) or bool(
        approved_request
        and (
            approved_request.get("client_confirmed_at")
            or approved_request.get("contractor_confirmed_at")
        )
    )
    approved_match_html = ""
    if approved_request:
        approved_name = approved_request.get("contractor_name", "Contractor")
        approved_state = approved_request.get("completion_state", "awaiting")
        completion_class = "verified" if approved_state == "verified" else "awaiting"
        message_action = (
            f'<a class="button compact" href="{escape(approved_request.get("thread_url", ""))}">Message</a>'
            if approved_request.get("thread_url")
            else ""
        )
        approved_match_html = f"""
    <section class="project-match-context" aria-labelledby="approved-match-title">
      <div class="project-match-heading">
        <p class="eyebrow">Approved match</p>
        <h2 id="approved-match-title">{escape(approved_name)}</h2>
        <span class="completion-chip {completion_class}">{escape(approved_request.get('completion_label', 'Awaiting completion'))}</span>
      </div>
      <div class="project-match-actions">
        {message_action}
        <a class="button secondary compact" href="{escape(approved_request.get('profile_url', ''))}">Profile</a>
      </div>
      <dl class="thread-match-facts">
        <div><dt>Price</dt><dd>{escape(approved_request.get('price_range') or 'Not provided')}</dd></div>
        <div><dt>Timeline</dt><dd>{escape(approved_request.get('timeline') or 'Not provided')}</dd></div>
        <div><dt>Availability</dt><dd>{escape(approved_request.get('availability') or 'Not provided')}</dd></div>
      </dl>
    </section>"""
    invitation_banner = ""
    if repeat_invitation:
        invitation_action = ""
        if repeat_invitation.get("status") == "pending":
            invitation_action = f"""
      <form data-json-action="{escape(repeat_invitation.get('withdraw_url', ''))}" data-success-url-template="/client/jobs/{job_id}" aria-label="Withdraw repeat provider invitation"><button class="button secondary compact" type="submit">Withdraw</button><span class="sr-only" data-form-status aria-live="polite"></span></form>"""
        invitation_banner = f"""
    <section class="repeat-invitation-banner compact-banner" aria-label="Repeat provider invitation status">
      <div><strong>{escape(repeat_invitation.get('contractor_name', 'Contractor'))} was invited to bid</strong><p>{escape(repeat_invitation.get('status_label', 'Waiting for contractor'))}. This is a private invitation, not an approval or reserved bid slot.</p></div>
      {invitation_action}
    </section>"""
    close_dialog = ""
    if status == "open":
        close_options = "\n".join(
            f"""
          <label class="outcome-choice">
            <input type="radio" name="reason_code" value="{escape(option['value'])}" required>
            <span><strong>{escape(option['label'])}</strong><small>{escape(option['description'])}</small></span>
          </label>"""
            for option in PROJECT_CLOSE_REASONS
        )
        status_form = """
        <button class="button secondary full" type="button" data-inline-dialog-open="close-job-dialog">Close job</button>"""
        close_dialog = f"""
    <dialog id="close-job-dialog" class="inline-dialog" data-inline-dialog aria-labelledby="close-job-title">
      <form class="inline-dialog-surface stack-form" data-json-action="/api/jobs/{job_id}/close" data-success-url-template="/client/jobs/{job_id}" aria-label="Close {escape(job_title)}" aria-describedby="job-status-form-status">
        <header class="inline-dialog-header">
          <div><p class="eyebrow">Project close-out</p><h2 id="close-job-title">Where did this project land?</h2></div>
          <button class="button secondary compact" type="button" data-inline-dialog-close>Cancel</button>
        </header>
        <p class="help-text">This keeps project history and pilot results accurate. Private notes are visible only to you and Workdoe administrators.</p>
        <fieldset class="outcome-choice-list"><legend>Choose one outcome</legend>{close_options}</fieldset>
        <label for="close-job-note">Private note (optional) <textarea id="close-job-note" name="note" rows="3" maxlength="{OUTCOME_NOTE_MAX_LENGTH}" placeholder="Anything the operations team should understand?"></textarea></label>
        <div class="inline-dialog-actions">
          <button class="button secondary" type="button" data-inline-dialog-close>Keep open</button>
          <button class="button" type="submit">Close project</button>
        </div>
        <p id="job-status-form-status" class="help-text" data-form-status aria-live="polite"></p>
      </form>
    </dialog>"""
    elif status == "closed" and not completion_started:
        status_form = f"""
        <form data-json-action="/api/jobs/{job_id}/reopen" data-success-url-template="/client/jobs/{job_id}" aria-label="Reopen {escape(job_title)}" aria-describedby="job-status-form-status">
          <button class="button secondary full" type="submit">Reopen job</button>
          <p id="job-status-form-status" class="help-text" data-form-status aria-live="polite"></p>
        </form>"""
    elif status == "closed":
        status_form = '<p class="help-text">This project cannot reopen after either participant confirms completion.</p>'
    else:
        status_form = '<p class="help-text">This job is hidden by moderation.</p>'
    request_rows = []
    for request in requests:
        request_id = int(request.get("id", 0) or 0)
        request_status = request.get("status", "")
        actions = ""
        if request.get("can_approve"):
            contractor_name = request.get("contractor_name", "contractor")
            actions = f"""
          <div class="bid-actions">
            <form data-json-action="/api/match-requests/{request_id}/approve" data-success-url-template="/client/jobs/{job_id}" aria-label="Approve mini bid from {escape(contractor_name)}" aria-describedby="match-request-{request_id}-approve-status">
              <button class="button" type="submit">Approve</button>
              <p id="match-request-{request_id}-approve-status" class="help-text" data-form-status aria-live="polite"></p>
            </form>
            <form data-json-action="/api/match-requests/{request_id}/reject" data-success-url-template="/client/jobs/{job_id}" aria-label="Reject mini bid from {escape(contractor_name)}" aria-describedby="match-request-{request_id}-reject-status">
              <button class="button secondary" type="submit">Reject</button>
              <p id="match-request-{request_id}-reject-status" class="help-text" data-form-status aria-live="polite"></p>
            </form>
          </div>"""
        elif request.get("thread_url"):
            actions = f'<a class="button secondary" href="{escape(request.get("thread_url", ""))}">Message</a>'
        if (
            request_status == "approved"
            and job.get("status") == "closed"
            and job.get("close_reason") == "workdoe-match"
            and not request.get("client_confirmed_at")
        ):
            actions += f"""
          <form data-json-action="/api/match-requests/{request_id}/complete" data-success-url-template="/client/jobs/{job_id}" aria-label="Confirm completion with {escape(request.get('contractor_name', 'contractor'))}" aria-describedby="match-completion-{request_id}-status">
            <button class="button compact" type="submit">Confirm complete</button>
            <p id="match-completion-{request_id}-status" class="help-text" data-form-status aria-live="polite"></p>
          </form>"""
        completion = ""
        if request_status == "approved":
            completion_message = (
                "Close the project after the work is finished to begin confirmation."
                if job.get("status") != "closed"
                else (
                    "This project closed without a Workdoe fulfillment claim."
                    if job.get("close_reason") != "workdoe-match"
                    else (
                        "Both participants confirmed this Workdoe project."
                        if request.get("verified_at")
                        else "Both participants confirm independently. No rating or payment is created."
                    )
                )
            )
            completion = f"""
        <div class="completion-status {escape(request.get('completion_state', 'awaiting'))}">
          <strong>{escape(request.get('completion_label', 'Awaiting both confirmations'))}</strong>
          <span>{escape(completion_message)}</span>
        </div>"""
        feedback_html = ""
        if request.get("verified_at"):
            item_reviews = reviews_by_request.get(request_id, {})
            feedback_parts = []
            if not item_reviews.get("client"):
                feedback_parts.append(
                    match_review_form_html(
                        request_id,
                        "client",
                        f"/client/jobs/{job_id}#completed-feedback",
                    )
                )
            feedback_parts.extend(
                match_review_card_html(
                    review,
                    user,
                    f"/client/jobs/{job_id}#completed-feedback",
                )
                for review in item_reviews.values()
            )
            feedback_html = (
                '<section id="completed-feedback" class="completed-feedback" aria-label="Completed-work feedback">'
                + "".join(feedback_parts)
                + "</section>"
            )
        request_rows.append(
            f"""
      <article class="bid-card" aria-labelledby="bid-title-{request_id}">
        <div class="row-meta">
          <span class="status {escape(request_status)}">{escape(request_status)}</span>
          <span>{escape(request.get('trades', 'Contractor profile'))}</span>
        </div>
        <h2 id="bid-title-{request_id}">{escape(request.get('contractor_name', 'Contractor'))}</h2>
        <p class="job-summary">{escape(request.get('scope_note', ''))}</p>
        <dl class="profile-facts compact-facts">
          <div><dt>Price</dt><dd>{escape(request.get('price_range', ''))}</dd></div>
          <div><dt>Timeline</dt><dd>{escape(request.get('timeline', ''))}</dd></div>
          <div><dt>Availability</dt><dd>{escape(request.get('availability', ''))}</dd></div>
        </dl>
        <details class="optional-field"><summary>Experience</summary><p class="preline">{escape(request.get('experience', ''))}</p></details>
        {('<details class="optional-field"><summary>Questions</summary><p class="preline">' + escape(request.get('questions', '')) + '</p></details>') if request.get('questions') else ''}
        {actions}
        {completion}
        {feedback_html}
      </article>"""
        )
    requests_html = "\n".join(request_rows) if request_rows else empty_state("No mini bids yet", "/client/dashboard", "Back to dashboard")
    bid_window_markup = bid_window_html(bidding, owner=True, job_id=job_id) if status == "open" else ""
    body = f"""
    <section class="dashboard-header">
      <div>
        <p class="eyebrow">Client job</p>
        <h1>{escape(job.get('title', 'Job'))}</h1>
        <p>{escape(job_service_name(job))} in {escape(job.get('area_label', ''))}</p>
      </div>
      <span class="status {escape(job.get('status', ''))}">{escape(job.get('status', ''))}</span>
    </section>
    <ol class="project-journey" aria-label="Project journey">
      <li class="is-complete"><span>01</span><strong>Posted</strong></li>
      <li{' class="is-complete"' if int(stats.get('total', 0)) else ''}><span>02</span><strong>Bids</strong></li>
      <li{' class="is-complete"' if int(stats.get('approved', 0)) else ''}><span>03</span><strong>Matched</strong></li>
      <li{' class="is-complete"' if int(stats.get('verified', 0)) else ''}><span>04</span><strong>Complete</strong></li>
    </ol>
    {approved_match_html}
    {bid_window_markup}
    {invitation_banner}
    <section class="detail-grid">
      <article class="panel">
        <h2>Job details</h2>
        <dl class="job-facts">
          <div><dt>Service</dt><dd>{escape(job_service_name(job))}</dd></div>
          <div><dt>Setting</dt><dd>{escape(job.get('project_setting_label', 'Not specified'))}</dd></div>
          <div><dt>Area</dt><dd>{escape(job.get('area_label', ''))}</dd></div>
          <div><dt>Desired</dt><dd>{escape(job.get('desired_date', '') or 'Flexible')}</dd></div>
          <div><dt>Photos</dt><dd>{len(photos)}</dd></div>
          <div><dt>Bids</dt><dd>{escape(bidding.get('usage_label', ''))}</dd></div>
        </dl>
        {brief_html}
        {scope_html}
        <p class="preline">{escape(job.get('description', ''))}</p>
        <div class="photo-grid">{photo_html}</div>
      </article>
      <aside id="job-controls" class="panel">
        <h2>Job controls</h2>
        <a class="button full" href="/client/jobs/{job_id}/edit">Edit project</a>
        {status_form}
        {(
            '<div class="close-outcome-summary"><span>Close outcome</span><strong>'
            + escape(project_close_reason_label(job.get('close_reason')))
            + '</strong>'
            + (('<p>' + escape(job.get('close_note', '')) + '</p>') if job.get('close_note') else '')
            + '</div>'
        ) if job.get('status') == 'closed' and job.get('close_reason') else ''}
        <form class="stack-form" data-file-action="/api/media/jobs/{job_id}/upload" data-success-url-template="/client/jobs/{job_id}" enctype="multipart/form-data" aria-label="Upload job photo" aria-describedby="job-photo-upload-status">
          <label for="job-photo-upload">Job photo <input id="job-photo-upload" name="photo" type="file" accept="image/png,image/jpeg,image/gif,image/webp" required></label>
          <button class="button secondary full" type="submit" aria-label="Upload job photo">Upload photo</button>
          <p id="job-photo-upload-status" class="help-text" data-form-status aria-live="polite"></p>
        </form>
      </aside>
    </section>
    {close_dialog}
    <section class="band subtle bid-review-section" id="mini-bids">
      <div class="panel-heading">
        <h2>Mini bids</h2>
        <nav class="filter-links" aria-label="Mini-bid filters">{link_html}</nav>
      </div>
      {comparison_html}
      <div class="bid-list">
{requests_html}
      </div>
    </section>"""
    return layout(user, f"/client/jobs/{job_id}", job.get("title", "Client Job"), body, include_actions=True)


def simple_app_html(user, active_path: str, title: str, message: str, action_href: str, action_label: str) -> str:
    body = f"""
    <section class="dashboard-header">
      <div>
        <p class="eyebrow">Workdoe</p>
        <h1>{escape(title)}</h1>
        <p>{escape(message)}</p>
      </div>
      <a class="button" href="{escape(action_href)}">{escape(action_label)}</a>
    </section>"""
    return layout(user, active_path, title, body)
