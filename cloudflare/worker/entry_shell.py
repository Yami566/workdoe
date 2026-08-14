from __future__ import annotations

import json
from html import escape
from urllib.parse import urlencode, urlparse

from public_jobs import (
    DEFAULT_JOB_SORT,
    public_job_filters_from_query,
    public_jobs_payload,
)


ENTRY_ROUTES = {"/", "/login", "/start"}
ENTRY_JOB_LIMIT = 18
DEFAULT_CLERK_FRONTEND_API_URL = "https://workdoe.com/__clerk"
CLERK_SIGNIN_MODE = "signin"
CLERK_START_MODE = "start"
WORKDOE_PUBLIC_DOMAIN = "workdoe.com"
CLERK_PROXY_PATH = "/__clerk"


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


def csp_source(base: str, extra: str) -> str:
    return f"{base} {extra}" if extra else base


def selected_job_id(params: dict) -> str:
    value = first_query_value(params, "job_id")
    if value.isdigit() and int(value) > 0:
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
    filters = public_job_filters_from_query(params)
    args: dict[str, str] = {
        "limit": str(ENTRY_JOB_LIMIT),
        "target": target,
    }
    if filters.get("category"):
        args["category"] = filters["category"]
    if filters.get("q"):
        args["q"] = filters["q"]
    if filters.get("sort", DEFAULT_JOB_SORT) != DEFAULT_JOB_SORT:
        args["sort"] = filters["sort"]
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
    job_id = str(row_value(row, "id", ""))
    is_selected = selected_id and selected_id == job_id
    row_class = "job-row link-row compact-lead-row" + (" is-selected" if is_selected else "")
    href = "/login?" + urlencode({"next": f"/jobs/{job_id}"}, safe="/")
    cue = "Sign in" if target == "login" else "Find work"
    if target == "start":
        href = "/start?" + urlencode({"intent": "find-work", "job_id": job_id})
        cue = "Selected" if is_selected else "Find work"
    desired_date = row_value(row, "desired_date", "") or ""
    target_label = (
        f'<span>Target <time datetime="{escape(desired_date)}">{escape(desired_date)}</time></span>'
        if desired_date
        else ""
    )
    current = ' aria-current="true"' if is_selected else ""
    aria_label = (
        f"Selected lead {row_value(row, 'title', '') or ''}"
        if is_selected
        else f"{cue} for {row_value(row, 'title', '') or ''}"
    )
    return f"""
          <a class="{row_class}" role="listitem" data-job-id="{escape(job_id)}" href="{escape(href)}" aria-label="{escape(aria_label)}"{current}>
            <div>
              <div class="row-meta">
                <span>{escape(row_value(row, 'category', '') or '')}</span>
                <span>{escape(row_value(row, 'city', '') or '')}, {escape(row_value(row, 'state', '') or '')}</span>
                {target_label}
                <span>{escape(photo_count_label(row_value(row, 'photo_count', 0)))}</span>
              </div>
              <h3>{escape(row_value(row, 'title', '') or '')}</h3>
            </div>
            <span class="row-cue">{escape(cue)}</span>
          </a>"""


def job_list_html(rows: list, selected_id: str, target: str) -> str:
    if not rows:
        return """
          <div class="empty-state">
            <h2>No open jobs yet</h2>
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
        <legend>Choose your workspace</legend>
        <label class="segmented-option">
          <input type="radio" name="intent" value="post-job" {"checked" if intent == "post-job" else ""} required>
          <span>Post job</span>
        </label>
        <label class="segmented-option">
          <input type="radio" name="intent" value="find-work" {"checked" if intent == "find-work" else ""} required>
          <span>Find work</span>
        </label>
      </fieldset>"""


def shell_csp(clerk_frontend_api_url: str, include_turnstile: bool = False) -> str:
    clerk_origin = clerk_csp_origin(clerk_frontend_api_url)
    turnstile_origin = "https://challenges.cloudflare.com" if include_turnstile else ""
    frame_sources = [source for source in (clerk_origin, turnstile_origin) if source]
    frame_source = " ".join(frame_sources) or "'self'"
    return "; ".join(
        [
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            csp_source(csp_source("script-src 'self'", clerk_origin), turnstile_origin),
            "style-src 'self'",
            csp_source("style-src-elem 'self'", clerk_origin),
            "style-src-attr 'unsafe-inline'",
            "img-src 'self' data: https://*.tile.openstreetmap.org",
            csp_source(csp_source("connect-src 'self'", clerk_origin), turnstile_origin),
            f"frame-src {frame_source}",
            "font-src 'self'",
            "media-src 'self'",
            "worker-src 'none'",
            "manifest-src 'self'",
        ]
    )


def shell_headers(
    clerk_frontend_api_url: str,
    include_turnstile: bool = False,
) -> dict[str, str]:
    return {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Expires": "0",
        "Content-Security-Policy": shell_csp(
            clerk_frontend_api_url,
            include_turnstile=include_turnstile,
        ),
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
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
    target = "login" if path == "/login" else "start"
    intent = normalize_intent(first_query_value(params, "intent"), path)
    selected_id = selected_job_id(params)
    selected = selected_job(rows, selected_id)
    redirect_url = entry_redirect_url(path, params, intent, selected_id)
    filters = public_job_filters_from_query(params)
    map_payload = public_jobs_payload(rows, filters, target=target)
    jobs_api_url = public_jobs_api_url(params, target)
    proxy_url = "" if native_email_code else clerk_proxy_url(clerk_frontend_api_url)
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
    title = "Sign in - Workdoe" if path == "/login" else "Start - Workdoe"
    heading = "Sign in" if path == "/login" else "Start"
    eyebrow = "Welcome back" if path == "/login" else "Workdoe account"
    panel_id = "signin" if path == "/login" else "start-account"
    panel_shortcut_label = "Sign in" if path == "/login" else "Start"
    clerk_mode = CLERK_SIGNIN_MODE if path == "/login" else CLERK_START_MODE
    sign_up_url = entry_sign_up_url(path, selected_id)
    data_selected = selected_id if selected else ""
    start_current = ' aria-current="page"' if path in {"/", "/start"} else ""
    login_current = ' aria-current="page"' if path == "/login" else ""
    checklist_html = (
        """
          <ul class="form-checklist auth-checklist" aria-label="Email code safeguards">
            <li>Email code</li>
            <li>Same site</li>
            <li>No password</li>
          </ul>"""
        if path != "/login"
        else ""
    )
    onboarding_fields = (
        f"""
{role_segment(intent)}
        <label>
          Name
          <input name="display_name" autocomplete="name" aria-describedby="entry-name-help" data-clerk-display-name data-email-code-display-name>
          <span id="entry-name-help" class="help-text">Used after email verification.</span>
        </label>
        <label>
          Company or household
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
            + '  <script defer src="/static/email-code-entry.js"></script>'
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
          <div class="clerk-entry-loading" role="status">Loading secure email sign-in...</div>
        </div>
        <p class="help-text clerk-entry-status" role="status" aria-live="polite" data-clerk-onboarding-message></p>"""
        auth_scripts_html = f"""  <script defer crossorigin="anonymous" src="{escape(clerk_frontend_api_url)}/npm/@clerk/ui@1/dist/ui.browser.js"></script>
  <script defer crossorigin="anonymous" data-clerk-publishable-key="{escape(clerk_publishable_key)}"{proxy_script_attr} src="{escape(clerk_frontend_api_url)}/npm/@clerk/clerk-js@6/dist/clerk.browser.js"></script>
  <script defer src="/static/clerk-entry.js"></script>"""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="description" content="Workdoe helps DMV clients post contractor jobs and review trusted mini bids.">
  <meta name="theme-color" content="#1b5e20">
  <meta name="application-name" content="Workdoe">
  <meta name="mobile-web-app-capable" content="yes">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://workdoe.com/">
  <meta property="og:title" content="Workdoe">
  <meta property="og:description" content="DMV contractor leads with same-site email-code sign-in.">
  <meta name="twitter:card" content="summary">
  <title>{escape(title)}</title>
  <link rel="canonical" href="https://workdoe.com/">
  <link rel="icon" href="/static/deer.svg" type="image/svg+xml">
  <link rel="manifest" href="/static/site.webmanifest">
  <link rel="stylesheet" href="/static/styles.css">
  <link rel="stylesheet" href="/static/vendor/leaflet/leaflet.css">
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to content</a>
  <header class="site-header">
    <a class="brand brand-home-button" href="/" aria-label="Workdoe home">
      <span class="brand-mark"><img class="brand-icon" src="/static/deer.svg" alt=""></span>
      <span><strong>Workdoe</strong><small>DMV contractor leads</small></span>
    </a>
    <nav class="main-nav" aria-label="Primary">
      <a href="/start"{start_current}>Start</a>
      <a href="/login"{login_current}>Sign in</a>
    </nav>
  </header>
  <main id="main-content" tabindex="-1">
    <section class="start-market">
      <div id="live-jobs" class="login-live-panel start-live-panel" tabindex="-1">
        <div class="section-heading compact-heading">
          <p class="eyebrow">Live jobs posted</p>
          <h1>{len(rows)} open leads</h1>
          <a class="entry-shortcut" href="#{escape(panel_id)}">{escape(panel_shortcut_label)}</a>
        </div>
        <div class="login-board start-board">
          <div class="map-panel login-map-panel">
            <div id="lead-map" data-map data-jobs-api="{escape(jobs_api_url)}" role="region" tabindex="0" aria-label="Approximate DMV job map while signing in" aria-describedby="lead-map-status">
              <p id="lead-map-loading" class="map-fallback" aria-hidden="true">Map loading. Job list is ready.</p>
              <p id="lead-map-status" class="sr-only" aria-live="polite" aria-atomic="true">Map loading. Job list is ready.</p>
            </div>
          </div>
          <div class="job-list login-job-list" aria-label="Open jobs while signing in"{job_list_role}>
{job_list_html(rows, selected_id, target)}
          </div>
        </div>
      </div>
      <section id="{escape(panel_id)}" class="form-panel login-form-panel start-form-panel clerk-entry-panel" aria-labelledby="entry-title">
        <div>
          <p class="eyebrow">{escape(eyebrow)}</p>
          <h2 id="entry-title">{escape(heading)}</h2>
          <nav class="entry-shortcuts" aria-label="{escape(heading)} shortcuts">
            <a href="#live-jobs">Live jobs</a>
          </nav>
{checklist_html}
{selected_job_pill(selected)}
        </div>
{auth_mount_html}
        <div class="auth-switch clerk-entry-note">
          <span>Email code sign-in stays on workdoe.com.</span>
        </div>
      </section>
    </section>
  </main>
  <script id="map-jobs-data" type="application/json">{safe_json_script(map_payload["jobs"])}</script>
  <script src="/static/vendor/leaflet/leaflet.js"></script>
  <script src="/static/map.js"></script>
{auth_scripts_html}
</body>
</html>
"""
