from __future__ import annotations

import json
from base64 import urlsafe_b64decode
from binascii import Error as Base64Error
from html import escape
from urllib.parse import urlencode, urlparse

from public_jobs import (
    JOB_CATEGORIES,
    public_job_filters_from_query,
    public_job_payload,
    public_jobs_payload,
)


ENTRY_ROUTES = {"/", "/login", "/start"}
ENTRY_JOB_LIMIT = 50
DEFAULT_CLERK_FRONTEND_API_URL = "https://workdoe.com/__clerk"
CLERK_SIGNIN_MODE = "signin"
CLERK_START_MODE = "start"
WORKDOE_PUBLIC_DOMAIN = "workdoe.com"
CLERK_PROXY_PATH = "/__clerk"
CLERK_DEVELOPMENT_SUFFIX = ".clerk.accounts.dev"
CLERK_CHALLENGE_ORIGIN = "https://challenges.cloudflare.com"
CLERK_PROTECT_ORIGIN = "https://*.protect.clerk.com"
CLERK_IMAGE_ORIGIN = "https://img.clerk.com"
CLERK_TELEMETRY_ORIGINS = (
    "https://clerk-telemetry.com",
    "https://*.clerk-telemetry.com",
)


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def first_query_value(params: dict, key: str, default: str = "") -> str:
    value = params.get(key, default)
    if isinstance(value, list):
        value = value[0] if value else default
    return str(value or default)


def normalize_intent(value: str | None, path: str = "/start") -> str:
    if value in {"post-job", "find-work"}:
        return value
    return "find-work" if path == "/login" else "post-job"


def normalize_clerk_frontend_api_url(value: str | None) -> str:
    raw = (value or DEFAULT_CLERK_FRONTEND_API_URL).strip().rstrip("/")
    if raw.startswith("/") and not raw.startswith("//"):
        return raw if raw and raw != "/" else DEFAULT_CLERK_FRONTEND_API_URL
    parsed = urlparse(raw)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not is_workdoe_domain(parsed.hostname)
    ):
        return DEFAULT_CLERK_FRONTEND_API_URL
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def is_workdoe_domain(hostname: str | None) -> bool:
    host = (hostname or "").strip().lower().rstrip(".")
    return host == WORKDOE_PUBLIC_DOMAIN or host.endswith(f".{WORKDOE_PUBLIC_DOMAIN}")


def clerk_csp_origin(frontend_api_url: str) -> str:
    direct = urlparse(str(frontend_api_url or "").strip().rstrip("/"))
    if (
        direct.scheme == "https"
        and direct.hostname
        and direct.hostname.endswith(CLERK_DEVELOPMENT_SUFFIX)
        and not direct.path
        and not direct.params
        and not direct.query
        and not direct.fragment
        and direct.port is None
    ):
        return f"https://{direct.hostname}"
    normalized = normalize_clerk_frontend_api_url(frontend_api_url)
    if normalized.startswith("/"):
        return ""
    parsed = urlparse(normalized)
    if parsed.scheme == "https" and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return DEFAULT_CLERK_FRONTEND_API_URL


def clerk_proxy_url(frontend_api_url: str) -> str:
    normalized = normalize_clerk_frontend_api_url(frontend_api_url)
    if normalized.startswith(CLERK_PROXY_PATH):
        return normalized
    parsed = urlparse(normalized)
    if is_workdoe_domain(parsed.hostname) and parsed.path.startswith(CLERK_PROXY_PATH):
        return normalized
    return ""


def clerk_development_frontend_api_url(publishable_key: str | None) -> str:
    value = str(publishable_key or "").strip()
    if not value.startswith("pk_test_"):
        return ""
    encoded = value.removeprefix("pk_test_")
    try:
        padding = "=" * (-len(encoded) % 4)
        hostname = urlsafe_b64decode(encoded + padding).decode("utf-8").removesuffix("$")
    except (Base64Error, UnicodeDecodeError, ValueError):
        return ""
    parsed = urlparse(f"https://{hostname}")
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(CLERK_DEVELOPMENT_SUFFIX)
        or parsed.hostname != hostname
        or parsed.port is not None
    ):
        return ""
    return f"https://{parsed.hostname}"


def clerk_runtime_frontend_api_url(
    publishable_key: str | None,
    configured_frontend_api_url: str | None,
) -> str:
    return clerk_development_frontend_api_url(
        publishable_key
    ) or normalize_clerk_frontend_api_url(configured_frontend_api_url)


def csp_source(base: str, extra: str) -> str:
    return f"{base} {extra}" if extra else base


def csp_sources(base: str, *extras: str) -> str:
    values = [base]
    for extra in extras:
        if extra and extra not in values:
            values.append(extra)
    return " ".join(values)


def selected_job_id(params: dict) -> str:
    value = first_query_value(params, "job_id")
    if (value.isdigit() and int(value) > 0) or value.startswith("demo-"):
        return value
    next_url = first_query_value(params, "next")
    if next_url.startswith("/jobs/"):
        raw = next_url.removeprefix("/jobs/").split("?", 1)[0].split("/", 1)[0]
        if raw.isdigit() and int(raw) > 0:
            return raw
    return ""


def selected_job(rows: list, job_id: str):
    if not job_id:
        return None
    for row in rows:
        if str(row_value(row, "id")) == job_id:
            return row
    return None


def photo_count_label(value) -> str:
    try:
        count = int(value or 0)
    except (TypeError, ValueError):
        count = 0
    return f"{count} {'photo' if count == 1 else 'photos'}"


def public_jobs_api_url(params: dict, target: str) -> str:
    args: dict[str, str] = {
        "limit": str(ENTRY_JOB_LIMIT),
        "target": target,
    }
    return "/api/jobs/open?" + urlencode(args)


def entry_redirect_url(path: str, params: dict, intent: str, selected_id: str) -> str:
    if path == "/login":
        next_url = first_query_value(params, "next")
        return next_url if next_url.startswith("/") and not next_url.startswith("//") else "/dashboard"
    args = {"intent": intent}
    if selected_id:
        args["job_id"] = selected_id
    return "/start?" + urlencode(args)


def entry_sign_up_url(path: str, selected_id: str) -> str:
    if path == "/login" and selected_id:
        return "/start?" + urlencode({"intent": "find-work", "job_id": selected_id})
    return "/start"


def job_row(row, selected_id: str, target: str) -> str:
    project = public_job_payload(row, target=target)
    job_id = str(project["id"])
    is_selected = selected_id == job_id
    row_class = "project-result" + (" is-map-active" if is_selected else "")
    current = ' aria-current="true"' if is_selected else ""
    sample = '<span class="sample-badge">Sample</span>' if project["is_demo"] else ""
    return f"""
          <a class="{row_class}" role="listitem" data-job-id="{escape(job_id)}" href="{escape(project['detail_url'])}"{current}>
            <span class="project-result-topline">
              <span>{escape(project['category'])}</span>
              {sample}
            </span>
            <strong>{escape(project['title'])}</strong>
            <span class="project-result-facts">
              <span>{escape(project['city'])}, {escape(project['state'])}</span>
              <span>{escape(project['budget'])}</span>
            </span>
          </a>"""


def job_list_html(rows: list, selected_id: str, target: str) -> str:
    if not rows:
        return """
          <div class="empty-state field-empty-state">
            <img class="empty-state-visual" src="/field-doe.webp" alt="" width="180" height="180">
            <h2>The board is quiet</h2>
            <p>New local projects will appear here.</p>
          </div>"""
    return "\n".join(job_row(row, selected_id, target) for row in rows)


def selected_job_pill(row) -> str:
    if not row:
        return ""
    return f"""
        <div class="selected-lead-pill" aria-label="Selected lead">
          <span>Selected</span>
          <strong>{escape(row_value(row, 'title', '') or '')}</strong>
          <small>{escape(row_value(row, 'city', '') or '')}, {escape(row_value(row, 'state', '') or '')}</small>
        </div>"""


def category_options(selected: str = "") -> str:
    options = ['<option value="">All categories</option>']
    options.extend(
        f'<option value="{escape(category)}" {"selected" if category == selected else ""}>{escape(category)}</option>'
        for category in sorted(JOB_CATEGORIES)
    )
    return "\n".join(options)


def project_detail_html(row, target: str) -> str:
    if not row:
        return """
        <div class="market-detail-empty" data-project-detail-content>
          <img src="/field-doe.webp" alt="" width="160" height="160">
          <h2>No projects match</h2>
          <p>Adjust the filters to widen the map.</p>
        </div>"""
    project = public_job_payload(row, target=target)
    sample = '<span class="sample-badge">Demonstration project</span>' if project["is_demo"] else '<span class="live-badge">Open project</span>'
    date_html = (
        f'<time datetime="{escape(project["desired_date"])}">{escape(project["desired_date"])}</time>'
        if project["desired_date"]
        else "Flexible"
    )
    return f"""
        <article class="market-project-detail" data-project-detail-content data-job-id="{escape(str(project['id']))}">
          <div class="project-detail-heading">
            {sample}
            <span>{escape(project['category'])}</span>
          </div>
          <h2>{escape(project['title'])}</h2>
          <p class="project-detail-location">{escape(project['city'])}, {escape(project['state'])}</p>
          <dl class="project-facts">
            <div><dt>Estimated budget</dt><dd>{escape(project['budget'])}</dd></div>
            <div><dt>Desired date</dt><dd>{date_html}</dd></div>
          </dl>
          <div class="project-description">
            <h3>Field brief</h3>
            <p>{escape(project['description'])}</p>
          </div>
          <p class="project-privacy-note">Location is intentionally approximate until a match is approved.</p>
          <div class="project-detail-actions">
            <a class="button primary" href="{escape(project['url'])}">{escape(project['action_label'])}</a>
            <a class="button secondary" href="{escape(project['detail_url'])}">Open project link</a>
          </div>
        </article>"""


def safe_json_script(value) -> str:
    return (
        json.dumps(value, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def role_segment(intent: str) -> str:
    return f"""
      <fieldset class="segmented-control" data-clerk-role-choice data-email-code-role-choice>
        <legend>What brings you here?</legend>
        <label class="segmented-option">
          <input type="radio" name="intent" value="post-job" {"checked" if intent == "post-job" else ""} required>
          <span><strong>Consumer</strong><small>I need work done</small></span>
        </label>
        <label class="segmented-option">
          <input type="radio" name="intent" value="find-work" {"checked" if intent == "find-work" else ""} required>
          <span><strong>Contractor</strong><small>I am looking for work</small></span>
        </label>
      </fieldset>"""


def shell_csp(
    clerk_frontend_api_url: str,
    include_turnstile: bool = False,
    clerk_publishable_key: str = "",
) -> str:
    clerk_origin = clerk_csp_origin(
        clerk_runtime_frontend_api_url(clerk_publishable_key, clerk_frontend_api_url)
    )
    clerk_enabled = bool(str(clerk_publishable_key or "").strip() or clerk_origin)
    challenge_origin = (
        CLERK_CHALLENGE_ORIGIN if include_turnstile or clerk_enabled else ""
    )
    protect_origin = CLERK_PROTECT_ORIGIN if clerk_enabled else ""
    telemetry_origins = CLERK_TELEMETRY_ORIGINS if clerk_enabled else ("", "")
    frame_source = csp_sources(
        "'self'",
        clerk_origin,
        challenge_origin,
        protect_origin,
    )
    return "; ".join(
        [
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            csp_sources(
                "script-src 'self'",
                clerk_origin,
                challenge_origin,
                protect_origin,
            ),
            "style-src 'self' 'unsafe-inline'",
            csp_sources("style-src-elem 'self' 'unsafe-inline'", clerk_origin),
            "style-src-attr 'unsafe-inline'",
            csp_sources(
                "img-src 'self' data: https://*.tile.openstreetmap.org",
                CLERK_IMAGE_ORIGIN if clerk_enabled else "",
            ),
            csp_sources(
                "connect-src 'self'",
                clerk_origin,
                challenge_origin,
                protect_origin,
                CLERK_IMAGE_ORIGIN if clerk_enabled else "",
                *telemetry_origins,
            ),
            f"frame-src {frame_source}",
            "font-src 'self' data:",
            "media-src 'self'",
            "worker-src 'self' blob:",
            "manifest-src 'self'",
        ]
    )


def shell_headers(
    clerk_frontend_api_url: str,
    include_turnstile: bool = False,
    clerk_publishable_key: str = "",
) -> dict[str, str]:
    return {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Expires": "0",
        "Content-Security-Policy": shell_csp(
            clerk_frontend_api_url,
            include_turnstile=include_turnstile,
            clerk_publishable_key=clerk_publishable_key,
        ),
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    }


def build_entry_shell_html(
    path: str,
    params: dict,
    rows: list,
    clerk_publishable_key: str,
    clerk_frontend_api_url: str,
    auth_provider: str = "clerk",
    turnstile_site_key: str = "",
) -> str:
    native_email_code = auth_provider == "workdoe_email_code"
    development_frontend_api_url = clerk_development_frontend_api_url(
        clerk_publishable_key
    )
    clerk_asset_base_url = development_frontend_api_url or normalize_clerk_frontend_api_url(
        clerk_frontend_api_url
    )
    target = "login" if path == "/login" else "start"
    intent = normalize_intent(first_query_value(params, "intent"), path)
    selected_id = selected_job_id(params)
    selected = selected_job(rows, selected_id) or (rows[0] if rows else None)
    if selected and not selected_id:
        selected_id = str(row_value(selected, "id", ""))
    redirect_url = entry_redirect_url(path, params, intent, selected_id)
    filters = public_job_filters_from_query(params)
    map_payload = public_jobs_payload(rows, filters, target=target)
    jobs_api_url = public_jobs_api_url(params, target)
    proxy_url = (
        ""
        if native_email_code or development_frontend_api_url
        else clerk_proxy_url(clerk_frontend_api_url)
    )
    proxy_data_attr = (
        f'\n          data-clerk-proxy-url="{escape(proxy_url)}"'
        if proxy_url
        else ""
    )
    proxy_script_attr = (
        f' data-clerk-proxy-url="{escape(proxy_url)}"'
        if proxy_url
        else ""
    )
    job_list_role = ' role="list"' if rows else ""
    title = (
        "Sign in - Workdoe"
        if path == "/login"
        else "Join Workdoe" if path == "/start" else "Local projects - Workdoe"
    )
    heading = "Sign in" if path == "/login" else "Join Workdoe"
    eyebrow = "Welcome back" if path == "/login" else "Choose your role"
    panel_id = "signin" if path == "/login" else "start-account"
    clerk_mode = CLERK_SIGNIN_MODE if path == "/login" else CLERK_START_MODE
    sign_up_url = entry_sign_up_url(path, selected_id)
    data_selected = selected_id if selected and selected_id.isdigit() else ""
    browse_current = ' aria-current="page"' if path == "/" else ""
    start_current = ' aria-current="page"' if path == "/start" else ""
    login_current = ' aria-current="page"' if path == "/login" else ""
    onboarding_fields = (
        f"""
{role_segment(intent)}
        <label>
          Name
          <input name="display_name" autocomplete="name" aria-describedby="entry-name-help" data-clerk-display-name data-email-code-display-name>
          <span id="entry-name-help" class="help-text">Shown on your Workdoe profile.</span>
        </label>
        <label>
          Business or household name <span class="optional-label">Optional</span>
          <input name="company_name" autocomplete="organization" data-clerk-company-name data-email-code-company-name>
        </label>"""
        if path != "/login"
        else ""
    )
    start_data_attrs = (
        f"""
          data-onboard-url="/api/auth/onboard"
          data-selected-job-id="{escape(data_selected)}"
          data-post-job-url="/jobs/new"
          data-leads-url="/leads"
"""
        if path != "/login"
        else ""
    )
    if native_email_code:
        turnstile_html = (
            f"""
          <div class="turnstile-field">
            <div class="cf-turnstile" data-sitekey="{escape(turnstile_site_key)}" data-action="{'login' if path == '/login' else 'start'}" data-theme="light"></div>
          </div>"""
            if turnstile_site_key
            else ""
        )
        auth_mount_html = f"""
        <form
          class="email-code-form"
          data-email-code-entry
          data-mode="{'signin' if path == '/login' else 'start'}"
          data-request-url="/api/auth/code/request"
          data-verify-url="/api/auth/code/verify"
          data-redirect-url="{escape(redirect_url)}"
          data-selected-job-id="{escape(data_selected)}"
        >
          <div data-request-step>
            <label>
              Email address
              <input type="email" name="email" autocomplete="email" maxlength="254" required>
            </label>
{onboarding_fields}
{turnstile_html}
            <button class="button primary" type="submit" data-request-code>Email me a code</button>
          </div>
          <div class="email-code-verify" data-code-step hidden>
            <label>
              6-digit code
              <input name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{{6}}" maxlength="6" aria-describedby="email-code-help">
              <span id="email-code-help" class="help-text">The code expires in 10 minutes.</span>
            </label>
            <button class="button primary" type="submit" data-verify-code>Verify and continue</button>
            <button class="button secondary" type="button" data-restart-code>Use a different email</button>
          </div>
          <p class="help-text clerk-entry-status" role="status" aria-live="polite" data-email-code-message></p>
        </form>"""
        auth_scripts_html = (
            (
                '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>\n'
                if turnstile_site_key
                else ""
            )
            + '  <script defer src="/email-code-entry.js"></script>'
        )
    else:
        auth_mount_html = f"""
{onboarding_fields}
        <div
          id="clerk-entry"
          class="clerk-entry-mount"
          data-clerk-entry
          data-clerk-mode="{escape(clerk_mode)}"
          data-redirect-url="{escape(redirect_url)}"
          data-sign-up-url="{escape(sign_up_url)}"
          data-session-url="/api/auth/session"
          data-dashboard-url="/dashboard"
{proxy_data_attr}
{start_data_attrs}
        >
          <form class="email-code-form" data-clerk-email-code-form>
            <div data-clerk-request-step>
              <label>
                Email address
                <input type="email" name="email" autocomplete="email" maxlength="254" required>
              </label>
              <div id="clerk-captcha" data-cl-theme="light" data-cl-size="flexible" data-cl-language="en-US"></div>
              <button class="button primary" type="submit" data-clerk-request-code>Email me a code</button>
            </div>
            <div class="email-code-verify" data-clerk-code-step hidden>
              <label>
                6-digit code
                <input name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{{6}}" maxlength="6" aria-describedby="clerk-code-help">
                <span id="clerk-code-help" class="help-text">The code expires in 10 minutes.</span>
              </label>
              <button class="button primary" type="submit" data-clerk-verify-code>Verify and continue</button>
              <button class="button secondary" type="button" data-clerk-restart-code>Use a different email</button>
            </div>
          </form>
        </div>
        <p class="help-text clerk-entry-status" role="status" aria-live="polite" data-clerk-onboarding-message></p>"""
        auth_scripts_html = f"""  <script defer crossorigin="anonymous" data-clerk-publishable-key="{escape(clerk_publishable_key)}"{proxy_script_attr} src="{escape(clerk_asset_base_url)}/npm/@clerk/clerk-js@6/dist/clerk.browser.js"></script>
  <script defer src="/clerk-entry.js"></script>"""
    if path == "/":
        auth_scripts_html = ""
        right_panel_html = f"""
      <aside class="market-detail-rail" data-market-panel="details" aria-label="Selected project">
{project_detail_html(selected, target)}
      </aside>"""
    else:
        right_panel_html = f"""
      <aside id="{escape(panel_id)}" class="market-detail-rail market-auth-rail" data-market-panel="details" aria-labelledby="entry-title">
        <div class="market-auth-heading">
          <p class="eyebrow">{escape(eyebrow)}</p>
          <h2 id="entry-title">{escape(heading)}</h2>
          <p>{'Use your email code to reopen your workspace.' if path == '/login' else 'Choose a role and verify your email to begin.'}</p>
{selected_job_pill(selected if selected_job_id(params) else None)}
        </div>
{auth_mount_html}
        <div class="auth-switch clerk-entry-note">
          <span>No password needed. Your one-time code arrives by email.</span>
        </div>
      </aside>"""
    mobile_default = "details" if path in {"/login", "/start"} else "map"
    filter_count = len(map_payload["jobs"])
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
  <meta property="og:url" content="https://workdoe.com/">
  <meta property="og:title" content="Workdoe">
  <meta property="og:description" content="Local projects and contractors across the DMV.">
  <meta name="twitter:card" content="summary">
  <title>{escape(title)}</title>
  <link rel="canonical" href="https://workdoe.com/">
  <link rel="icon" href="/deer.svg" type="image/svg+xml">
  <link rel="manifest" href="/site.webmanifest">
  <link rel="stylesheet" href="/styles.css">
  <link rel="stylesheet" href="/vendor/leaflet/leaflet.css">
  <link rel="stylesheet" href="/vendor/leaflet-markercluster/MarkerCluster.css">
  <link rel="stylesheet" href="/vendor/leaflet-markercluster/MarkerCluster.Default.css">
</head>
<body class="market-entry-body" data-default-mobile-panel="{escape(mobile_default)}">
  <a class="skip-link" href="#main-content">Skip to content</a>
  <header class="market-header">
    <a class="brand brand-home-button" href="/" aria-label="Workdoe home">
      <span class="brand-mark"><img class="brand-icon" src="/deer.svg" alt=""></span>
      <span><strong>Workdoe</strong><small>Local work exchange</small></span>
    </a>
    <div class="market-area-label"><span aria-hidden="true"></span>DC, Maryland &amp; Virginia</div>
    <nav class="market-nav" aria-label="Primary">
      <a href="/"{browse_current}>Browse projects</a>
      <a href="/start?intent=post-job"{start_current}>Post a project</a>
      <a href="/login"{login_current}>Sign in</a>
    </nav>
  </header>
  <div class="market-mobile-tabs" role="tablist" aria-label="Marketplace view">
    <button type="button" role="tab" data-mobile-panel-target="filters">Projects</button>
    <button type="button" role="tab" data-mobile-panel-target="map">Map</button>
    <button type="button" role="tab" data-mobile-panel-target="details">Details</button>
  </div>
  <main id="main-content" class="market-workspace" tabindex="-1" data-market-workspace data-mobile-panel="{escape(mobile_default)}">
    <aside class="market-filter-rail" data-market-panel="filters" aria-label="Project search and filters">
      <div class="market-rail-heading">
        <p class="eyebrow">DMV field board</p>
        <h1>Find work nearby</h1>
        <p>Explore approximate locations before creating an account.</p>
      </div>
      <form class="market-filter-form" data-market-filters>
        <label for="market-search">Search projects</label>
        <input id="market-search" type="search" value="{escape(filters.get('q', ''))}" placeholder="Try painting or Arlington" autocomplete="off" data-market-search>
        <label for="market-category">Category</label>
        <select id="market-category" data-market-category>
{category_options(filters.get('category', ''))}
        </select>
        <div class="filter-actions">
          <button class="button secondary compact" type="button" data-clear-market-filters>Clear filters</button>
        </div>
      </form>
      <div class="sample-data-note">
        <span class="sample-badge">Demonstration data</span>
        <p>{map_payload['demo_count']} realistic sample projects show how Workdoe will feel as local jobs arrive.</p>
      </div>
      <div class="project-results-heading">
        <strong data-project-result-count>{filter_count} projects</strong>
        <span>Approximate locations</span>
      </div>
      <div class="project-results" data-project-results aria-label="Available projects"{job_list_role}>
{job_list_html(rows, selected_id, target)}
      </div>
    </aside>
    <section class="market-map-stage" data-market-panel="map" aria-label="Project map workspace">
      <div class="map-stage-toolbar">
        <div>
          <span class="map-live-indicator" aria-hidden="true"></span>
          <strong data-map-result-count>{filter_count} projects mapped</strong>
        </div>
        <span>{map_payload['live_count']} live / {map_payload['demo_count']} sample</span>
      </div>
      <div class="market-map-frame">
        <div id="lead-map" data-map data-map-workspace data-jobs-api="{escape(jobs_api_url)}" role="region" tabindex="0" aria-label="Interactive map of approximate DMV project locations" aria-describedby="lead-map-status">
          <p id="lead-map-loading" class="map-fallback" aria-hidden="true">Loading the project map. The project list is ready.</p>
          <p id="lead-map-status" class="sr-only" aria-live="polite" aria-atomic="true">Loading the project map. The project list is ready.</p>
        </div>
      </div>
    </section>
{right_panel_html}
  </main>
  <script id="map-jobs-data" type="application/json">{safe_json_script(map_payload["jobs"])}</script>
  <script src="/vendor/leaflet/leaflet.js"></script>
  <script src="/vendor/leaflet-markercluster/leaflet.markercluster.js"></script>
  <script src="/map.js"></script>
{auth_scripts_html}
</body>
</html>
"""
