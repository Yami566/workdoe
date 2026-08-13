from __future__ import annotations

import json
from html import escape
from urllib.parse import urlencode

from job_posts import DMV_ZIPS, JOB_CATEGORIES


APP_SHELL_ROUTES = {
    "/dashboard",
    "/client/dashboard",
    "/contractor/dashboard",
    "/leads",
    "/jobs/new",
    "/contractor/profile",
    "/messages",
    "/admin",
}


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def is_app_shell_route(path: str) -> bool:
    if path in APP_SHELL_ROUTES:
        return True
    if path.startswith("/client/jobs/"):
        raw = path.removeprefix("/client/jobs/").strip("/")
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
    return "/start"


def parse_app_job_id(path: str) -> int:
    raw = path.removeprefix("/jobs/").strip("/")
    return int(raw) if raw.isdigit() and int(raw) > 0 else 0


def parse_app_client_job_id(path: str) -> int:
    raw = path.removeprefix("/client/jobs/").strip("/")
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


def app_shell_csp(include_map: bool = False, include_turnstile: bool = False) -> str:
    script_sources = ["'self'"]
    frame_sources = []
    connect_sources = ["'self'"]
    if include_turnstile:
        script_sources.append("https://challenges.cloudflare.com")
        frame_sources.append("https://challenges.cloudflare.com")
        connect_sources.append("https://challenges.cloudflare.com")
    img_sources = ["'self'", "data:"]
    if include_map:
        img_sources.append("https://*.tile.openstreetmap.org")
    directives = [
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "script-src " + " ".join(script_sources),
        "style-src 'self'",
        "style-src-elem 'self'",
        "style-src-attr 'unsafe-inline'",
        "img-src " + " ".join(img_sources),
        "connect-src " + " ".join(connect_sources),
        "font-src 'self'",
        "media-src 'self'",
        "worker-src 'none'",
        "manifest-src 'self'",
    ]
    if frame_sources:
        directives.append("frame-src " + " ".join(frame_sources))
    return "; ".join(directives)


def app_shell_headers(include_map: bool = False, include_turnstile: bool = False) -> dict[str, str]:
    return {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Expires": "0",
        "Content-Security-Policy": app_shell_csp(
            include_map=include_map,
            include_turnstile=include_turnstile,
        ),
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
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


def nav_links(user, active_path: str) -> str:
    role = row_value(user, "role")
    links: list[tuple[str, str]] = []
    if role == "client":
        links = [("/client/dashboard", "Dashboard"), ("/jobs/new", "Post Job"), ("/messages", "Messages")]
    elif role == "contractor":
        links = [("/leads", "Leads"), ("/contractor/dashboard", "Bids"), ("/contractor/profile", "Profile"), ("/messages", "Messages")]
    elif role == "admin":
        links = [("/admin", "Admin")]
    return "\n".join(
        f'<a href="{escape(href)}"{" aria-current=\"page\"" if href == active_path else ""}>{escape(label)}</a>'
        for href, label in links
    )


def layout(
    user,
    active_path: str,
    title: str,
    body: str,
    *,
    include_map: bool = False,
    include_actions: bool = False,
    include_turnstile: bool = False,
) -> str:
    scripts = []
    if include_turnstile:
        scripts.append('<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>')
    if include_map:
        scripts.extend(
            [
                '<script src="/static/vendor/leaflet/leaflet.js"></script>',
                '<script src="/static/map.js"></script>',
            ]
        )
    if include_actions:
        scripts.append('<script defer src="/static/worker-actions.js"></script>')
    script_html = "\n  ".join(scripts)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Workdoe helps DMV clients post contractor jobs and review trusted mini bids.">
  <title>{escape(title)} - Workdoe</title>
  <link rel="stylesheet" href="/static/styles.css">
  {"<link rel=\"stylesheet\" href=\"/static/vendor/leaflet/leaflet.css\">" if include_map else ""}
  {script_html}
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to content</a>
  <header class="site-header">
    <a class="brand brand-home-button" href="/" aria-label="Workdoe home">
      <span class="brand-mark"><img class="brand-icon" src="/static/deer.svg" alt=""></span>
      <span><strong>Workdoe</strong><small>DMV contractor leads</small></span>
    </a>
    <nav class="main-nav" aria-label="Primary">
      {nav_links(user, active_path)}
    </nav>
  </header>
  <main id="main-content" tabindex="-1">
{body}
  </main>
  <footer class="site-footer">
    <span>workdoe.com</span>
    <span>DMV beta: DC, Maryland, Virginia</span>
  </footer>
</body>
</html>
"""


def empty_state(title: str, href: str, label: str) -> str:
    return f"""
    <div class="empty-state">
      <h2>{escape(title)}</h2>
      <a class="button secondary" href="{escape(href)}">{escape(label)}</a>
    </div>"""


def client_dashboard_html(user, payload: dict) -> str:
    jobs = payload.get("jobs", [])
    stats = payload.get("stats", {})
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
          <span>{escape(job.get('category', ''))}</span>
          <span>{escape(job.get('city', ''))}, {escape(job.get('state', ''))}</span>
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
    job_html = "\n".join(rows) if rows else empty_state("No jobs yet", "/jobs/new", "Post a job")
    body = f"""
    <section class="dashboard-header">
      <div>
        <p class="eyebrow">Client dashboard</p>
        <h1>Your jobs</h1>
      </div>
      <a class="button" href="/jobs/new">Post a job</a>
    </section>
    <section class="dashboard-metrics" aria-label="Client work queue">
      <div class="metric-card"><span>Open</span><strong>{int(stats.get('open_jobs', 0))}</strong></div>
      <div class="metric-card"><span>Pending bids</span><strong>{int(stats.get('pending_requests', 0))}</strong></div>
      <div class="metric-card"><span>Total jobs</span><strong>{int(stats.get('total_jobs', 0))}</strong></div>
    </section>
    <section class="job-list" aria-label="Client jobs">
{job_html}
    </section>"""
    return layout(user, "/client/dashboard", "Client Dashboard", body)


def contractor_dashboard_html(user, payload: dict) -> str:
    bids = payload.get("bids", [])
    stats = payload.get("stats", {})
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
      <div>
        <div class="row-meta">
          <span class="status {escape(bid.get('status', ''))}">{escape(bid.get('status', ''))}</span>
          <span>{escape(bid.get('category', ''))}</span>
          <span>{escape(bid.get('city', ''))}, {escape(bid.get('state', ''))}</span>
        </div>
        <h2>{escape(bid.get('title', ''))}</h2>
        <p class="job-summary">{escape(bid.get('scope_note', ''))}</p>
      </div>
      <span class="row-cue">{escape(row_cue)}</span>
    </a>"""
        )
    bid_html = "\n".join(rows) if rows else empty_state("No mini bids yet", "/leads", "Browse leads")
    body = f"""
    <section class="dashboard-header">
      <div>
        <p class="eyebrow">Contractor dashboard</p>
        <h1>Your mini bids</h1>
      </div>
      <a class="button" href="/leads">Browse leads</a>
    </section>
    <section class="dashboard-metrics" aria-label="Contractor work queue">
      <div class="metric-card"><span>Pending</span><strong>{int(stats.get('pending_requests', 0))}</strong></div>
      <div class="metric-card"><span>Approved</span><strong>{int(stats.get('approved_requests', 0))}</strong></div>
      <div class="metric-card"><span>Total bids</span><strong>{int(stats.get('total_requests', 0))}</strong></div>
    </section>
    <section class="job-list" aria-label="Contractor mini bids">
{bid_html}
    </section>"""
    return layout(user, "/contractor/dashboard", "Contractor Dashboard", body)


def lead_board_html(user, payload: dict) -> str:
    jobs = payload.get("jobs", [])
    rows = []
    for job in jobs:
        row_cue = str(job.get("row_cue", "View") or "View")
        row_label = (
            f"Open sent bid for {job.get('title', 'lead')}"
            if row_cue == "Sent"
            else f"View {job.get('title', 'lead')}"
        )
        rows.append(
            f"""
      <a class="job-row link-row" role="listitem" data-job-id="{escape(str(job.get('id', '')))}" href="{escape(job.get('url', '#'))}" aria-label="{escape(row_label)}">
        <div>
          <div class="row-meta">
            <span>{escape(job.get('category', ''))}</span>
            <span>{escape(job.get('city', ''))}, {escape(job.get('state', ''))}</span>
            <span>{escape(photo_count_label(job.get('photo_count', 0)))}</span>
            {('<span class="status ' + escape(job.get('request_status', '')) + '">bid ' + escape(job.get('request_status', '')) + '</span>') if job.get('request_status') else ''}
          </div>
          <h2>{escape(job.get('title', ''))}</h2>
          <p class="job-summary">{escape(job.get('description', ''))}</p>
        </div>
        <span class="row-cue">{escape(row_cue)}</span>
      </a>"""
        )
    list_html = "\n".join(rows) if rows else empty_state("No leads match this view", "/leads", "Clear filters")
    map_jobs = payload.get("map_jobs", [])
    list_role = ' role="list"' if rows else ""
    body = f"""
    <section class="dashboard-header">
      <div>
        <p class="eyebrow">Lead board</p>
        <h1>Open DMV jobs</h1>
        <p>Approximate pins until matched.</p>
      </div>
    </section>
    <section class="lead-layout">
      <div class="job-list lead-job-list" aria-label="Open leads"{list_role}>
{list_html}
      </div>
      <div class="map-panel lead-map-panel">
        <div id="lead-map" data-map role="region" tabindex="0" aria-label="Approximate DMV job map" aria-describedby="lead-map-status">
          <p id="lead-map-loading" class="map-fallback" aria-hidden="true">Map loading. Job list is ready.</p>
          <p id="lead-map-status" class="sr-only" aria-live="polite" aria-atomic="true">Map loading. Job list is ready.</p>
        </div>
      </div>
    </section>
    <script id="map-jobs-data" type="application/json">{safe_json_script(map_jobs)}</script>"""
    return layout(user, "/leads", "Lead Board", body, include_map=True)


def turnstile_html(site_key: str, action: str) -> str:
    if not site_key:
        return ""
    return f"""
        <div class="turnstile-field">
          <div class="cf-turnstile" data-sitekey="{escape(site_key)}" data-action="{escape(action)}" data-theme="light"></div>
        </div>"""


def job_form_html(user, site_key: str = "") -> str:
    category_options = "\n".join(
        f'<option value="{escape(category)}">{escape(category)}</option>'
        for category in sorted(JOB_CATEGORIES)
    )
    city_options = dmv_city_options_html()
    zip_options = dmv_zip_options_html()
    body = f"""
    <section class="dashboard-header">
      <div>
        <p class="eyebrow">New client job</p>
        <h1>Post a job.</h1>
      </div>
      <a class="button secondary" href="/client/dashboard">Dashboard</a>
    </section>
    <ul class="form-checklist" aria-label="Posting safeguards">
      <li>City/ZIP pin</li>
      <li>Private photos</li>
      <li>Approve before chat</li>
    </ul>
    <form class="form-grid" data-json-action="/api/jobs" data-upload-after-json-template="/api/media/jobs/{{job_id}}/upload" data-success-url-template="/client/jobs/{{id}}" aria-label="Post a job." aria-describedby="worker-form-status">
      <label class="wide" for="job-title">Job title <input id="job-title" name="title" maxlength="90" autocomplete="off" autocapitalize="sentences" spellcheck="true" enterkeyhint="next" placeholder="Power wash front steps and patio" required></label>
      <label for="job-category">Category <select id="job-category" name="category" required>{category_options}</select></label>
      <label for="job-desired-date">Desired date <input id="job-desired-date" name="desired_date" type="date"></label>
      <label for="job-city">City <input id="job-city" name="city" maxlength="80" autocomplete="address-level2" autocapitalize="words" spellcheck="false" list="job-city-options" enterkeyhint="next" placeholder="Washington" required></label>
      <label for="job-state">State <select id="job-state" name="state" autocomplete="address-level1" required><option value="DC">DC</option><option value="MD">MD</option><option value="VA">VA</option></select></label>
      <label for="job-zip-code">ZIP <input id="job-zip-code" name="zip_code" pattern="[0-9]{{5}}" maxlength="5" inputmode="numeric" autocomplete="postal-code" list="job-zip-options" enterkeyhint="next" placeholder="20003" required></label>
      <datalist id="job-city-options">
{city_options}
      </datalist>
      <datalist id="job-zip-options">
{zip_options}
      </datalist>
      <label class="wide" for="job-description">Description <textarea id="job-description" name="description" rows="5" minlength="20" maxlength="1200" autocapitalize="sentences" spellcheck="true" enterkeyhint="done" placeholder="Scope, access, timing, and desired outcome." required></textarea></label>
      <label class="wide" for="job-photos">Photos <input id="job-photos" name="photos" type="file" accept="image/png,image/jpeg,image/gif,image/webp" multiple aria-describedby="job-photos-help"></label>
      <p id="job-photos-help" class="help-text wide">Private uploads. PNG, JPG, GIF, or WebP.</p>
      {turnstile_html(site_key, "job-post")}
      <div class="form-actions wide">
        <button class="button" type="submit" aria-label="Post job">Post job</button>
        <p id="worker-form-status" class="help-text" data-form-status aria-live="polite"></p>
      </div>
    </form>"""
    return layout(user, "/jobs/new", "Post Job", body, include_actions=True, include_turnstile=bool(site_key))


def contractor_profile_html(user, profile: dict, photos: list[dict] | None = None) -> str:
    selected_trades = {
        item.strip()
        for item in str(profile.get("trades", "") or "").split(",")
        if item.strip()
    }
    trade_options = "\n".join(
        f"""
      <label for="profile-trade-{index}">
        <input id="profile-trade-{index}" type="checkbox" name="trades" value="{escape(category)}"{" checked" if category in selected_trades else ""}>
        {escape(category)}
      </label>"""
        for index, category in enumerate(sorted(JOB_CATEGORIES), start=1)
    )
    years = profile.get("years_in_business")
    years_value = "" if years is None else str(years)
    contractor_id = int(row_value(user, "id", 0) or 0)
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
    body = f"""
    <section class="dashboard-header">
      <div>
        <p class="eyebrow">Contractor profile</p>
        <h1>Profile setup</h1>
        <p>Clients see this when they review your mini bid.</p>
      </div>
      <a class="button secondary" href="/contractors/{contractor_id}">Preview</a>
    </section>
    <form class="form-grid" data-json-action="/api/contractor/profile" data-success-url-template="/contractor/profile" aria-label="Contractor profile" aria-describedby="profile-form-status">
      <label class="wide" for="profile-business-name">Business name <input id="profile-business-name" name="business_name" value="{escape(profile.get('business_name', ''))}" maxlength="120" autocomplete="organization" autocapitalize="words" spellcheck="false" enterkeyhint="next" required></label>
      <fieldset class="wide checkbox-grid" id="profile-trades">
        <legend>Trades</legend>
{trade_options}
      </fieldset>
      <label for="profile-service-area">Service area <input id="profile-service-area" name="service_area" value="{escape(profile.get('service_area', ''))}" maxlength="160" autocomplete="address-level2" autocapitalize="words" spellcheck="false" enterkeyhint="next" placeholder="DC, Montgomery County, Northern Virginia" required></label>
      <label for="profile-years-in-business">Years in business <input id="profile-years-in-business" name="years_in_business" type="number" min="0" max="100" value="{escape(years_value)}" inputmode="numeric" enterkeyhint="next"></label>
      <label for="profile-insurance-status">Insurance status <input id="profile-insurance-status" name="insurance_status" value="{escape(profile.get('insurance_status', ''))}" maxlength="120" autocapitalize="sentences" spellcheck="true" enterkeyhint="next" placeholder="Available on request"></label>
      <label for="profile-license-number">License number <input id="profile-license-number" name="license_number" value="{escape(profile.get('license_number', ''))}" maxlength="80" autocapitalize="characters" spellcheck="false" enterkeyhint="next" placeholder="Optional for the local beta"></label>
      <label for="profile-website">Website <input id="profile-website" name="website" type="url" value="{escape(profile.get('website', ''))}" maxlength="200" autocomplete="url" autocapitalize="off" spellcheck="false" enterkeyhint="next" placeholder="https://example.com"></label>
      <label for="profile-phone">Phone <input id="profile-phone" name="phone" type="tel" value="{escape(profile.get('phone', ''))}" maxlength="40" autocomplete="tel" inputmode="tel" enterkeyhint="next" placeholder="Optional"></label>
      <label class="wide" for="profile-intro">Intro <textarea id="profile-intro" name="intro" rows="5" minlength="20" maxlength="900" autocapitalize="sentences" spellcheck="true" enterkeyhint="done" placeholder="Describe your crew, service style, and ideal jobs." required>{escape(profile.get('intro', ''))}</textarea></label>
      <div class="form-actions wide">
        <button class="button" type="submit">Save profile</button>
        <p id="profile-form-status" class="help-text" data-form-status aria-live="polite"></p>
      </div>
    </form>
    <section class="detail-grid">
      <form class="panel stack-form" data-file-action="/api/media/contractors/{contractor_id}/upload" data-success-url-template="/contractor/profile" enctype="multipart/form-data" aria-describedby="profile-upload-status">
        <h2>Portfolio photo</h2>
        <label for="profile-photos">Image <input id="profile-photos" name="portfolio_photo" type="file" accept="image/png,image/jpeg,image/gif,image/webp" aria-describedby="profile-photos-help" required></label>
        <p id="profile-photos-help" class="help-text">Private uploads. PNG, JPG, GIF, or WebP.</p>
        <button class="button secondary" type="submit">Upload photo</button>
        <p id="profile-upload-status" class="help-text" data-form-status aria-live="polite"></p>
      </form>
      <section class="photo-grid profile-photos" aria-label="Portfolio photos">
{photo_html}
      </section>
    </section>"""
    return layout(user, "/contractor/profile", "Contractor Profile", body, include_actions=True)


def public_contractor_profile_html(user, payload: dict) -> str:
    contractor = payload.get("contractor", {})
    photos = contractor.get("photos", [])
    contractor_id = int(contractor.get("id", 0) or 0)
    photo_html = "\n".join(
        f'<figure><img src="{escape(photo.get("url", ""))}" alt="Portfolio photo"><figcaption>{escape(photo.get("original_filename", ""))}</figcaption></figure>'
        for photo in photos
    )
    if not photo_html:
        photo_html = """
        <div class="empty-state">
          <h2>No portfolio photos yet</h2>
          <p class="help-text">Clients can still review this contractor through mini bids.</p>
        </div>"""
    years = contractor.get("years_in_business")
    year_label = "Not listed" if years in {"", None} else str(years)
    status_html = (
        f'<span class="status {escape(contractor.get("status", ""))}">{escape(contractor.get("status", ""))}</span>'
        if contractor.get("status")
        else ""
    )
    body = f"""
    <section class="dashboard-header">
      <div>
        <p class="eyebrow">Contractor profile</p>
        <h1>{escape(contractor.get('business_name', 'Workdoe contractor'))}</h1>
        <p>{escape(contractor.get('trades', 'DMV contractor'))}</p>
      </div>
      {status_html}
    </section>
    <section class="detail-grid">
      <article class="panel">
        <h2>About</h2>
        <p class="preline">{escape(contractor.get('intro', ''))}</p>
        <dl class="profile-facts">
          <div><dt>Service area</dt><dd>{escape(contractor.get('service_area', 'DMV area'))}</dd></div>
          <div><dt>Insurance</dt><dd>{escape(contractor.get('insurance_status', 'Available on request'))}</dd></div>
          <div><dt>License</dt><dd>{escape(contractor.get('license_number', 'Not listed'))}</dd></div>
          <div><dt>Years</dt><dd>{escape(year_label)}</dd></div>
        </dl>
        <p class="help-text">{escape(contractor.get('contact_policy', 'Clients approve a mini bid before messaging opens.'))}</p>
      </article>
      <aside class="panel">
        <h2>Portfolio</h2>
        <div class="photo-grid">
{photo_html}
        </div>
      </aside>
    </section>
    <section class="action-row">
      <a class="button secondary" href="/leads">Back to leads</a>
      <a class="button secondary" href="/login?next=/contractors/{contractor_id}">Sign in</a>
    </section>"""
    return layout(user, f"/contractors/{contractor_id}", contractor.get("business_name", "Contractor Profile"), body)


def message_threads_html(user, payload: dict) -> str:
    threads = payload.get("threads", [])
    stats = payload.get("stats", {})
    rows = []
    for thread in threads:
        rows.append(
            f"""
    <a class="job-row link-row" href="{escape(thread.get('url', '#'))}" aria-label="Open message thread for {escape(thread.get('title', 'message thread'))}">
      <span>
        <span class="row-meta">
          <span>{escape(thread.get('category', ''))}</span>
          <span>{escape(thread.get('city', ''))}, {escape(thread.get('state', ''))}</span>
          <span>{escape(message_count_label(thread.get('message_count', 0)))}</span>
        </span>
        <strong>{escape(thread.get('title', 'Message thread'))}</strong>
        <small>{escape(thread.get('client_name', 'Client'))} and {escape(thread.get('contractor_name', 'Contractor'))}</small>
        <small class="thread-preview">{escape(thread.get('last_message') or 'No messages yet')}</small>
      </span>
      <span class="button secondary compact">Open</span>
    </a>"""
        )
    thread_html = "\n".join(rows) if rows else empty_state("No message threads yet", "/dashboard", "Back to dashboard")
    body = f"""
    <section class="page-header">
      <p class="eyebrow">Approved matches</p>
      <h1>Messages</h1>
    </section>
    <section class="dashboard-metrics compact-metrics" aria-label="Message summary">
      <div class="metric-card"><span>Threads</span><strong>{int(stats.get('threads', 0))}</strong></div>
      <div class="metric-card"><span>Messages</span><strong>{int(stats.get('messages', 0))}</strong></div>
    </section>
    <section class="job-list" aria-label="Message threads">
{thread_html}
    </section>"""
    return layout(user, "/messages", "Messages", body)


def message_thread_detail_html(user, payload: dict, can_reply: bool = True) -> str:
    thread = payload.get("thread", {})
    messages = payload.get("messages", [])
    thread_id = int(thread.get("id", 0) or 0)
    user_id = int(row_value(user, "id", 0) or 0)
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
    <form class="message-form" data-json-action="/api/messages/threads/{thread_id}" data-success-url-template="/messages/{thread_id}" aria-label="New message">
      <label>New message <textarea name="body" rows="4" maxlength="1000" placeholder="Share timing, access, or next steps." autocapitalize="sentences" spellcheck="true" enterkeyhint="send" required></textarea></label>
      <button class="button full" type="submit" aria-label="Send message">Send</button>
      <p class="help-text" data-form-status aria-live="polite"></p>
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
    <section class="message-shell">
      <div class="message-list">
{messages_html}
      </div>
{reply_html}
    </section>"""
    return layout(user, f"/messages/{thread_id}", "Message Thread", body, include_actions=can_reply)


def admin_action_form(action_url: str, label: str) -> str:
    return f"""
        <form data-json-action="{escape(action_url)}" data-success-url-template="/admin">
          <button class="button secondary compact" type="submit">{escape(label)}</button>
          <span class="sr-only" data-form-status aria-live="polite"></span>
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
                f"{job.get('category', '')} - {job.get('city', '')}, {job.get('state', '')} - {job.get('status', '')}",
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
    message_rows = []
    for message in payload.get("messages", []):
        action_url = "" if int(message.get("is_hidden", 0) or 0) else f"/api/admin/messages/{int(message.get('id', 0) or 0)}/hide"
        message_rows.append(
            admin_row(
                message.get("sender_email", "Workdoe user"),
                f"{message.get('job_title', '')} - {str(message.get('body', ''))[:90]}",
                action_url=action_url,
                action_label="Hide" if action_url else "",
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
    body = f"""
    <section class="page-header">
      <p class="eyebrow">Admin</p>
      <h1>Moderation console</h1>
    </section>
    <section class="dashboard-metrics compact-metrics" aria-label="Moderation summary">
      <div class="metric-card"><span>Open reports</span><strong>{int(stats.get('open_reports', 0))}</strong></div>
      <div class="metric-card"><span>Suspended</span><strong>{int(stats.get('suspended_users', 0))}</strong></div>
      <div class="metric-card"><span>Hidden</span><strong>{int(stats.get('hidden_content', 0))}</strong></div>
      <div class="metric-card"><span>Audit</span><strong>{int(stats.get('audit_actions', 0))}</strong></div>
      <div class="metric-card"><span>Automation</span><strong>{int(stats.get('automation_events', 0))}</strong></div>
    </section>
    <section class="admin-grid">
      {admin_panel("Open reports", report_rows, "No open reports.")}
      {admin_panel("Users", user_rows, "No users yet.")}
      {admin_panel("Jobs", job_rows, "No jobs yet.")}
      {admin_panel("Job photos", photo_rows, "No uploaded job photos yet.")}
      {admin_panel("Portfolio photos", contractor_photo_rows, "No portfolio photos yet.")}
      {admin_panel("Recent messages", message_rows, "No messages yet.")}
      {admin_panel("Audit trail", action_rows, "No moderation actions yet.")}
      {admin_panel("Automation", automation_rows, "No automation events yet.")}
    </section>"""
    return layout(user, "/admin", "Admin", body, include_actions=True)


def contractor_job_detail_html(user, payload: dict, site_key: str = "") -> str:
    job = payload.get("job", {})
    existing = payload.get("existing_request")
    photos = payload.get("photos", [])
    photo_html = "\n".join(
        f'<figure><img src="{escape(photo.get("url", ""))}" alt="Job photo"><figcaption>{escape(photo.get("original_filename", ""))}</figcaption></figure>'
        for photo in photos
    )
    if existing:
        side = f"""
        <h2>Mini bid sent</h2>
        <p>Your request is currently <strong>{escape(existing.get('status', ''))}</strong>.</p>
        <dl class="profile-facts compact-facts">
          <div><dt>Price</dt><dd>{escape(existing.get('price_range', ''))}</dd></div>
          <div><dt>Timeline</dt><dd>{escape(existing.get('timeline', ''))}</dd></div>
          <div><dt>Availability</dt><dd>{escape(existing.get('availability', ''))}</dd></div>
        </dl>
        <a class="button secondary full" href="/leads">Back to leads</a>"""
    elif job.get("can_request_match"):
        side = f"""
        <h2>Send mini bid</h2>
        <form class="stack-form bid-form" data-json-action="/api/jobs/{int(job.get('id', 0))}/request" data-success-url-template="/jobs/{int(job.get('id', 0))}" aria-label="Send mini bid">
          <label for="bid-scope-note">Scope note <textarea id="bid-scope-note" name="scope_note" rows="4" minlength="20" maxlength="800" placeholder="Work included, assumptions, access needs." autocapitalize="sentences" spellcheck="true" enterkeyhint="next" required></textarea></label>
          <div class="bid-quick-grid">
            <label for="bid-price-range">Price range <input id="bid-price-range" name="price_range" maxlength="80" inputmode="text" placeholder="$450-$650" list="bid-price-options" enterkeyhint="next" required></label>
            <label for="bid-timeline">Timeline <input id="bid-timeline" name="timeline" maxlength="120" placeholder="Next week" list="bid-timeline-options" autocapitalize="sentences" spellcheck="true" enterkeyhint="next" required></label>
            <label for="bid-availability">Availability <input id="bid-availability" name="availability" maxlength="120" placeholder="Tue/Thu PM" list="bid-availability-options" autocapitalize="sentences" spellcheck="true" enterkeyhint="next" required></label>
          </div>
          <label for="bid-experience">Relevant experience <textarea id="bid-experience" name="experience" rows="3" minlength="20" maxlength="800" placeholder="Similar work or crew capability." autocapitalize="sentences" spellcheck="true" enterkeyhint="next" required></textarea></label>
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
          <details class="optional-field"><summary>Questions (optional)</summary><label class="sr-only" for="bid-questions">Questions</label><textarea id="bid-questions" name="questions" rows="2" maxlength="500" placeholder="Optional" autocapitalize="sentences" spellcheck="true" enterkeyhint="done"></textarea></details>
          {turnstile_html(site_key, "match-request")}
          <button class="button full" type="submit" aria-label="Send mini bid">Send bid</button>
          <p class="help-text" data-form-status aria-live="polite"></p>
        </form>"""
    else:
        side = '<h2>Lead unavailable</h2><p class="help-text">This lead is not open for a new mini bid.</p>'
    body = f"""
    <section class="dashboard-header">
      <div>
        <p class="eyebrow">Contractor lead</p>
        <h1>{escape(job.get('title', 'Lead'))}</h1>
        <p>{escape(job.get('category', ''))} in {escape(job.get('area_label', ''))}</p>
      </div>
      <span class="status {escape(job.get('status', ''))}">{escape(job.get('status', ''))}</span>
    </section>
    <section class="detail-grid">
      <article class="panel">
        <h2>Job details</h2>
        <dl class="job-facts">
          <div><dt>Trade</dt><dd>{escape(job.get('category', ''))}</dd></div>
          <div><dt>Area</dt><dd>{escape(job.get('area_label', ''))}</dd></div>
          <div><dt>Photos</dt><dd>{len(photos)}</dd></div>
        </dl>
        <p class="preline">{escape(job.get('description', ''))}</p>
        <p class="help-text">{escape(job.get('location_privacy', ''))}</p>
        <div class="photo-grid">{photo_html}</div>
      </article>
      <aside class="panel">{side}</aside>
    </section>"""
    return layout(user, "/leads", job.get("title", "Lead"), body, include_actions=True, include_turnstile=bool(site_key))


def client_job_detail_html(user, detail_payload: dict, requests_payload: dict) -> str:
    job = detail_payload.get("job", {})
    requests = requests_payload.get("requests", [])
    stats = requests_payload.get("stats", {})
    view_links = requests_payload.get("view_links", [])
    photos = detail_payload.get("photos", [])
    view = requests_payload.get("view", "all")
    job_id = int(job.get("id", 0) or 0)
    photo_html = "\n".join(
        f'<figure><img src="{escape(photo.get("url", ""))}" alt="Job photo"><figcaption>{escape(photo.get("original_filename", ""))}</figcaption></figure>'
        for photo in photos
    )
    link_html = "\n".join(
        f'<a href="{escape(link.get("url", "#"))}"{" aria-current=\"page\"" if link.get("value") == view else ""}>{escape(link.get("label", ""))}</a>'
        for link in view_links
    )
    status = job.get("status", "")
    if status == "open":
        status_form = f"""
        <form data-json-action="/api/jobs/{job_id}/close" data-success-url-template="/client/jobs/{job_id}">
          <button class="button secondary full" type="submit">Close job</button>
          <p class="help-text" data-form-status aria-live="polite"></p>
        </form>"""
    elif status == "closed":
        status_form = f"""
        <form data-json-action="/api/jobs/{job_id}/reopen" data-success-url-template="/client/jobs/{job_id}">
          <button class="button secondary full" type="submit">Reopen job</button>
          <p class="help-text" data-form-status aria-live="polite"></p>
        </form>"""
    else:
        status_form = '<p class="help-text">This job is hidden by moderation.</p>'
    request_rows = []
    for request in requests:
        request_id = int(request.get("id", 0) or 0)
        status = request.get("status", "")
        actions = ""
        if request.get("can_approve"):
            actions = f"""
          <div class="bid-actions">
            <form data-json-action="/api/match-requests/{request_id}/approve" data-success-url-template="/client/jobs/{job_id}">
              <button class="button" type="submit">Approve</button>
              <p class="help-text" data-form-status aria-live="polite"></p>
            </form>
            <form data-json-action="/api/match-requests/{request_id}/reject" data-success-url-template="/client/jobs/{job_id}">
              <button class="button secondary" type="submit">Reject</button>
              <p class="help-text" data-form-status aria-live="polite"></p>
            </form>
          </div>"""
        elif request.get("thread_url"):
            actions = f'<a class="button secondary" href="{escape(request.get("thread_url", ""))}">Message</a>'
        request_rows.append(
            f"""
      <article class="bid-card">
        <div class="row-meta">
          <span class="status {escape(status)}">{escape(status)}</span>
          <span>{escape(request.get('trades', 'Contractor profile'))}</span>
        </div>
        <h2>{escape(request.get('contractor_name', 'Contractor'))}</h2>
        <p class="job-summary">{escape(request.get('scope_note', ''))}</p>
        <dl class="profile-facts compact-facts">
          <div><dt>Price</dt><dd>{escape(request.get('price_range', ''))}</dd></div>
          <div><dt>Timeline</dt><dd>{escape(request.get('timeline', ''))}</dd></div>
          <div><dt>Availability</dt><dd>{escape(request.get('availability', ''))}</dd></div>
        </dl>
        <details class="optional-field"><summary>Experience</summary><p class="preline">{escape(request.get('experience', ''))}</p></details>
        {('<details class="optional-field"><summary>Questions</summary><p class="preline">' + escape(request.get('questions', '')) + '</p></details>') if request.get('questions') else ''}
        {actions}
      </article>"""
        )
    requests_html = "\n".join(request_rows) if request_rows else empty_state("No mini bids yet", "/client/dashboard", "Back to dashboard")
    body = f"""
    <section class="dashboard-header">
      <div>
        <p class="eyebrow">Client job</p>
        <h1>{escape(job.get('title', 'Job'))}</h1>
        <p>{escape(job.get('category', ''))} in {escape(job.get('area_label', ''))}</p>
      </div>
      <span class="status {escape(job.get('status', ''))}">{escape(job.get('status', ''))}</span>
    </section>
    <section class="dashboard-metrics" aria-label="Mini-bid queue">
      <div class="metric-card"><span>Pending</span><strong>{int(stats.get('pending', 0))}</strong></div>
      <div class="metric-card"><span>Approved</span><strong>{int(stats.get('approved', 0))}</strong></div>
      <div class="metric-card"><span>Total bids</span><strong>{int(stats.get('total', 0))}</strong></div>
    </section>
    <section class="detail-grid">
      <article class="panel">
        <h2>Job details</h2>
        <dl class="job-facts">
          <div><dt>Trade</dt><dd>{escape(job.get('category', ''))}</dd></div>
          <div><dt>Area</dt><dd>{escape(job.get('area_label', ''))}</dd></div>
          <div><dt>Desired</dt><dd>{escape(job.get('desired_date', '') or 'Flexible')}</dd></div>
          <div><dt>Photos</dt><dd>{len(photos)}</dd></div>
        </dl>
        <p class="preline">{escape(job.get('description', ''))}</p>
        <div class="photo-grid">{photo_html}</div>
      </article>
      <aside class="panel">
        <h2>Job controls</h2>
        {status_form}
        <form class="stack-form" data-file-action="/api/media/jobs/{job_id}/upload" data-success-url-template="/client/jobs/{job_id}" enctype="multipart/form-data" aria-describedby="job-photo-upload-status">
          <label>Job photo <input name="photo" type="file" accept="image/png,image/jpeg,image/gif,image/webp" required></label>
          <button class="button secondary full" type="submit">Upload photo</button>
          <p id="job-photo-upload-status" class="help-text" data-form-status aria-live="polite"></p>
        </form>
      </aside>
    </section>
    <section class="panel" id="mini-bids">
      <div class="panel-heading">
        <h2>Mini bids</h2>
        <nav class="filter-links" aria-label="Mini-bid filters">{link_html}</nav>
      </div>
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
