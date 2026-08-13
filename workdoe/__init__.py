from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request as UrlRequest, urlopen

from flask import (
    Flask,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
    jsonify,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent

JOB_CATEGORIES = [
    "Power washing",
    "Window cleaning",
    "Roofing",
    "Painting",
    "Drywall",
    "Flooring",
    "Electrical",
    "Plumbing",
    "HVAC",
    "Landscaping",
    "Tree service",
    "Fencing",
    "Decks and patios",
    "Concrete and masonry",
    "Junk removal",
    "General handyman",
    "Commercial maintenance",
    "Other",
]

DMV_ZIPS = {
    "20001": ("Washington", "DC", 38.9101, -77.0171),
    "20002": ("Washington", "DC", 38.9047, -76.9786),
    "20003": ("Washington", "DC", 38.8876, -76.9901),
    "20007": ("Washington", "DC", 38.9146, -77.0730),
    "20910": ("Silver Spring", "MD", 38.9981, -77.0318),
    "20814": ("Bethesda", "MD", 38.9897, -77.1003),
    "20850": ("Rockville", "MD", 39.0918, -77.1812),
    "20742": ("College Park", "MD", 38.9869, -76.9426),
    "20770": ("Greenbelt", "MD", 39.0046, -76.8755),
    "21401": ("Annapolis", "MD", 38.9784, -76.4922),
    "22201": ("Arlington", "VA", 38.8871, -77.0932),
    "22314": ("Alexandria", "VA", 38.8048, -77.0469),
    "22102": ("McLean", "VA", 38.9339, -77.1773),
    "22030": ("Fairfax", "VA", 38.8462, -77.3064),
    "20190": ("Reston", "VA", 38.9586, -77.3570),
    "20170": ("Herndon", "VA", 38.9695, -77.3861),
}

CITY_COORDS = {
    "washington dc": (38.9072, -77.0369),
    "silver spring md": (38.9907, -77.0261),
    "bethesda md": (38.9847, -77.0947),
    "rockville md": (39.0840, -77.1528),
    "college park md": (38.9897, -76.9378),
    "greenbelt md": (39.0046, -76.8755),
    "annapolis md": (38.9784, -76.4922),
    "arlington va": (38.8797, -77.1068),
    "alexandria va": (38.8048, -77.0469),
    "mclean va": (38.9339, -77.1773),
    "fairfax va": (38.8462, -77.3064),
    "reston va": (38.9586, -77.3570),
    "herndon va": (38.9695, -77.3861),
}

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
DMV_STATES = {"DC", "MD", "VA"}
JOB_TITLE_MAX_LENGTH = 90
JOB_CITY_MAX_LENGTH = 80
JOB_DESCRIPTION_MIN_LENGTH = 20
JOB_DESCRIPTION_MAX_LENGTH = 1200
BID_SCOPE_MIN_LENGTH = 20
BID_SCOPE_MAX_LENGTH = 800
BID_PRICE_MAX_LENGTH = 80
BID_TIMELINE_MAX_LENGTH = 120
BID_EXPERIENCE_MIN_LENGTH = 20
BID_EXPERIENCE_MAX_LENGTH = 800
BID_QUESTIONS_MAX_LENGTH = 500
BID_AVAILABILITY_MAX_LENGTH = 120
MESSAGE_BODY_MAX_LENGTH = 1000
REPORT_REASON_MAX_LENGTH = 500
FILTER_QUERY_MAX_LENGTH = 80
HOME_JOB_LIMIT = 8
ENTRY_JOB_LIMIT = 6
LEAD_BOARD_JOB_LIMIT = 50
DEFAULT_JOB_SORT = "newest"
JOB_SORT_OPTIONS = (
    ("newest", "Newest"),
    ("soonest", "Soonest"),
    ("city", "City"),
)
LEAD_VIEW_OPTIONS = (
    ("all", "All"),
    ("new", "New"),
    ("sent", "Bids sent"),
)
CLIENT_JOB_VIEW_OPTIONS = (
    ("all", "All"),
    ("review", "Needs review"),
    ("open", "Open"),
    ("closed", "Closed"),
)
BID_VIEW_OPTIONS = (
    ("all", "All"),
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
)
PROFILE_BUSINESS_MAX_LENGTH = 120
PROFILE_TRADES_MAX_LENGTH = 240
PROFILE_SERVICE_AREA_MAX_LENGTH = 160
PROFILE_INTRO_MIN_LENGTH = 20
PROFILE_INTRO_MAX_LENGTH = 900
PROFILE_INSURANCE_MAX_LENGTH = 120
PROFILE_LICENSE_MAX_LENGTH = 80
PROFILE_YEARS_MAX = 100
PROFILE_WEBSITE_MAX_LENGTH = 200
PROFILE_PHONE_MAX_LENGTH = 40
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_POSTS = 40
_POST_RATE_LIMITS: dict[tuple[str, str], list[float]] = {}
TURNSTILE_TOKEN_MAX_LENGTH = 2048
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_PROTECTED_ENDPOINTS = {
    "login",
    "start",
    "new_job",
    "request_match",
    "report_content",
}
LOCAL_DEV_SECRET = "workdoe-local-dev-only"
AUTH_PROVIDERS = {"local", "clerk"}
CLERK_LOGIN_MODES = {"same_domain_email_code"}
CLERK_ONBOARDING_TEXT_MAX_LENGTH = 120
WORKDOE_PUBLIC_DOMAIN = "workdoe.com"
CLERK_PROXY_PATH = "/__clerk"
CONTENT_SECURITY_POLICY_DIRECTIVES = [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "style-src-elem 'self'",
    "style-src-attr 'unsafe-inline'",
    "img-src 'self' data: https://*.tile.openstreetmap.org",
    "connect-src 'self'",
    "font-src 'self'",
    "media-src 'self'",
    "worker-src 'none'",
    "manifest-src 'self'",
]
AUTH_FLOW_ENDPOINTS = {
    "login",
    "start",
    "verify_start",
    "forgot_password",
    "reset_password",
    "api_auth_session",
    "api_auth_onboard",
}


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    workdoe_env = os.environ.get("WORKDOE_ENV", "local").strip().lower()
    is_production = workdoe_env == "production"
    app.config.from_mapping(
        WORKDOE_ENV=workdoe_env,
        PRODUCTION=is_production,
        SECRET_KEY=os.environ.get("WORKDOE_SECRET_KEY", LOCAL_DEV_SECRET),
        AUTH_PROVIDER=os.environ.get("WORKDOE_AUTH_PROVIDER", "local").strip().lower(),
        CLERK_PUBLISHABLE_KEY=os.environ.get("CLERK_PUBLISHABLE_KEY", ""),
        CLERK_SECRET_KEY=os.environ.get("CLERK_SECRET_KEY", ""),
        CLERK_WEBHOOK_SECRET=os.environ.get("CLERK_WEBHOOK_SECRET", ""),
        CLERK_JWT_KEY=os.environ.get("CLERK_JWT_KEY", ""),
        CLERK_FRONTEND_API_URL=os.environ.get(
            "CLERK_FRONTEND_API_URL",
            os.environ.get("WORKDOE_CLERK_FRONTEND_API_URL", ""),
        ),
        CLERK_LOGIN_MODE=os.environ.get(
            "WORKDOE_CLERK_LOGIN_MODE",
            "same_domain_email_code",
        ),
        DATABASE=str(Path(app.instance_path) / "workdoe.sqlite3"),
        UPLOAD_ROOT=str(Path(app.instance_path) / "private_uploads"),
        MAX_CONTENT_LENGTH=12 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=is_production
        or os.environ.get("WORKDOE_SECURE_COOKIES", "").lower() in {"1", "true", "yes"},
        SEED_DEMO_DATA=not is_production,
        DISABLE_CSRF=False,
        DISABLE_TURNSTILE=False,
        TURNSTILE_SITE_KEY=os.environ.get("WORKDOE_TURNSTILE_SITE_KEY", ""),
        TURNSTILE_SECRET_KEY=os.environ.get("WORKDOE_TURNSTILE_SECRET_KEY", ""),
        TURNSTILE_VERIFY_URL=os.environ.get("WORKDOE_TURNSTILE_VERIFY_URL", TURNSTILE_VERIFY_URL),
        TURNSTILE_TEST_TOKENS=(),
        SHOW_LOCAL_LOGIN_CODE=not is_production,
    )
    if test_config:
        app.config.update(test_config)
    validate_production_config(app)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_ROOT"]).mkdir(parents=True, exist_ok=True)

    app.teardown_appcontext(close_db)
    app.before_request(load_logged_in_user)
    app.before_request(enforce_post_safety)
    app.after_request(add_security_headers)
    app.jinja_env.globals["csrf_token"] = csrf_token
    app.jinja_env.globals["job_categories"] = JOB_CATEGORIES
    app.jinja_env.globals["job_sort_options"] = JOB_SORT_OPTIONS
    app.jinja_env.globals["report_reason_max"] = REPORT_REASON_MAX_LENGTH
    app.jinja_env.globals["filter_query_max"] = FILTER_QUERY_MAX_LENGTH
    app.jinja_env.globals["home_job_limit"] = HOME_JOB_LIMIT
    app.jinja_env.globals["entry_job_limit"] = ENTRY_JOB_LIMIT
    app.jinja_env.globals["lead_board_job_limit"] = LEAD_BOARD_JOB_LIMIT
    app.jinja_env.globals["map_jobs_api_url"] = map_jobs_api_url
    app.jinja_env.globals["turnstile_enabled"] = turnstile_enabled
    app.jinja_env.globals["turnstile_site_key"] = turnstile_site_key
    app.jinja_env.globals["clerk_entry_enabled"] = clerk_entry_enabled
    app.jinja_env.globals["clerk_publishable_key"] = clerk_publishable_key
    app.jinja_env.globals["clerk_frontend_api_url"] = clerk_frontend_api_url
    app.jinja_env.globals["clerk_proxy_url"] = clerk_proxy_url
    app.jinja_env.filters["money"] = money_filter
    app.jinja_env.filters["date_label"] = date_label_filter
    app.jinja_env.filters["datetime_label"] = datetime_label_filter
    app.jinja_env.filters["photo_count_label"] = photo_count_label
    app.jinja_env.filters["message_count_label"] = message_count_label

    register_routes(app)
    register_error_handlers(app)
    init_db(app)
    return app


def validate_production_config(app: Flask) -> None:
    auth_provider = str(app.config.get("AUTH_PROVIDER", "local")).strip().lower()
    clerk_login_mode = str(
        app.config.get("CLERK_LOGIN_MODE", "same_domain_email_code")
    ).strip().lower()
    app.config["AUTH_PROVIDER"] = auth_provider
    app.config["CLERK_LOGIN_MODE"] = clerk_login_mode
    if auth_provider not in AUTH_PROVIDERS:
        raise RuntimeError(
            "Workdoe configuration is incomplete: WORKDOE_AUTH_PROVIDER must be local or clerk"
        )
    if clerk_login_mode not in CLERK_LOGIN_MODES:
        raise RuntimeError(
            "Workdoe configuration is incomplete: WORKDOE_CLERK_LOGIN_MODE must be same_domain_email_code"
        )
    if not app.config.get("PRODUCTION"):
        return
    missing = []
    if app.config.get("SECRET_KEY") == LOCAL_DEV_SECRET:
        missing.append("WORKDOE_SECRET_KEY")
    if app.config.get("SEED_DEMO_DATA"):
        missing.append("SEED_DEMO_DATA=False")
    if not app.config.get("SESSION_COOKIE_SECURE"):
        missing.append("SESSION_COOKIE_SECURE=True")
    if not app.config.get("TURNSTILE_SITE_KEY"):
        missing.append("WORKDOE_TURNSTILE_SITE_KEY")
    if not app.config.get("TURNSTILE_SECRET_KEY"):
        missing.append("WORKDOE_TURNSTILE_SECRET_KEY")
    if auth_provider == "clerk":
        for env_name, config_name in (
            ("CLERK_PUBLISHABLE_KEY", "CLERK_PUBLISHABLE_KEY"),
            ("CLERK_SECRET_KEY", "CLERK_SECRET_KEY"),
            ("CLERK_WEBHOOK_SECRET", "CLERK_WEBHOOK_SECRET"),
            ("CLERK_JWT_KEY", "CLERK_JWT_KEY"),
        ):
            if not app.config.get(config_name):
                missing.append(env_name)
        if not normalize_clerk_frontend_api_url(app.config.get("CLERK_FRONTEND_API_URL")):
            missing.append("CLERK_FRONTEND_API_URL=https://...")
    if missing:
        raise RuntimeError(
            "Workdoe production configuration is incomplete: " + ", ".join(missing)
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE"])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(error: Exception | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app: Flask) -> None:
    with app.app_context():
        db = get_db()
        schema = (BASE_DIR / "schema.sql").read_text(encoding="utf-8")
        db.executescript(schema)
        ensure_schema_migrations(db)
        seed_reference_data(db)
        if app.config.get("SEED_DEMO_DATA", True):
            seed_demo_data(db)
        db.commit()


def ensure_schema_migrations(db: sqlite3.Connection) -> None:
    user_columns = {row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()}
    if "auth_provider" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN auth_provider TEXT NOT NULL DEFAULT 'local'")
    if "external_subject" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN external_subject TEXT")
    db.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_auth_subject
        ON users(auth_provider, external_subject)
        WHERE external_subject IS NOT NULL
        """
    )

    login_code_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(login_codes)").fetchall()
    }
    if "selected_job_id" not in login_code_columns:
        db.execute("ALTER TABLE login_codes ADD COLUMN selected_job_id INTEGER")
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_login_codes_selected_job ON login_codes(selected_job_id)"
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_events (
            id INTEGER PRIMARY KEY,
            event_type TEXT NOT NULL,
            target_type TEXT NOT NULL DEFAULT '',
            target_id INTEGER,
            payload_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'processed', 'failed')),
            created_at TEXT NOT NULL,
            processed_at TEXT
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_automation_events_type_target
        ON automation_events(event_type, target_type, target_id, created_at)
        """
    )


def seed_reference_data(db: sqlite3.Connection) -> None:
    for category in JOB_CATEGORIES:
        db.execute(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)",
            (category,),
        )


def ensure_user(
    db: sqlite3.Connection,
    email: str,
    password: str,
    role: str,
    display_name: str,
    company_name: str = "",
) -> int:
    row = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row:
        return int(row["id"])
    cur = db.execute(
        """
        INSERT INTO users
            (email, password_hash, role, display_name, company_name, status, email_verified, created_at)
        VALUES (?, ?, ?, ?, ?, 'active', 1, ?)
        """,
        (
            email,
            generate_password_hash(password),
            role,
            display_name,
            company_name,
            now_iso(),
        ),
    )
    user_id = int(cur.lastrowid)
    if role == "client":
        db.execute(
            "INSERT INTO client_profiles (user_id, organization_name, phone) VALUES (?, ?, '')",
            (user_id, company_name or display_name),
        )
    if role == "contractor":
        db.execute(
            """
            INSERT INTO contractor_profiles
                (user_id, business_name, trades, service_area, intro, insurance_status,
                 license_number, years_in_business, website, phone, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                company_name or display_name,
                "Power washing, Window cleaning, General handyman",
                "DC, Maryland, Northern Virginia",
                "Responsive DMV contractor available for residential and commercial work.",
                "Available on request",
                "Local beta profile",
                5,
                "",
                "",
                now_iso(),
            ),
        )
    return user_id


def seed_demo_data(db: sqlite3.Connection) -> None:
    admin_id = ensure_user(
        db,
        "admin@workdoe.local",
        "workdoe-admin",
        "admin",
        "Workdoe Admin",
        "Workdoe",
    )
    client_id = ensure_user(
        db,
        "client@workdoe.local",
        "workdoe-client",
        "client",
        "Avery Homeowner",
        "Capitol Hill Rowhome",
    )
    contractor_id = ensure_user(
        db,
        "contractor@workdoe.local",
        "workdoe-contractor",
        "contractor",
        "Jordan Rivera",
        "Rivera Exterior Care",
    )

    existing_jobs = db.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()["count"]
    if existing_jobs:
        return

    samples = [
        (
            "Power wash townhouse front steps",
            "Power washing",
            "Washington",
            "DC",
            "20003",
            "Need front steps, walkway, and small patio cleaned before a family event.",
            "2026-08-15",
        ),
        (
            "Replace damaged fence panel",
            "Fencing",
            "Silver Spring",
            "MD",
            "20910",
            "One wind-damaged privacy fence panel needs replacement and staining.",
            "2026-08-22",
        ),
        (
            "Office suite touch-up painting",
            "Painting",
            "Arlington",
            "VA",
            "22201",
            "Small office needs evening touch-up painting on three walls.",
            "2026-08-29",
        ),
    ]
    for title, category, city, state, zip_code, description, desired_date in samples:
        lat, lng = approximate_location(city, state, zip_code)
        db.execute(
            """
            INSERT INTO jobs
                (client_id, title, category, city, state, zip_code, description,
                 desired_date, status, approx_lat, approx_lng, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)
            """,
            (
                client_id,
                title,
                category,
                city,
                state,
                zip_code,
                description,
                desired_date,
                lat,
                lng,
                now_iso(),
                now_iso(),
            ),
        )

    db.execute(
        """
        INSERT INTO moderation_actions
            (admin_id, action_type, target_type, target_id, notes, created_at)
        VALUES (?, 'seed', 'workspace', 0, 'Created local demo accounts and DMV sample jobs.', ?)
        """,
        (admin_id, now_iso()),
    )
    db.execute(
        """
        INSERT OR IGNORE INTO reports
            (reporter_id, target_type, target_id, reason, status, created_at, resolved_at)
        VALUES (?, 'job', 1, 'Demo moderation queue item for local QA.', 'open', ?, NULL)
        """,
        (contractor_id, now_iso()),
    )


def no_store_json(payload: dict, status: int = 200):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def workdoe_user_payload(user) -> dict:
    return {
        "id": int(user["id"]),
        "role": user["role"],
        "display_name": user["display_name"],
        "company_name": user["company_name"] or "",
        "status": user["status"],
    }


def sign_in_workdoe_user(user_id: int) -> None:
    session.clear()
    session["user_id"] = int(user_id)
    csrf_token()


def local_clerk_subject_for_email(email: str) -> str:
    return "local-clerk:" + hash_token(email)[:32]


def record_automation_event(
    db: sqlite3.Connection,
    event_type: str,
    *,
    target_type: str = "",
    target_id: int | None = None,
    payload: dict | None = None,
    status: str = "processed",
    created_at: str | None = None,
) -> None:
    event_time = created_at or now_iso()
    db.execute(
        """
        INSERT INTO automation_events
            (event_type, target_type, target_id, payload_json, status, created_at, processed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_type,
            target_type,
            target_id,
            json.dumps(payload or {}, sort_keys=True),
            status,
            event_time,
            event_time,
        ),
    )


def register_routes(app: Flask) -> None:
    @app.route("/")
    def home():
        filters = public_job_filters()
        open_jobs, map_jobs = public_open_jobs(limit=HOME_JOB_LIMIT, filters=filters, target="login")
        return render_template(
            "home.html",
            open_jobs=open_jobs,
            map_jobs=map_jobs,
            filters=filters,
            has_filters=public_filters_active(filters),
        )

    @app.route("/api/jobs/open")
    def api_open_jobs():
        limit = parse_limit(request.args.get("limit"), default=24, maximum=50)
        filters = public_job_filters()
        target = normalize_public_job_target(request.args.get("target"))
        lead_view = normalize_lead_view(request.args.get("view"))
        jobs, map_jobs = public_open_jobs(limit=limit, filters=filters, target=target)
        if lead_view != "all" and g.user and g.user["role"] == "contractor":
            jobs = attach_contractor_request_status(jobs, g.user["id"])
            jobs = filter_jobs_by_lead_view(jobs, lead_view)
            map_jobs = filter_map_jobs_by_jobs(map_jobs, jobs)
        response = jsonify(
            {
                "count": len(map_jobs),
                "jobs": map_jobs,
                "filters": filters,
                "view": lead_view if g.user and g.user["role"] == "contractor" else "all",
                "location_privacy": "Approximate city or ZIP-level pins only.",
            }
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.route("/api/auth/session")
    def api_auth_session():
        if g.user:
            return no_store_json(
                {
                    "authenticated": True,
                    "onboarding_required": False,
                    "workdoe_user": workdoe_user_payload(g.user),
                }
            )
        return no_store_json(
            {
                "authenticated": False,
                "onboarding_required": clerk_entry_enabled(),
                "workdoe_user": None,
            }
        )

    @app.route("/api/auth/onboard", methods=("POST",))
    def api_auth_onboard():
        if not clerk_entry_enabled():
            return no_store_json(
                {
                    "ok": False,
                    "error": "Clerk same-domain sign-in is not configured.",
                },
                status=404,
            )
        if current_app.config.get("PRODUCTION"):
            return no_store_json(
                {
                    "ok": False,
                    "error": "Cloudflare Worker Clerk verification is required before production onboarding.",
                },
                status=501,
            )

        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return no_store_json(
                {"ok": False, "error": "Onboarding body must be a JSON object."},
                status=400,
            )

        email = compact_spaces(body.get("email")).lower()[:254]
        role = compact_spaces(body.get("role")).lower()
        display_name = compact_spaces(body.get("display_name"))[:CLERK_ONBOARDING_TEXT_MAX_LENGTH]
        company_name = compact_spaces(body.get("company_name"))[:CLERK_ONBOARDING_TEXT_MAX_LENGTH]
        if not email or "@" not in email or email.startswith("@") or email.endswith("@"):
            return no_store_json(
                {"ok": False, "error": "A verified Clerk email is required."},
                status=400,
            )
        if role not in {"client", "contractor"}:
            return no_store_json(
                {"ok": False, "error": "Role must be client or contractor."},
                status=400,
            )
        if not display_name:
            display_name = email.split("@", 1)[0][:CLERK_ONBOARDING_TEXT_MAX_LENGTH]
        if not company_name:
            company_name = display_name

        db = get_db()
        external_subject = local_clerk_subject_for_email(email)
        linked_user = db.execute(
            """
            SELECT id, role, display_name, company_name, status
            FROM users
            WHERE auth_provider = 'clerk'
              AND external_subject = ?
            LIMIT 1
            """,
            (external_subject,),
        ).fetchone()
        if linked_user:
            if linked_user["status"] != "active":
                return no_store_json(
                    {"ok": False, "error": "Workdoe account is not active."},
                    status=403,
                )
            sign_in_workdoe_user(linked_user["id"])
            return no_store_json(
                {
                    "ok": True,
                    "created": False,
                    "workdoe_user": workdoe_user_payload(linked_user),
                }
            )

        email_conflict = db.execute(
            "SELECT id FROM users WHERE email = ? LIMIT 1",
            (email,),
        ).fetchone()
        if email_conflict:
            return no_store_json(
                {"ok": False, "error": "A Workdoe account already uses this email."},
                status=409,
            )

        created_at = now_iso()
        try:
            cur = db.execute(
                """
                INSERT INTO users
                    (email, password_hash, role, display_name, company_name,
                     status, email_verified, auth_provider, external_subject, created_at)
                VALUES (?, ?, ?, ?, ?, 'active', 1, 'clerk', ?, ?)
                """,
                (
                    email,
                    generate_password_hash(secrets.token_urlsafe(32)),
                    role,
                    display_name,
                    company_name,
                    external_subject,
                    created_at,
                ),
            )
            user_id = int(cur.lastrowid)
            if role == "client":
                db.execute(
                    """
                    INSERT INTO client_profiles (user_id, organization_name, phone)
                    VALUES (?, ?, '')
                    """,
                    (user_id, company_name),
                )
            else:
                db.execute(
                    """
                    INSERT INTO contractor_profiles
                        (user_id, business_name, trades, service_area, intro,
                         insurance_status, license_number, years_in_business,
                         website, phone, updated_at)
                    VALUES (?, ?, '', 'DMV area', '', '', '', NULL, '', '', ?)
                    """,
                    (user_id, company_name, created_at),
                )
            record_automation_event(
                db,
                "clerk-onboarding-linked",
                target_type="user",
                target_id=user_id,
                payload={
                    "role": role,
                    "email": email,
                    "auth_provider": "clerk",
                    "local_bridge": True,
                },
                status="processed",
                created_at=created_at,
            )
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            return no_store_json(
                {"ok": False, "error": "A Workdoe account already uses this email."},
                status=409,
            )

        user = db.execute(
            "SELECT id, role, display_name, company_name, status FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        sign_in_workdoe_user(user_id)
        return no_store_json(
            {
                "ok": True,
                "created": True,
                "workdoe_user": workdoe_user_payload(user),
            },
            status=201,
        )

    @app.route("/start", methods=("GET", "POST"))
    def start():
        filters = public_job_filters()
        intent = normalize_intent(request.values.get("intent") or "post-job")
        selected_job = selected_start_job(request.values.get("job_id"), intent)
        form_email = compact_spaces(request.values.get("email")).lower()[:254]
        form_display_name = ""
        form_company_name = ""
        if request.method == "POST":
            intent = normalize_intent(request.form.get("intent"))
            selected_job = selected_start_job(request.form.get("job_id"), intent)
            role = "client" if intent == "post-job" else "contractor"
            email = (request.form.get("email") or "").strip().lower()
            display_name = (request.form.get("display_name") or "").strip()
            company_name = (request.form.get("company_name") or "").strip()
            form_email = email
            form_display_name = display_name
            form_company_name = company_name
            existing_user = None
            if email and "@" in email:
                existing_user = get_db().execute(
                    "SELECT * FROM users WHERE email = ?",
                    (email,),
                ).fetchone()
                if existing_user:
                    display_name = display_name or existing_user["display_name"]
                    company_name = company_name or existing_user["company_name"] or ""
                    if existing_user["role"] in {"client", "contractor"}:
                        role = existing_user["role"]

            if not email or "@" not in email:
                flash("Enter a valid email address.", "error")
            elif not existing_user and not display_name:
                flash("Add your name to create a Workdoe workspace.", "error")
            else:
                issue_login_code(
                    email,
                    role,
                    display_name,
                    company_name,
                    intent,
                    selected_job["id"] if selected_job else None,
                )
                return redirect(url_for("verify_start"))
        open_jobs, map_jobs = public_open_jobs(limit=ENTRY_JOB_LIMIT, filters=filters)
        return render_template(
            "start.html",
            intent=intent,
            open_jobs=open_jobs,
            map_jobs=map_jobs,
            selected_job=selected_job,
            filters=filters,
            has_filters=public_filters_active(filters),
            form_email=form_email,
            form_display_name=form_display_name,
            form_company_name=form_company_name,
        )

    @app.route("/start/verify", methods=("GET", "POST"))
    def verify_start():
        code_id = session.get("start_code_id")
        code_error = ""
        if not code_id:
            flash("Start with your email so we can send a one-time code.", "error")
            return redirect(url_for("start"))
        login_code = get_db().execute(
            "SELECT * FROM login_codes WHERE id = ?",
            (code_id,),
        ).fetchone()
        if not login_code or login_code["used_at"] or login_code["expires_at"] < now_iso():
            session.pop("start_code_id", None)
            session.pop("local_login_code", None)
            session.pop("login_next_url", None)
            flash("That one-time code expired. Start again.", "error")
            return redirect(url_for("start"))

        if request.method == "POST":
            submitted = normalize_login_code_submission(request.form.get("code"))
            if not re.fullmatch(r"\d{6}", submitted):
                code_error = "Enter the 6-digit code."
            elif not secrets.compare_digest(hash_token(submitted), login_code["code_hash"]):
                code_error = "That code did not match."
            else:
                user_id = get_or_create_user_from_login_code(login_code)
                user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                if user["status"] != "active":
                    flash("This account is not active. Contact the Workdoe admin.", "error")
                    return redirect(url_for("login"))
                get_db().execute(
                    "UPDATE login_codes SET used_at = ? WHERE id = ?",
                    (now_iso(), code_id),
                )
                get_db().commit()
                login_next_url = safe_next_url(session.get("login_next_url"))
                session.clear()
                session["user_id"] = user_id
                csrf_token()
                flash("You are in. Workdoe skipped the username and provider maze.", "success")
                if login_next_url:
                    role_target = next_url_for_role(login_next_url, user["role"])
                    if role_target:
                        return redirect(role_target)
                return redirect(
                    after_start_url(
                        user["role"],
                        login_code["intent"],
                        login_code["selected_job_id"],
                    )
                )
        selected_job = selected_start_job(login_code["selected_job_id"], login_code["intent"])
        return render_template(
            "verify_start.html",
            login_code=login_code,
            local_code=(
                session.get("local_login_code")
                if current_app.config.get("SHOW_LOCAL_LOGIN_CODE")
                else None
            ),
            selected_job=selected_job,
            login_next_url=safe_next_url(session.get("login_next_url")),
            code_error=code_error,
        )

    @app.route("/safety")
    def safety():
        return render_template("safety.html")

    @app.route("/signup", methods=("GET", "POST"))
    def signup():
        if request.method == "GET":
            return redirect(url_for("start"))
        if request.method == "POST":
            role = request.form.get("role", "")
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""
            display_name = (request.form.get("display_name") or "").strip()
            company_name = (request.form.get("company_name") or "").strip()

            if role not in {"client", "contractor"}:
                flash("Choose whether this account is for a client or contractor.", "error")
            elif not email or "@" not in email:
                flash("Enter a valid email address.", "error")
            elif len(password) < 8:
                flash("Use at least 8 characters for the local prototype password.", "error")
            elif not display_name:
                flash("Add your name so the dashboard feels personal.", "error")
            else:
                db = get_db()
                try:
                    cur = db.execute(
                        """
                        INSERT INTO users
                            (email, password_hash, role, display_name, company_name,
                             status, email_verified, created_at)
                        VALUES (?, ?, ?, ?, ?, 'active', 1, ?)
                        """,
                        (
                            email,
                            generate_password_hash(password),
                            role,
                            display_name,
                            company_name,
                            now_iso(),
                        ),
                    )
                    user_id = int(cur.lastrowid)
                    if role == "client":
                        db.execute(
                            """
                            INSERT INTO client_profiles (user_id, organization_name, phone)
                            VALUES (?, ?, '')
                            """,
                            (user_id, company_name or display_name),
                        )
                    else:
                        db.execute(
                            """
                            INSERT INTO contractor_profiles
                                (user_id, business_name, trades, service_area, intro,
                                 insurance_status, license_number, years_in_business,
                                 website, phone, updated_at)
                            VALUES (?, ?, '', 'DMV area', '', '', '', NULL, '', '', ?)
                            """,
                            (user_id, company_name or display_name, now_iso()),
                        )
                    db.commit()
                except sqlite3.IntegrityError:
                    flash("That email already has a Workdoe account.", "error")
                else:
                    session.clear()
                    session["user_id"] = user_id
                    csrf_token()
                    flash("Welcome to Workdoe. Your local account is ready.", "success")
                    return redirect(url_for("dashboard"))
        return render_template("signup.html")

    @app.route("/login", methods=("GET", "POST"))
    def login():
        filters = public_job_filters()
        next_url = safe_next_url(request.values.get("next"))
        selected_job = selected_next_job(next_url)
        if request.method == "POST":
            auth_action = request.form.get("auth_action") or (
                "password" if request.form.get("password") else "code"
            )
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""
            user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if auth_action == "code":
                if not email or "@" not in email:
                    flash("Enter a valid email address.", "error")
                elif user is None:
                    flash("New here? Start with email and keep this lead selected.", "success")
                    return redirect(start_url_for_email(email, selected_job))
                elif user["status"] != "active":
                    flash("This account is not active. Contact the Workdoe admin.", "error")
                elif user["role"] == "admin":
                    flash("Admin accounts use password sign-in for now.", "error")
                else:
                    selected_job_id = selected_job["id"] if selected_job and user["role"] == "contractor" else None
                    intent = "find-work" if user["role"] == "contractor" else "post-job"
                    if next_url == url_for("new_job") and user["role"] == "client":
                        intent = "post-job"
                    issue_login_code(
                        user["email"],
                        user["role"],
                        user["display_name"],
                        user["company_name"] or "",
                        intent,
                        selected_job_id,
                    )
                    if next_url:
                        session["login_next_url"] = next_url
                    else:
                        session.pop("login_next_url", None)
                    return redirect(url_for("verify_start"))
            elif user is None or not check_password_hash(user["password_hash"], password):
                flash("Email or password did not match.", "error")
            elif user["status"] != "active":
                flash("This account is not active. Contact the Workdoe admin.", "error")
            else:
                session.clear()
                session["user_id"] = int(user["id"])
                csrf_token()
                flash("Signed in.", "success")
                return redirect(next_url_for_role(next_url, user["role"]) or url_for("dashboard"))
        open_jobs, map_jobs = public_open_jobs(
            limit=ENTRY_JOB_LIMIT,
            filters=filters,
            target="login",
        )
        return render_template(
            "login.html",
            open_jobs=open_jobs,
            map_jobs=map_jobs,
            next_url=next_url,
            selected_job=selected_job,
            filters=filters,
            has_filters=public_filters_active(filters),
        )

    @app.route("/forgot-password", methods=("GET", "POST"))
    def forgot_password():
        reset_link = None
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if user:
                raw_token = secrets.token_urlsafe(32)
                expires_at = (
                    datetime.now(timezone.utc) + timedelta(minutes=30)
                ).isoformat(timespec="seconds")
                get_db().execute(
                    """
                    INSERT INTO password_reset_tokens
                        (user_id, token_hash, expires_at, used_at, created_at)
                    VALUES (?, ?, ?, NULL, ?)
                    """,
                    (user["id"], hash_token(raw_token), expires_at, now_iso()),
                )
                get_db().commit()
                reset_link = url_for("reset_password", token=raw_token)
            flash(
                "If that email exists locally, a reset link has been generated below for the prototype.",
                "success",
            )
        return render_template("forgot_password.html", reset_link=reset_link)

    @app.route("/reset-password/<token>", methods=("GET", "POST"))
    def reset_password(token: str):
        token_hash = hash_token(token)
        reset = get_db().execute(
            """
            SELECT password_reset_tokens.*, users.email
            FROM password_reset_tokens
            JOIN users ON users.id = password_reset_tokens.user_id
            WHERE password_reset_tokens.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
        if not reset or reset["used_at"] or reset["expires_at"] < now_iso():
            flash("That reset link is expired or already used.", "error")
            return redirect(url_for("forgot_password"))
        if request.method == "POST":
            password = request.form.get("password") or ""
            if len(password) < 8:
                flash("Use at least 8 characters.", "error")
            else:
                get_db().execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (generate_password_hash(password), reset["user_id"]),
                )
                get_db().execute(
                    "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?",
                    (now_iso(), reset["id"]),
                )
                get_db().commit()
                flash("Password updated. Sign in with the new password.", "success")
                return redirect(url_for("login"))
        return render_template("reset_password.html", reset=reset)

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Signed out.", "success")
        return redirect(url_for("home"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        if g.user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        if g.user["role"] == "client":
            return redirect(url_for("client_dashboard"))
        return redirect(url_for("contractor_dashboard"))

    @app.route("/client/dashboard")
    @role_required("client")
    def client_dashboard():
        db = get_db()
        job_view = normalize_client_job_view(request.args.get("view"))
        jobs = db.execute(
            """
            SELECT jobs.*,
                   COUNT(match_requests.id) AS request_count,
                   SUM(CASE WHEN match_requests.status = 'pending' THEN 1 ELSE 0 END) AS pending_count
            FROM jobs
            LEFT JOIN match_requests ON match_requests.job_id = jobs.id
            WHERE jobs.client_id = ?
            GROUP BY jobs.id
            ORDER BY jobs.created_at DESC
            """,
            (g.user["id"],),
        ).fetchall()
        all_jobs = [{key: row[key] for key in row.keys()} for row in jobs]
        jobs = filter_client_jobs_by_view(all_jobs, job_view)
        stats = {
            "visible_jobs": len(jobs),
            "total_jobs": len(all_jobs),
            "open_jobs": sum(1 for job in all_jobs if job["status"] == "open"),
            "closed_jobs": sum(1 for job in all_jobs if job["status"] == "closed"),
            "review_jobs": sum(1 for job in all_jobs if (job["pending_count"] or 0) > 0),
            "pending_requests": sum(job["pending_count"] or 0 for job in all_jobs),
        }
        return render_template(
            "client_dashboard.html",
            jobs=jobs,
            stats=stats,
            job_view=job_view,
            job_view_links=client_job_view_links(),
        )

    @app.route("/jobs/new", methods=("GET", "POST"))
    @role_required("client")
    def new_job():
        form = blank_job_form()
        if request.method == "POST":
            form = cleaned_job_form(request.form)
            errors = validate_job_form(form)
            if errors:
                return render_job_form(form, mode="new", errors=errors)
            else:
                lat, lng = approximate_location(form["city"], form["state"], form["zip_code"])
                db = get_db()
                cur = db.execute(
                    """
                    INSERT INTO jobs
                        (client_id, title, category, city, state, zip_code, description,
                         desired_date, status, approx_lat, approx_lng, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)
                    """,
                    (
                        g.user["id"],
                        form["title"],
                        form["category"],
                        form["city"],
                        form["state"],
                        form["zip_code"],
                        form["description"],
                        form["desired_date"],
                        lat,
                        lng,
                        now_iso(),
                        now_iso(),
                    ),
                )
                job_id = int(cur.lastrowid)
                save_job_photos(job_id, g.user["id"], request.files.getlist("photos"))
                db.commit()
                flash("Job posted. Contractors can now request a match.", "success")
                return redirect(url_for("client_job_detail", job_id=job_id))
        return render_job_form(form, mode="new")

    @app.route("/client/jobs/<int:job_id>/edit", methods=("GET", "POST"))
    @role_required("client", "admin")
    def edit_job(job_id: int):
        job = fetch_job(job_id)
        if not job:
            abort(404)
        if g.user["role"] != "admin" and job["client_id"] != g.user["id"]:
            abort(403)
        form = job_to_form(job)
        if request.method == "POST":
            form = cleaned_job_form(request.form)
            errors = validate_job_form(form)
            if errors:
                return render_job_form(form, mode="edit", job=job, errors=errors)
            else:
                lat, lng = approximate_location(form["city"], form["state"], form["zip_code"])
                db = get_db()
                db.execute(
                    """
                    UPDATE jobs
                    SET title = ?,
                        category = ?,
                        city = ?,
                        state = ?,
                        zip_code = ?,
                        description = ?,
                        desired_date = ?,
                        approx_lat = ?,
                        approx_lng = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        form["title"],
                        form["category"],
                        form["city"],
                        form["state"],
                        form["zip_code"],
                        form["description"],
                        form["desired_date"],
                        lat,
                        lng,
                        now_iso(),
                        job_id,
                    ),
                )
                save_job_photos(job_id, g.user["id"], request.files.getlist("photos"))
                db.commit()
                flash("Job updated.", "success")
                return redirect(url_for("client_job_detail", job_id=job_id))
        return render_job_form(form, mode="edit", job=job)

    @app.route("/client/jobs/<int:job_id>")
    @role_required("client", "admin")
    def client_job_detail(job_id: int):
        job = fetch_job(job_id)
        if not job:
            abort(404)
        if g.user["role"] != "admin" and job["client_id"] != g.user["id"]:
            abort(403)
        bid_view = normalize_bid_view(request.args.get("bids"))
        db = get_db()
        photos = db.execute(
            "SELECT * FROM job_photos WHERE job_id = ? ORDER BY created_at",
            (job_id,),
        ).fetchall()
        requests = db.execute(
            """
            SELECT match_requests.*, users.display_name, users.company_name,
                   contractor_profiles.business_name, contractor_profiles.trades,
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
                match_requests.created_at DESC
            """,
            (job_id,),
        ).fetchall()
        all_requests = requests
        requests = filter_bids_by_view(all_requests, bid_view)
        request_stats = {
            "visible": len(requests),
            "total": len(all_requests),
            "pending": sum(1 for item in all_requests if item["status"] == "pending"),
            "approved": sum(1 for item in all_requests if item["status"] == "approved"),
            "rejected": sum(1 for item in all_requests if item["status"] == "rejected"),
        }
        return render_template(
            "client_job_detail.html",
            job=job,
            photos=photos,
            requests=requests,
            request_stats=request_stats,
            bid_view=bid_view,
            bid_view_links=bid_view_links(job_id),
        )

    @app.route("/client/jobs/<int:job_id>/<action>", methods=("POST",))
    @role_required("client")
    def client_job_status(job_id: int, action: str):
        if action not in {"close", "reopen"}:
            abort(404)
        job = fetch_job(job_id)
        if not job:
            abort(404)
        if job["client_id"] != g.user["id"]:
            abort(403)
        if job["status"] == "hidden":
            abort(403)
        status = "closed" if action == "close" else "open"
        get_db().execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), job_id),
        )
        get_db().commit()
        flash(f"Job {status}.", "success")
        return redirect(url_for("client_job_detail", job_id=job_id))

    @app.route("/client/requests/<int:request_id>/<action>", methods=("POST",))
    @role_required("client")
    def decide_request(request_id: int, action: str):
        if action not in {"approve", "reject"}:
            abort(404)
        db = get_db()
        match = db.execute(
            """
            SELECT match_requests.*, jobs.client_id
            FROM match_requests
            JOIN jobs ON jobs.id = match_requests.job_id
            WHERE match_requests.id = ?
            """,
            (request_id,),
        ).fetchone()
        if not match:
            abort(404)
        if match["client_id"] != g.user["id"]:
            abort(403)
        status = "approved" if action == "approve" else "rejected"
        db.execute(
            "UPDATE match_requests SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), request_id),
        )
        if status == "approved":
            thread_id = ensure_thread_for_match(match)
            flash("Match approved. A private message thread is open.", "success")
            db.commit()
            return redirect(url_for("thread_detail", thread_id=thread_id))
        db.commit()
        flash("Request rejected.", "success")
        return redirect(url_for("client_job_detail", job_id=match["job_id"]))

    @app.route("/contractor/dashboard")
    @role_required("contractor")
    def contractor_dashboard():
        db = get_db()
        bid_view = normalize_bid_view(request.args.get("bids"))
        profile = db.execute(
            "SELECT * FROM contractor_profiles WHERE user_id = ?",
            (g.user["id"],),
        ).fetchone()
        requests = db.execute(
            """
            SELECT match_requests.*, jobs.title, jobs.category, jobs.city, jobs.state,
                   threads.id AS thread_id
            FROM match_requests
            JOIN jobs ON jobs.id = match_requests.job_id
            LEFT JOIN threads ON threads.match_request_id = match_requests.id
            WHERE match_requests.contractor_id = ?
            ORDER BY match_requests.created_at DESC
            """,
            (g.user["id"],),
        ).fetchall()
        all_requests = requests
        requests = filter_bids_by_view(all_requests, bid_view)
        open_jobs = db.execute(
            "SELECT COUNT(*) AS count FROM jobs WHERE status = 'open'"
        ).fetchone()["count"]
        stats = {
            "open_jobs": open_jobs,
            "visible_requests": len(requests),
            "total_requests": len(all_requests),
            "pending_requests": sum(1 for item in all_requests if item["status"] == "pending"),
            "approved_requests": sum(1 for item in all_requests if item["status"] == "approved"),
            "rejected_requests": sum(1 for item in all_requests if item["status"] == "rejected"),
        }
        return render_template(
            "contractor_dashboard.html",
            profile=profile,
            requests=requests,
            open_jobs=open_jobs,
            stats=stats,
            bid_view=bid_view,
            bid_view_links=contractor_bid_view_links(),
        )

    @app.route("/contractor/profile", methods=("GET", "POST"))
    @role_required("contractor")
    def contractor_profile():
        db = get_db()
        profile = db.execute(
            "SELECT * FROM contractor_profiles WHERE user_id = ?",
            (g.user["id"],),
        ).fetchone()
        photos = db.execute(
            "SELECT * FROM contractor_photos WHERE contractor_id = ? ORDER BY created_at DESC",
            (g.user["id"],),
        ).fetchall()
        if request.method == "POST":
            form = cleaned_contractor_profile_form(request.form)
            errors = validate_contractor_profile_form(form)
            if errors:
                for error in errors:
                    flash(error, "error")
                return render_contractor_profile_form(form, photos)

            db.execute(
                """
                UPDATE contractor_profiles
                SET business_name = ?, trades = ?, service_area = ?, intro = ?,
                    insurance_status = ?, license_number = ?, years_in_business = ?,
                    website = ?, phone = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (
                    form["business_name"],
                    form["trades"],
                    form["service_area"],
                    form["intro"],
                    form["insurance_status"],
                    form["license_number"],
                    profile_years_value(form["years_in_business"]),
                    form["website"],
                    form["phone"],
                    now_iso(),
                    g.user["id"],
                ),
            )
            save_contractor_photos(g.user["id"], request.files.getlist("portfolio_photos"))
            db.commit()
            flash("Contractor profile updated.", "success")
            return redirect(url_for("contractor_profile"))

        return render_contractor_profile_form(contractor_profile_to_form(profile), photos)

    @app.route("/contractors/<int:contractor_id>")
    def contractor_public_profile(contractor_id: int):
        db = get_db()
        contractor = db.execute(
            """
            SELECT users.id, users.display_name, users.company_name, users.status,
                   contractor_profiles.*
            FROM users
            JOIN contractor_profiles ON contractor_profiles.user_id = users.id
            WHERE users.id = ? AND users.role = 'contractor'
            """,
            (contractor_id,),
        ).fetchone()
        is_admin = g.user and g.user["role"] == "admin"
        if not contractor or (contractor["status"] != "active" and not is_admin):
            abort(404)
        photos = db.execute(
            """
            SELECT * FROM contractor_photos
            WHERE contractor_id = ? AND is_hidden = 0
            ORDER BY created_at DESC
            """,
            (contractor_id,),
        ).fetchall()
        return render_template("contractor_public.html", contractor=contractor, photos=photos)

    @app.route("/leads")
    @role_required("contractor")
    def leads():
        filters = public_job_filters()
        lead_view = normalize_lead_view(request.args.get("view"))
        jobs, map_jobs = public_open_jobs(limit=LEAD_BOARD_JOB_LIMIT, filters=filters)
        jobs = attach_contractor_request_status(jobs, g.user["id"])
        all_jobs = jobs
        jobs = filter_jobs_by_lead_view(all_jobs, lead_view)
        map_jobs = filter_map_jobs_by_jobs(map_jobs, jobs)
        stats = {
            "visible_jobs": len(jobs),
            "all_jobs": len(all_jobs),
            "new_jobs": sum(1 for job in all_jobs if not job["request_status"]),
            "sent_bids": sum(1 for job in all_jobs if job["request_status"]),
        }
        return render_template(
            "leads.html",
            jobs=jobs,
            filters=filters,
            map_jobs=map_jobs,
            map_jobs_api_url=map_jobs_api_url(
                filters,
                limit=LEAD_BOARD_JOB_LIMIT,
                view=lead_view,
            ),
            has_filters=public_filters_active(filters) or lead_view != "all",
            lead_view=lead_view,
            lead_view_links=lead_view_links(filters),
            stats=stats,
        )

    @app.route("/jobs/<int:job_id>")
    @role_required("contractor", "admin")
    def contractor_job_detail(job_id: int):
        job = fetch_job(job_id)
        if not job:
            abort(404)
        if job["status"] == "hidden" and g.user["role"] != "admin":
            abort(404)
        db = get_db()
        photos = db.execute(
            """
            SELECT * FROM job_photos
            WHERE job_id = ? AND is_hidden = 0
            ORDER BY created_at
            """,
            (job_id,),
        ).fetchall()
        existing_request = None
        if g.user["role"] == "contractor":
            existing_request = db.execute(
                """
                SELECT * FROM match_requests
                WHERE job_id = ? AND contractor_id = ?
                """,
                (job_id, g.user["id"]),
            ).fetchone()
        return render_template(
            "contractor_job_detail.html",
            job=job,
            photos=photos,
            existing_request=existing_request,
            bid_form=blank_bid_form(),
            bid_limits=bid_limits(),
            bid_error_feedback=bid_error_feedback([]),
        )

    @app.route("/jobs/<int:job_id>/request", methods=("POST",))
    @role_required("contractor")
    def request_match(job_id: int):
        job = fetch_job(job_id)
        if not job or job["status"] != "open":
            abort(404)
        db = get_db()
        existing = db.execute(
            "SELECT id FROM match_requests WHERE job_id = ? AND contractor_id = ?",
            (job_id, g.user["id"]),
        ).fetchone()
        if existing:
            flash("You already requested a match for this job.", "error")
            return redirect(url_for("contractor_job_detail", job_id=job_id))

        bid_form = cleaned_bid_form(request.form)
        errors = validate_bid_form(bid_form)
        if errors:
            photos = db.execute(
                """
                SELECT * FROM job_photos
                WHERE job_id = ? AND is_hidden = 0
                ORDER BY created_at
                """,
                (job_id,),
            ).fetchall()
            return render_template(
                "contractor_job_detail.html",
                job=job,
                photos=photos,
                existing_request=None,
                bid_form=bid_form,
                bid_limits=bid_limits(),
                bid_error_feedback=bid_error_feedback(errors),
            )

        db.execute(
            """
            INSERT INTO match_requests
                (job_id, contractor_id, scope_note, price_range, timeline,
                 experience, questions, availability, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                job_id,
                g.user["id"],
                bid_form["scope_note"],
                bid_form["price_range"],
                bid_form["timeline"],
                bid_form["experience"],
                bid_form["questions"],
                bid_form["availability"],
                now_iso(),
                now_iso(),
            ),
        )
        db.commit()
        flash("Mini bid sent. The client can approve it to open messaging.", "success")
        return redirect(url_for("contractor_job_detail", job_id=job_id))

    @app.route("/messages")
    @role_required("client", "contractor")
    def message_threads():
        threads = get_db().execute(
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
            """,
            (g.user["id"], g.user["id"]),
        ).fetchall()
        stats = {
            "threads": len(threads),
            "messages": sum(thread["message_count"] or 0 for thread in threads),
        }
        return render_template("messages.html", threads=threads, stats=stats)

    @app.route("/messages/<int:thread_id>", methods=("GET", "POST"))
    @role_required("client", "contractor", "admin")
    def thread_detail(thread_id: int):
        thread = fetch_thread(thread_id)
        if not thread:
            abort(404)
        is_admin = g.user["role"] == "admin"
        if not is_admin and g.user["id"] not in {thread["client_id"], thread["contractor_id"]}:
            abort(403)
        db = get_db()
        draft_body = ""
        if request.method == "POST":
            if is_admin:
                abort(403)
            draft_body = (request.form.get("body") or "").strip()
            if not draft_body:
                flash("Write a message before sending.", "error")
            elif len(draft_body) > MESSAGE_BODY_MAX_LENGTH:
                flash(f"Keep messages under {MESSAGE_BODY_MAX_LENGTH} characters.", "error")
            else:
                db.execute(
                    """
                    INSERT INTO messages (thread_id, sender_id, body, is_hidden, created_at)
                    VALUES (?, ?, ?, 0, ?)
                    """,
                    (thread_id, g.user["id"], draft_body, now_iso()),
                )
                db.commit()
                flash("Message sent.", "success")
                return redirect(url_for("thread_detail", thread_id=thread_id))
        message_visibility = "" if is_admin else "AND messages.is_hidden = 0"
        messages = db.execute(
            f"""
            SELECT messages.*, users.display_name
            FROM messages
            JOIN users ON users.id = messages.sender_id
            WHERE messages.thread_id = ? {message_visibility}
            ORDER BY messages.created_at
            """,
            (thread_id,),
        ).fetchall()
        return render_template(
            "thread_detail.html",
            thread=thread,
            messages=messages,
            draft_body=draft_body,
            message_max=MESSAGE_BODY_MAX_LENGTH,
            can_reply=not is_admin,
        )

    @app.route("/report", methods=("POST",))
    @login_required
    def report_content():
        target_type = request.form.get("target_type")
        target_id = parse_positive_int(request.form.get("target_id"))
        reason = (request.form.get("reason") or "").strip()
        return_url = safe_return_url(request.referrer) or url_for("dashboard")
        if target_type not in {"job", "message", "profile"} or not target_id or not reason:
            flash("Choose what to report and include a reason.", "error")
            return redirect(return_url)
        if len(reason) > REPORT_REASON_MAX_LENGTH:
            flash(f"Keep report notes under {REPORT_REASON_MAX_LENGTH} characters.", "error")
            return redirect(return_url)
        if not report_target_exists(target_type, target_id):
            flash("That item is no longer available to report.", "error")
            return redirect(return_url)
        get_db().execute(
            """
            INSERT INTO reports (reporter_id, target_type, target_id, reason, status, created_at, resolved_at)
            VALUES (?, ?, ?, ?, 'open', ?, NULL)
            """,
            (g.user["id"], target_type, target_id, reason, now_iso()),
        )
        get_db().commit()
        flash("Report sent to moderation.", "success")
        return redirect(return_url)

    @app.route("/admin")
    @role_required("admin")
    def admin_dashboard():
        db = get_db()
        users = db.execute(
            "SELECT id, email, role, display_name, company_name, status, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
        jobs = db.execute(
            """
            SELECT jobs.*, users.display_name AS client_name
            FROM jobs
            JOIN users ON users.id = jobs.client_id
            ORDER BY jobs.created_at DESC
            LIMIT 20
            """
        ).fetchall()
        reports = db.execute(
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
            """
        ).fetchall()
        messages = db.execute(
            """
            SELECT messages.*, users.email AS sender_email, jobs.title AS job_title
            FROM messages
            JOIN users ON users.id = messages.sender_id
            JOIN threads ON threads.id = messages.thread_id
            JOIN jobs ON jobs.id = threads.job_id
            ORDER BY messages.created_at DESC
            LIMIT 20
            """
        ).fetchall()
        actions = db.execute(
            """
            SELECT moderation_actions.*, users.email AS admin_email
            FROM moderation_actions
            LEFT JOIN users ON users.id = moderation_actions.admin_id
            ORDER BY moderation_actions.created_at DESC
            LIMIT 20
            """
        ).fetchall()
        automation_events = db.execute(
            """
            SELECT id, event_type, target_type, target_id, status, created_at
            FROM automation_events
            ORDER BY created_at DESC
            LIMIT 20
            """
        ).fetchall()
        photos = db.execute(
            """
            SELECT job_photos.*, jobs.title
            FROM job_photos
            JOIN jobs ON jobs.id = job_photos.job_id
            ORDER BY job_photos.created_at DESC
            LIMIT 20
            """
        ).fetchall()
        contractor_photos = db.execute(
            """
            SELECT contractor_photos.*, contractor_profiles.business_name
            FROM contractor_photos
            JOIN contractor_profiles ON contractor_profiles.user_id = contractor_photos.contractor_id
            ORDER BY contractor_photos.created_at DESC
            LIMIT 20
            """
        ).fetchall()
        hidden_content_count = db.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM jobs WHERE status = 'hidden') +
                (SELECT COUNT(*) FROM job_photos WHERE is_hidden = 1) +
                (SELECT COUNT(*) FROM contractor_photos WHERE is_hidden = 1) +
                (SELECT COUNT(*) FROM messages WHERE is_hidden = 1) AS total
            """
        ).fetchone()["total"]
        audit_action_count = db.execute(
            "SELECT COUNT(*) AS total FROM moderation_actions"
        ).fetchone()["total"]
        automation_event_count = db.execute(
            "SELECT COUNT(*) AS total FROM automation_events"
        ).fetchone()["total"]
        stats = {
            "open_reports": len(reports),
            "suspended_users": sum(1 for user in users if user["status"] == "suspended"),
            "hidden_content": hidden_content_count,
            "audit_actions": audit_action_count,
            "automation_events": automation_event_count,
        }
        return render_template(
            "admin_dashboard.html",
            users=users,
            jobs=jobs,
            reports=reports,
            messages=messages,
            actions=actions,
            automation_events=automation_events,
            photos=photos,
            contractor_photos=contractor_photos,
            stats=stats,
        )

    @app.route("/admin/users/<int:user_id>/<action>", methods=("POST",))
    @role_required("admin")
    def admin_user_action(user_id: int, action: str):
        if action not in {"suspend", "activate"}:
            abort(404)
        status = "suspended" if action == "suspend" else "active"
        get_db().execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))
        log_action(action, "user", user_id, f"Set user status to {status}.")
        get_db().commit()
        flash(f"User {status}.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/jobs/<int:job_id>/<action>", methods=("POST",))
    @role_required("admin")
    def admin_job_action(job_id: int, action: str):
        if action not in {"hide", "restore"}:
            abort(404)
        status = "hidden" if action == "hide" else "open"
        get_db().execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), job_id),
        )
        log_action(action, "job", job_id, f"Set job status to {status}.")
        get_db().commit()
        flash(f"Job {status}.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/photos/job/<int:photo_id>/<action>", methods=("POST",))
    @role_required("admin")
    def admin_job_photo_action(photo_id: int, action: str):
        if action not in {"hide", "restore"}:
            abort(404)
        hidden = 1 if action == "hide" else 0
        get_db().execute("UPDATE job_photos SET is_hidden = ? WHERE id = ?", (hidden, photo_id))
        log_action(action, "job_photo", photo_id, f"Set job photo hidden={hidden}.")
        get_db().commit()
        flash("Photo moderation updated.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/photos/contractor/<int:photo_id>/<action>", methods=("POST",))
    @role_required("admin")
    def admin_contractor_photo_action(photo_id: int, action: str):
        if action not in {"hide", "restore"}:
            abort(404)
        hidden = 1 if action == "hide" else 0
        get_db().execute(
            "UPDATE contractor_photos SET is_hidden = ? WHERE id = ?",
            (hidden, photo_id),
        )
        log_action(action, "contractor_photo", photo_id, f"Set contractor photo hidden={hidden}.")
        get_db().commit()
        flash("Portfolio photo moderation updated.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/messages/<int:message_id>/hide", methods=("POST",))
    @role_required("admin")
    def admin_hide_message(message_id: int):
        get_db().execute("UPDATE messages SET is_hidden = 1 WHERE id = ?", (message_id,))
        log_action("hide", "message", message_id, "Hidden by admin.")
        get_db().commit()
        flash("Message hidden.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/reports/<int:report_id>/resolve", methods=("POST",))
    @role_required("admin")
    def admin_resolve_report(report_id: int):
        get_db().execute(
            "UPDATE reports SET status = 'resolved', resolved_at = ? WHERE id = ?",
            (now_iso(), report_id),
        )
        log_action("resolve", "report", report_id, "Marked report resolved.")
        get_db().commit()
        flash("Report resolved.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/media/jobs/<int:photo_id>")
    @login_required
    def job_photo(photo_id: int):
        db = get_db()
        photo = db.execute(
            """
            SELECT job_photos.*, jobs.client_id, jobs.status
            FROM job_photos
            JOIN jobs ON jobs.id = job_photos.job_id
            WHERE job_photos.id = ?
            """,
            (photo_id,),
        ).fetchone()
        if not photo:
            abort(404)
        if photo["is_hidden"] and g.user["role"] != "admin":
            abort(404)
        allowed = (
            g.user["role"] == "admin"
            or photo["client_id"] == g.user["id"]
            or (g.user["role"] == "contractor" and photo["status"] == "open")
        )
        if not allowed:
            abort(403)
        return send_private_file(photo["stored_path"], photo["content_type"], photo["original_filename"])

    @app.route("/media/contractors/<int:photo_id>")
    def contractor_photo(photo_id: int):
        photo = get_db().execute(
            """
            SELECT contractor_photos.*, users.status
            FROM contractor_photos
            JOIN users ON users.id = contractor_photos.contractor_id
            WHERE contractor_photos.id = ?
            """,
            (photo_id,),
        ).fetchone()
        if not photo:
            abort(404)
        owner_or_admin = g.user and (
            g.user["role"] == "admin" or photo["contractor_id"] == g.user["id"]
        )
        if (photo["is_hidden"] or photo["status"] != "active") and not owner_or_admin:
            abort(404)
        return send_private_file(photo["stored_path"], photo["content_type"], photo["original_filename"])


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(400)
    def bad_request(error):
        return render_error_page(
            400,
            "Request stopped",
            "Try again from the form so Workdoe can verify the request.",
            "Back home",
        )

    @app.errorhandler(403)
    def forbidden(error):
        return render_error_page(
            403,
            "Access limited",
            "This workspace cannot open that page.",
            "Dashboard",
            primary_url=url_for("dashboard") if g.user else url_for("login"),
            secondary_label="Back home",
            secondary_url=url_for("home"),
        )

    @app.errorhandler(404)
    def not_found(error):
        return render_error_page(
            404,
            "Not found",
            "That page is not available or has been removed.",
            "Back home",
        )

    @app.errorhandler(429)
    def too_many_requests(error):
        return render_error_page(
            429,
            "Slow down",
            "Too many requests arrived at once. Wait a moment and try again.",
            "Back home",
        )

    @app.errorhandler(500)
    def server_error(error):
        return render_error_page(
            500,
            "Something broke",
            "Workdoe hit a server issue. No job details are shown here.",
            "Back home",
        )


def render_error_page(
    status_code: int,
    title: str,
    message: str,
    primary_label: str,
    primary_url: str | None = None,
    secondary_label: str = "Start",
    secondary_url: str | None = None,
):
    return (
        render_template(
            "error.html",
            status_code=status_code,
            title=title,
            message=message,
            primary_label=primary_label,
            primary_url=primary_url or url_for("home"),
            secondary_label=secondary_label,
            secondary_url=secondary_url or url_for("start"),
        ),
        status_code,
    )


def load_logged_in_user() -> None:
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if g.user and g.user["status"] != "active" and request.endpoint != "logout":
            session.clear()
            flash("Your account is not active.", "error")
            g.user = None


def enforce_post_safety() -> None:
    if request.method != "POST":
        return
    clerk_api_post = request.endpoint == "api_auth_onboard" and clerk_entry_enabled()
    if not current_app.config.get("DISABLE_CSRF", False) and not clerk_api_post:
        form_token = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token")
        session_token = session.get("_csrf_token")
        if not session_token or not form_token or not secrets.compare_digest(session_token, form_token):
            abort(400)
    if request.endpoint in TURNSTILE_PROTECTED_ENDPOINTS and not verify_turnstile_submission():
        abort(400)
    if current_app.config.get("TESTING"):
        return
    key = (request.remote_addr or "local", request.endpoint or request.path)
    timestamp = datetime.now(timezone.utc).timestamp()
    bucket = [
        item
        for item in _POST_RATE_LIMITS.get(key, [])
        if timestamp - item < RATE_LIMIT_WINDOW_SECONDS
    ]
    if len(bucket) >= RATE_LIMIT_MAX_POSTS:
        abort(429)
    bucket.append(timestamp)
    _POST_RATE_LIMITS[key] = bucket


def add_security_headers(response):
    response.headers.setdefault("Content-Security-Policy", content_security_policy())
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if should_no_store_response():
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.vary.add("Cookie")
    return response


def content_security_policy() -> str:
    directives = list(CONTENT_SECURITY_POLICY_DIRECTIVES)
    frame_sources: list[str] = []
    if turnstile_enabled():
        for source_directive in ("script-src", "connect-src"):
            directives = [
                add_csp_source(directive, source_directive, "https://challenges.cloudflare.com")
                for directive in directives
            ]
        frame_sources.append("https://challenges.cloudflare.com")
    clerk_origin = clerk_csp_origin()
    if clerk_entry_enabled() and clerk_origin:
        for source_directive in ("script-src", "connect-src", "img-src", "style-src-elem"):
            directives = [
                add_csp_source(directive, source_directive, clerk_origin)
                for directive in directives
            ]
        frame_sources.append(clerk_origin)
    if frame_sources:
        directives.append("frame-src " + " ".join(dict.fromkeys(frame_sources)))
    return "; ".join(directives)


def add_csp_source(directive: str, directive_name: str, source: str) -> str:
    if directive.startswith(f"{directive_name} "):
        parts = directive.split()
        if source not in parts:
            return directive + " " + source
    return directive


def turnstile_enabled() -> bool:
    return bool(
        not current_app.config.get("DISABLE_TURNSTILE", False)
        and current_app.config.get("TURNSTILE_SITE_KEY")
        and current_app.config.get("TURNSTILE_SECRET_KEY")
    )


def turnstile_site_key() -> str:
    return str(current_app.config.get("TURNSTILE_SITE_KEY", ""))


def clerk_publishable_key() -> str:
    return str(current_app.config.get("CLERK_PUBLISHABLE_KEY", "")).strip()


def normalized_clerk_frontend_api_url() -> str:
    return normalize_clerk_frontend_api_url(current_app.config.get("CLERK_FRONTEND_API_URL", ""))


def normalize_clerk_frontend_api_url(value: str | None) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    if raw_value.startswith("/") and not raw_value.startswith("//"):
        path = raw_value.rstrip("/")
        return path if path and path != "/" else ""
    parsed = urlparse(raw_value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not is_workdoe_domain(parsed.hostname)
    ):
        return ""
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def is_workdoe_domain(hostname: str | None) -> bool:
    host = (hostname or "").strip().lower().rstrip(".")
    return host == WORKDOE_PUBLIC_DOMAIN or host.endswith(f".{WORKDOE_PUBLIC_DOMAIN}")


def clerk_frontend_api_url() -> str:
    return normalized_clerk_frontend_api_url()


def clerk_proxy_url() -> str:
    frontend_api_url = normalized_clerk_frontend_api_url()
    if frontend_api_url.startswith(CLERK_PROXY_PATH):
        return frontend_api_url
    parsed = urlparse(frontend_api_url)
    if is_workdoe_domain(parsed.hostname) and parsed.path.startswith(CLERK_PROXY_PATH):
        return frontend_api_url
    return ""


def clerk_csp_origin() -> str:
    frontend_api_url = normalized_clerk_frontend_api_url()
    parsed = urlparse(frontend_api_url)
    if parsed.scheme == "https" and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def clerk_entry_enabled() -> bool:
    return bool(
        current_app.config.get("AUTH_PROVIDER") == "clerk"
        and current_app.config.get("CLERK_LOGIN_MODE") == "same_domain_email_code"
        and clerk_publishable_key()
        and normalized_clerk_frontend_api_url()
    )


def verify_turnstile_submission() -> bool:
    if not turnstile_enabled():
        return True
    token = (request.form.get("cf-turnstile-response") or "").strip()
    if not token or len(token) > TURNSTILE_TOKEN_MAX_LENGTH:
        return False
    if current_app.config.get("TESTING"):
        return token in set(current_app.config.get("TURNSTILE_TEST_TOKENS", ()))
    return verify_turnstile_token(token, request.remote_addr or "")


def verify_turnstile_token(token: str, remote_ip: str) -> bool:
    payload = {
        "secret": current_app.config["TURNSTILE_SECRET_KEY"],
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip
    data = urlencode(payload).encode("utf-8")
    verify_request = UrlRequest(
        current_app.config["TURNSTILE_VERIFY_URL"],
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(verify_request, timeout=4) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    return bool(result.get("success"))


def should_no_store_response() -> bool:
    if request.endpoint == "static":
        return False
    if request.path.startswith("/media/"):
        return True
    if getattr(g, "user", None) is not None:
        return True
    return request.endpoint in AUTH_FLOW_ENDPOINTS


def csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_login_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def normalize_login_code_submission(value: str | None) -> str:
    return re.sub(r"[\s-]+", "", value or "")


def issue_login_code(
    email: str,
    role: str,
    display_name: str,
    company_name: str,
    intent: str,
    selected_job_id: int | None,
) -> None:
    code = generate_login_code()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=10)
    ).isoformat(timespec="seconds")
    cur = get_db().execute(
        """
        INSERT INTO login_codes
            (email, role, display_name, company_name, intent, selected_job_id, code_hash,
             expires_at, used_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
        """,
        (
            email,
            role,
            display_name,
            company_name,
            intent,
            selected_job_id,
            hash_token(code),
            expires_at,
            now_iso(),
        ),
    )
    get_db().commit()
    session["start_code_id"] = int(cur.lastrowid)
    session["local_login_code"] = code


def normalize_intent(value: str | None) -> str:
    return value if value in {"post-job", "find-work"} else "post-job"


def selected_start_job(value: str | int | None, intent: str):
    if intent != "find-work":
        return None
    job_id = parse_positive_int(value)
    if not job_id:
        return None
    return get_db().execute(
        """
        SELECT id, title, category, city, state
        FROM jobs
        WHERE id = ? AND status = 'open'
        """,
        (job_id,),
    ).fetchone()


def selected_next_job(value: str | None):
    if not value:
        return None
    path = value.split("?", 1)[0].split("#", 1)[0].rstrip("/") or "/"
    parts = [part for part in path.split("/") if part]
    if len(parts) == 2 and parts[0] == "jobs":
        return selected_start_job(parts[1], "find-work")
    return None


def start_url_for_email(email: str, selected_job=None) -> str:
    args = {
        "intent": "find-work" if selected_job else "post-job",
        "email": email,
    }
    if selected_job:
        args["job_id"] = selected_job["id"]
    return url_for("start", **args)


def safe_next_url(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return ""
    if value == url_for("logout"):
        return ""
    return value


def safe_return_url(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme not in {"http", "https"} or parsed.netloc != request.host:
            return ""
        value = parsed.path or "/"
        if parsed.query:
            value = f"{value}?{parsed.query}"
        if parsed.fragment:
            value = f"{value}#{parsed.fragment}"
    return safe_next_url(value)


def next_url_for_role(value: str, role: str) -> str:
    if not value:
        return ""
    path = value.split("?", 1)[0].split("#", 1)[0].rstrip("/") or "/"
    parts = [part for part in path.split("/") if part]
    if path == "/jobs/new":
        return value if role == "client" else ""
    if len(parts) == 2 and parts[0] == "jobs" and parts[1].isdigit():
        return value if role in {"contractor", "admin"} else ""
    if parts and parts[0] == "client":
        return value if role in {"client", "admin"} else ""
    if path == "/leads" or (parts and parts[0] == "contractor"):
        return value if role == "contractor" else ""
    if parts and parts[0] == "admin":
        return value if role == "admin" else ""
    return value


def blank_job_form() -> dict[str, str]:
    return {
        "title": "",
        "category": JOB_CATEGORIES[0],
        "desired_date": "",
        "city": "",
        "state": "DC",
        "zip_code": "",
        "description": "",
    }


def job_to_form(job) -> dict[str, str]:
    return {
        "title": job["title"],
        "category": job["category"],
        "desired_date": job["desired_date"] or "",
        "city": job["city"],
        "state": job["state"],
        "zip_code": job["zip_code"],
        "description": job["description"],
    }


def render_job_form(form: dict[str, str], mode: str, job=None, errors: list[str] | None = None):
    is_edit = mode == "edit"
    cancel_url = url_for("client_job_detail", job_id=job["id"]) if is_edit and job else url_for("client_dashboard")
    return render_template(
        "job_form.html",
        form=form,
        error_feedback=job_error_feedback(errors or []),
        mode=mode,
        page_eyebrow="Edit client job" if is_edit else "New client job",
        page_title="Edit job." if is_edit else "Post a job.",
        page_intro=(
            "Keep scope, timing, and approximate location current."
            if is_edit
            else "Approximate location stays public. Exact details wait for approval."
        ),
        submit_label="Save changes" if is_edit else "Post job",
        cancel_url=cancel_url,
        today=today_iso(),
        title_max=JOB_TITLE_MAX_LENGTH,
        city_max=JOB_CITY_MAX_LENGTH,
        dmv_city_options=dmv_city_options(),
        dmv_zip_options=dmv_zip_options(),
        description_min=JOB_DESCRIPTION_MIN_LENGTH,
        description_max=JOB_DESCRIPTION_MAX_LENGTH,
    )


def dmv_city_options() -> list[dict[str, str]]:
    seen = set()
    options = []
    for city, state, *_coords in DMV_ZIPS.values():
        key = (city, state)
        if key in seen:
            continue
        seen.add(key)
        options.append({"city": city, "state": state, "label": f"{city}, {state}"})
    return sorted(options, key=lambda option: (option["state"], option["city"]))


def dmv_zip_options() -> list[dict[str, str]]:
    return [
        {"zip": zip_code, "label": f"{city}, {state}"}
        for zip_code, (city, state, *_coords) in sorted(DMV_ZIPS.items())
    ]


def build_error_feedback(errors: list[str], resolver, fields: list[str]) -> dict:
    field_errors = {field: [] for field in fields}
    summary = []
    for message in errors:
        field = resolver(message)
        item = {
            "message": message,
            "field": field,
            "field_id": f"{resolver.__name__.replace('_error_field', '')}-{field.replace('_', '-')}"
            if field
            else "",
        }
        summary.append(item)
        if field:
            field_errors[field].append(message)
    return {"summary": summary, "fields": field_errors}


def job_error_feedback(errors: list[str]) -> dict:
    return build_error_feedback(
        errors,
        job_error_field,
        ["title", "category", "desired_date", "city", "state", "zip_code", "description"],
    )


def job_error_field(message: str) -> str:
    if "job title" in message:
        return "title"
    if "curated category" in message:
        return "category"
    if "valid desired date" in message or "future desired date" in message:
        return "desired_date"
    if "city" in message:
        return "city"
    if "DC, MD, or VA" in message:
        return "state"
    if "ZIP code" in message:
        return "zip_code"
    if "about the work" in message or "description" in message:
        return "description"
    return ""


def contractor_profile_to_form(profile) -> dict[str, str]:
    if not profile:
        return {
            "business_name": "",
            "trades": "",
            "service_area": "DMV area",
            "intro": "",
            "insurance_status": "",
            "license_number": "",
            "years_in_business": "",
            "website": "",
            "phone": "",
        }
    return {
        "business_name": profile["business_name"] or "",
        "trades": profile["trades"] or "",
        "service_area": profile["service_area"] or "",
        "intro": profile["intro"] or "",
        "insurance_status": profile["insurance_status"] or "",
        "license_number": profile["license_number"] or "",
        "years_in_business": (
            "" if profile["years_in_business"] is None else str(profile["years_in_business"])
        ),
        "website": profile["website"] or "",
        "phone": profile["phone"] or "",
    }


def render_contractor_profile_form(form: dict[str, str], photos):
    return render_template(
        "contractor_profile.html",
        form=form,
        photos=photos,
        selected_trades=parse_trades(form["trades"]),
        limits=contractor_profile_limits(),
    )


def cleaned_contractor_profile_form(form) -> dict[str, str]:
    selected = set(form.getlist("trades"))
    trades = [category for category in JOB_CATEGORIES if category in selected]
    return {
        "business_name": compact_spaces(form.get("business_name")),
        "trades": ", ".join(trades),
        "service_area": compact_spaces(form.get("service_area")),
        "intro": (form.get("intro") or "").strip(),
        "insurance_status": compact_spaces(form.get("insurance_status")),
        "license_number": compact_spaces(form.get("license_number")),
        "years_in_business": compact_spaces(form.get("years_in_business")),
        "website": compact_spaces(form.get("website")),
        "phone": compact_spaces(form.get("phone")),
    }


def validate_contractor_profile_form(form: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if not form["business_name"]:
        errors.append("Add a business name.")
    elif len(form["business_name"]) > PROFILE_BUSINESS_MAX_LENGTH:
        errors.append(f"Keep the business name under {PROFILE_BUSINESS_MAX_LENGTH} characters.")
    if not form["trades"]:
        errors.append("Choose at least one trade.")
    elif len(form["trades"]) > PROFILE_TRADES_MAX_LENGTH:
        errors.append("Choose fewer trades for the beta profile.")
    if not form["service_area"]:
        errors.append("Add a service area.")
    elif len(form["service_area"]) > PROFILE_SERVICE_AREA_MAX_LENGTH:
        errors.append(f"Keep the service area under {PROFILE_SERVICE_AREA_MAX_LENGTH} characters.")
    if len(form["intro"]) < PROFILE_INTRO_MIN_LENGTH:
        errors.append(f"Add at least {PROFILE_INTRO_MIN_LENGTH} characters about your business.")
    elif len(form["intro"]) > PROFILE_INTRO_MAX_LENGTH:
        errors.append(f"Keep the intro under {PROFILE_INTRO_MAX_LENGTH} characters.")
    if len(form["insurance_status"]) > PROFILE_INSURANCE_MAX_LENGTH:
        errors.append(f"Keep the insurance status under {PROFILE_INSURANCE_MAX_LENGTH} characters.")
    if len(form["license_number"]) > PROFILE_LICENSE_MAX_LENGTH:
        errors.append(f"Keep the license number under {PROFILE_LICENSE_MAX_LENGTH} characters.")
    if form["years_in_business"]:
        try:
            years = int(form["years_in_business"])
        except ValueError:
            errors.append("Use a whole number for years in business.")
        else:
            if years < 0 or years > PROFILE_YEARS_MAX:
                errors.append(f"Use 0 to {PROFILE_YEARS_MAX} for years in business.")
    if form["website"]:
        if len(form["website"]) > PROFILE_WEBSITE_MAX_LENGTH:
            errors.append(f"Keep the website under {PROFILE_WEBSITE_MAX_LENGTH} characters.")
        else:
            parsed = urlparse(form["website"])
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append("Use a full website URL that starts with http:// or https://.")
    if len(form["phone"]) > PROFILE_PHONE_MAX_LENGTH:
        errors.append(f"Keep the phone under {PROFILE_PHONE_MAX_LENGTH} characters.")
    return errors


def profile_years_value(value: str):
    return int(value) if value else None


def contractor_profile_limits() -> dict[str, int]:
    return {
        "business_max": PROFILE_BUSINESS_MAX_LENGTH,
        "trades_max": PROFILE_TRADES_MAX_LENGTH,
        "service_area_max": PROFILE_SERVICE_AREA_MAX_LENGTH,
        "intro_min": PROFILE_INTRO_MIN_LENGTH,
        "intro_max": PROFILE_INTRO_MAX_LENGTH,
        "insurance_max": PROFILE_INSURANCE_MAX_LENGTH,
        "license_max": PROFILE_LICENSE_MAX_LENGTH,
        "years_max": PROFILE_YEARS_MAX,
        "website_max": PROFILE_WEBSITE_MAX_LENGTH,
        "phone_max": PROFILE_PHONE_MAX_LENGTH,
    }


def cleaned_job_form(form) -> dict[str, str]:
    return {
        "title": compact_spaces(form.get("title")),
        "category": (form.get("category") or "").strip(),
        "desired_date": (form.get("desired_date") or "").strip(),
        "city": compact_spaces(form.get("city")),
        "state": (form.get("state") or "").strip().upper(),
        "zip_code": "".join(ch for ch in (form.get("zip_code") or "") if ch.isdigit())[:5],
        "description": (form.get("description") or "").strip(),
    }


def validate_job_form(form: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if not form["title"]:
        errors.append("Add a job title.")
    elif len(form["title"]) > JOB_TITLE_MAX_LENGTH:
        errors.append(f"Keep the job title under {JOB_TITLE_MAX_LENGTH} characters.")
    if form["category"] not in JOB_CATEGORIES:
        errors.append("Choose a curated category.")
    if form["state"] not in DMV_STATES:
        errors.append("Use DC, MD, or VA for the first DMV beta.")
    if not form["city"]:
        errors.append("Add the city so the lead can be mapped approximately.")
    elif len(form["city"]) > JOB_CITY_MAX_LENGTH:
        errors.append(f"Keep the city under {JOB_CITY_MAX_LENGTH} characters.")
    if len(form["zip_code"]) != 5:
        errors.append("Use a 5-digit DMV ZIP code.")
    if len(form["description"]) < JOB_DESCRIPTION_MIN_LENGTH:
        errors.append(f"Add at least {JOB_DESCRIPTION_MIN_LENGTH} characters about the work.")
    elif len(form["description"]) > JOB_DESCRIPTION_MAX_LENGTH:
        errors.append(f"Keep the description under {JOB_DESCRIPTION_MAX_LENGTH} characters.")
    if form["desired_date"]:
        try:
            desired_date = date.fromisoformat(form["desired_date"])
        except ValueError:
            errors.append("Use a valid desired date.")
        else:
            if desired_date < datetime.now(timezone.utc).date():
                errors.append("Choose today or a future desired date.")
    return errors


def blank_bid_form() -> dict[str, str]:
    return {
        "scope_note": "",
        "price_range": "",
        "timeline": "",
        "experience": "",
        "questions": "",
        "availability": "",
    }


def cleaned_bid_form(form) -> dict[str, str]:
    return {
        "scope_note": (form.get("scope_note") or "").strip(),
        "price_range": compact_spaces(form.get("price_range")),
        "timeline": compact_spaces(form.get("timeline")),
        "experience": (form.get("experience") or "").strip(),
        "questions": (form.get("questions") or "").strip(),
        "availability": compact_spaces(form.get("availability")),
    }


def validate_bid_form(form: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if len(form["scope_note"]) < BID_SCOPE_MIN_LENGTH:
        errors.append(f"Add at least {BID_SCOPE_MIN_LENGTH} characters about the scope.")
    elif len(form["scope_note"]) > BID_SCOPE_MAX_LENGTH:
        errors.append(f"Keep the scope note under {BID_SCOPE_MAX_LENGTH} characters.")
    if not form["price_range"]:
        errors.append("Add a price or range.")
    elif len(form["price_range"]) > BID_PRICE_MAX_LENGTH:
        errors.append(f"Keep the price range under {BID_PRICE_MAX_LENGTH} characters.")
    if not form["timeline"]:
        errors.append("Add a timeline.")
    elif len(form["timeline"]) > BID_TIMELINE_MAX_LENGTH:
        errors.append(f"Keep the timeline under {BID_TIMELINE_MAX_LENGTH} characters.")
    if len(form["experience"]) < BID_EXPERIENCE_MIN_LENGTH:
        errors.append(f"Add at least {BID_EXPERIENCE_MIN_LENGTH} characters about relevant experience.")
    elif len(form["experience"]) > BID_EXPERIENCE_MAX_LENGTH:
        errors.append(f"Keep relevant experience under {BID_EXPERIENCE_MAX_LENGTH} characters.")
    if len(form["questions"]) > BID_QUESTIONS_MAX_LENGTH:
        errors.append(f"Keep questions under {BID_QUESTIONS_MAX_LENGTH} characters.")
    if not form["availability"]:
        errors.append("Add availability.")
    elif len(form["availability"]) > BID_AVAILABILITY_MAX_LENGTH:
        errors.append(f"Keep availability under {BID_AVAILABILITY_MAX_LENGTH} characters.")
    return errors


def bid_error_feedback(errors: list[str]) -> dict:
    return build_error_feedback(
        errors,
        bid_error_field,
        ["scope_note", "price_range", "timeline", "experience", "questions", "availability"],
    )


def bid_error_field(message: str) -> str:
    if "scope" in message:
        return "scope_note"
    if "price" in message:
        return "price_range"
    if "timeline" in message:
        return "timeline"
    if "experience" in message:
        return "experience"
    if "questions" in message:
        return "questions"
    if "availability" in message:
        return "availability"
    return ""


def bid_limits() -> dict[str, int]:
    return {
        "scope_min": BID_SCOPE_MIN_LENGTH,
        "scope_max": BID_SCOPE_MAX_LENGTH,
        "price_max": BID_PRICE_MAX_LENGTH,
        "timeline_max": BID_TIMELINE_MAX_LENGTH,
        "experience_min": BID_EXPERIENCE_MIN_LENGTH,
        "experience_max": BID_EXPERIENCE_MAX_LENGTH,
        "questions_max": BID_QUESTIONS_MAX_LENGTH,
        "availability_max": BID_AVAILABILITY_MAX_LENGTH,
    }


def compact_spaces(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def parse_limit(value: str | None, default: int, maximum: int) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, maximum))


def parse_positive_int(value: str | int | None) -> int | None:
    try:
        parsed = int(value or "")
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def report_target_exists(target_type: str, target_id: int) -> bool:
    target_queries = {
        "job": "SELECT 1 FROM jobs WHERE id = ?",
        "message": "SELECT 1 FROM messages WHERE id = ?",
        "profile": "SELECT 1 FROM contractor_profiles WHERE user_id = ?",
    }
    query = target_queries.get(target_type)
    if not query:
        return False
    return get_db().execute(query, (target_id,)).fetchone() is not None


def get_or_create_user_from_login_code(login_code) -> int:
    db = get_db()
    existing = db.execute("SELECT * FROM users WHERE email = ?", (login_code["email"],)).fetchone()
    if existing:
        return int(existing["id"])

    cur = db.execute(
        """
        INSERT INTO users
            (email, password_hash, role, display_name, company_name,
             status, email_verified, created_at)
        VALUES (?, ?, ?, ?, ?, 'active', 1, ?)
        """,
        (
            login_code["email"],
            generate_password_hash(secrets.token_urlsafe(32)),
            login_code["role"],
            login_code["display_name"],
            login_code["company_name"],
            now_iso(),
        ),
    )
    user_id = int(cur.lastrowid)
    if login_code["role"] == "client":
        db.execute(
            """
            INSERT INTO client_profiles (user_id, organization_name, phone)
            VALUES (?, ?, '')
            """,
            (user_id, login_code["company_name"] or login_code["display_name"]),
        )
    else:
        db.execute(
            """
            INSERT INTO contractor_profiles
                (user_id, business_name, trades, service_area, intro,
                 insurance_status, license_number, years_in_business,
                 website, phone, updated_at)
            VALUES (?, ?, '', 'DMV area', '', '', '', NULL, '', '', ?)
            """,
            (user_id, login_code["company_name"] or login_code["display_name"], now_iso()),
        )
    return user_id


def after_start_url(role: str, intent: str, selected_job_id: str | int | None = None) -> str:
    if role == "client" and intent == "post-job":
        return url_for("new_job")
    if role == "contractor" and intent == "find-work":
        selected_job = selected_start_job(selected_job_id, intent)
        if selected_job:
            return url_for("contractor_job_detail", job_id=selected_job["id"])
        return url_for("leads")
    if role == "admin":
        return url_for("admin_dashboard")
    return url_for("dashboard")


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash("Sign in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        return view(**kwargs)

    return wrapped_view


def role_required(*roles: str):
    def decorator(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                flash("Sign in to continue.", "error")
                return redirect(url_for("login", next=request.path))
            if g.user["role"] not in roles:
                abort(403)
            return view(**kwargs)

        return wrapped_view

    return decorator


def fetch_job(job_id: int):
    return get_db().execute(
        """
        SELECT jobs.*, users.display_name AS client_name, users.company_name AS client_company
        FROM jobs
        JOIN users ON users.id = jobs.client_id
        WHERE jobs.id = ?
        """,
        (job_id,),
    ).fetchone()


def fetch_thread(thread_id: int):
    return get_db().execute(
        """
        SELECT threads.*, jobs.title, jobs.category, jobs.city, jobs.state,
               client.display_name AS client_name,
               contractor.display_name AS contractor_name
        FROM threads
        JOIN jobs ON jobs.id = threads.job_id
        JOIN users AS client ON client.id = threads.client_id
        JOIN users AS contractor ON contractor.id = threads.contractor_id
        WHERE threads.id = ?
        """,
        (thread_id,),
    ).fetchone()


def public_job_filters() -> dict[str, str]:
    category = request.args.get("category", "")
    if category not in JOB_CATEGORIES:
        category = ""
    return {
        "category": category,
        "q": compact_spaces(request.args.get("q"))[:FILTER_QUERY_MAX_LENGTH],
        "sort": normalize_job_sort(request.args.get("sort")),
    }


def normalize_job_sort(value: str | None) -> str:
    allowed = {option[0] for option in JOB_SORT_OPTIONS}
    return value if value in allowed else DEFAULT_JOB_SORT


def public_filters_active(filters: dict[str, str]) -> bool:
    return bool(
        filters.get("category")
        or filters.get("q")
        or filters.get("sort", DEFAULT_JOB_SORT) != DEFAULT_JOB_SORT
    )


def normalize_public_job_target(value: str | None) -> str:
    return value if value in {"login", "start"} else "start"


def normalize_lead_view(value: str | None) -> str:
    allowed = {option[0] for option in LEAD_VIEW_OPTIONS}
    return value if value in allowed else "all"


def lead_view_links(filters: dict[str, str]) -> list[dict[str, str]]:
    links = []
    for value, label in LEAD_VIEW_OPTIONS:
        args = {}
        if filters.get("category"):
            args["category"] = filters["category"]
        if filters.get("q"):
            args["q"] = filters["q"]
        if filters.get("sort", DEFAULT_JOB_SORT) != DEFAULT_JOB_SORT:
            args["sort"] = filters["sort"]
        if value != "all":
            args["view"] = value
        links.append({"value": value, "label": label, "url": url_for("leads", **args)})
    return links


def normalize_client_job_view(value: str | None) -> str:
    allowed = {option[0] for option in CLIENT_JOB_VIEW_OPTIONS}
    return value if value in allowed else "all"


def client_job_view_links() -> list[dict[str, str]]:
    links = []
    for value, label in CLIENT_JOB_VIEW_OPTIONS:
        args = {"view": value} if value != "all" else {}
        links.append({"value": value, "label": label, "url": url_for("client_dashboard", **args)})
    return links


def normalize_bid_view(value: str | None) -> str:
    allowed = {option[0] for option in BID_VIEW_OPTIONS}
    return value if value in allowed else "all"


def bid_view_links(job_id: int) -> list[dict[str, str]]:
    links = []
    for value, label in BID_VIEW_OPTIONS:
        args = {"bids": value} if value != "all" else {}
        links.append(
            {
                "value": value,
                "label": label,
                "url": url_for("client_job_detail", job_id=job_id, **args),
            }
        )
    return links


def contractor_bid_view_links() -> list[dict[str, str]]:
    links = []
    for value, label in BID_VIEW_OPTIONS:
        args = {"bids": value} if value != "all" else {}
        links.append({"value": value, "label": label, "url": url_for("contractor_dashboard", **args)})
    return links


def map_jobs_api_url(
    filters: dict[str, str],
    limit: int,
    target: str | None = None,
    view: str | None = None,
) -> str:
    args: dict[str, str | int] = {"limit": limit}
    if filters.get("category"):
        args["category"] = filters["category"]
    if filters.get("q"):
        args["q"] = filters["q"]
    if filters.get("sort", DEFAULT_JOB_SORT) != DEFAULT_JOB_SORT:
        args["sort"] = filters["sort"]
    if target:
        args["target"] = target
    lead_view = normalize_lead_view(view)
    if lead_view != "all":
        args["view"] = lead_view
    return url_for("api_open_jobs", **args)


def attach_contractor_request_status(jobs, contractor_id: int) -> list[dict]:
    annotated_jobs = [{key: row[key] for key in row.keys()} for row in jobs]
    if not annotated_jobs:
        return annotated_jobs
    placeholders = ", ".join("?" for _ in annotated_jobs)
    params = [contractor_id, *(job["id"] for job in annotated_jobs)]
    rows = get_db().execute(
        f"""
        SELECT job_id, status
        FROM match_requests
        WHERE contractor_id = ? AND job_id IN ({placeholders})
        """,
        params,
    ).fetchall()
    statuses = {row["job_id"]: row["status"] for row in rows}
    for job in annotated_jobs:
        job["request_status"] = statuses.get(job["id"])
    return annotated_jobs


def filter_jobs_by_lead_view(jobs, lead_view: str) -> list[dict]:
    if lead_view == "new":
        return [job for job in jobs if not job["request_status"]]
    if lead_view == "sent":
        return [job for job in jobs if job["request_status"]]
    return list(jobs)


def filter_map_jobs_by_jobs(map_jobs, jobs) -> list[dict]:
    job_ids = {job["id"] for job in jobs}
    return [job for job in map_jobs if job["id"] in job_ids]


def filter_client_jobs_by_view(jobs, job_view: str) -> list[dict]:
    if job_view == "review":
        return [job for job in jobs if (job["pending_count"] or 0) > 0]
    if job_view == "open":
        return [job for job in jobs if job["status"] == "open"]
    if job_view == "closed":
        return [job for job in jobs if job["status"] == "closed"]
    return list(jobs)


def filter_bids_by_view(bids, bid_view: str) -> list:
    if bid_view == "all":
        return list(bids)
    return [bid for bid in bids if bid["status"] == bid_view]


def public_open_jobs(
    limit: int = 8,
    filters: dict[str, str] | None = None,
    target: str = "start",
):
    active_filters = filters or {"category": "", "q": "", "sort": DEFAULT_JOB_SORT}
    public_target = normalize_public_job_target(target)
    sql = [
        """
        SELECT jobs.*,
               COUNT(job_photos.id) AS photo_count
        FROM jobs
        LEFT JOIN job_photos ON job_photos.job_id = jobs.id AND job_photos.is_hidden = 0
        WHERE jobs.status = 'open'
        """,
    ]
    params: list[str | int] = []
    if active_filters["category"]:
        sql.append("AND jobs.category = ?")
        params.append(active_filters["category"])
    if active_filters["q"]:
        like = f"%{active_filters['q']}%"
        sql.append(
            "AND (jobs.city LIKE ? OR jobs.state LIKE ? OR jobs.zip_code LIKE ? OR jobs.title LIKE ?)"
        )
        params.extend([like, like, like, like])
    sort_order = normalize_job_sort(active_filters.get("sort"))
    order_clauses = {
        "newest": "jobs.created_at DESC, jobs.id DESC",
        "soonest": (
            "CASE WHEN jobs.desired_date IS NULL OR jobs.desired_date = '' THEN 1 ELSE 0 END, "
            "jobs.desired_date ASC, jobs.created_at DESC, jobs.id DESC"
        ),
        "city": "jobs.city COLLATE NOCASE ASC, jobs.created_at DESC, jobs.id DESC",
    }
    sql.append(f"GROUP BY jobs.id ORDER BY {order_clauses[sort_order]} LIMIT ?")
    params.append(limit)
    jobs = get_db().execute("\n".join(sql), params).fetchall()
    if g.user and g.user["role"] in {"contractor", "admin"}:
        make_url = lambda row: url_for("contractor_job_detail", job_id=row["id"])
        action_label = "View"
    else:
        if public_target == "login":
            make_url = lambda row: url_for(
                "login",
                next=url_for("contractor_job_detail", job_id=row["id"]),
            )
            action_label = "Sign in"
        else:
            make_url = lambda row: url_for("start", intent="find-work", job_id=row["id"])
            action_label = "Start"
    map_jobs = [
        {
            "id": row["id"],
            "title": row["title"],
            "category": row["category"],
            "city": row["city"],
            "state": row["state"],
            "lat": row["approx_lat"],
            "lng": row["approx_lng"],
            "url": make_url(row),
            "action_label": action_label,
        }
        for row in jobs
        if row["approx_lat"] and row["approx_lng"]
    ]
    return jobs, map_jobs


def ensure_thread_for_match(match) -> int:
    db = get_db()
    existing = db.execute(
        "SELECT id FROM threads WHERE match_request_id = ?",
        (match["id"],),
    ).fetchone()
    if existing:
        return int(existing["id"])
    cur = db.execute(
        """
        INSERT INTO threads (job_id, match_request_id, client_id, contractor_id, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            match["job_id"],
            match["id"],
            match["client_id"],
            match["contractor_id"],
            now_iso(),
        ),
    )
    thread_id = int(cur.lastrowid)
    db.execute(
        """
        INSERT INTO messages (thread_id, sender_id, body, is_hidden, created_at)
        VALUES (?, ?, ?, 0, ?)
        """,
        (
            thread_id,
            match["contractor_id"],
            "Thanks for reviewing my mini bid. I am ready to coordinate details here.",
            now_iso(),
        ),
    )
    return thread_id


def log_action(action_type: str, target_type: str, target_id: int, notes: str) -> None:
    get_db().execute(
        """
        INSERT INTO moderation_actions
            (admin_id, action_type, target_type, target_id, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (g.user["id"] if g.user else None, action_type, target_type, target_id, notes, now_iso()),
    )


def approximate_location(city: str, state: str, zip_code: str) -> tuple[float, float]:
    zip_clean = "".join(ch for ch in zip_code if ch.isdigit())[:5]
    if zip_clean in DMV_ZIPS:
        return DMV_ZIPS[zip_clean][2], DMV_ZIPS[zip_clean][3]
    key = f"{city.strip().lower()} {state.strip().lower()}"
    if key in CITY_COORDS:
        return CITY_COORDS[key]
    return 38.9072, -77.0369


def parse_trades(trades: str) -> set[str]:
    return {item.strip() for item in (trades or "").split(",") if item.strip()}


def save_job_photos(job_id: int, user_id: int, files) -> None:
    for file in files:
        saved = save_upload(file, f"jobs/{job_id}")
        if not saved:
            continue
        get_db().execute(
            """
            INSERT INTO job_photos
                (job_id, uploaded_by, original_filename, stored_path, content_type, size_bytes,
                 is_hidden, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                job_id,
                user_id,
                saved["original_filename"],
                saved["stored_path"],
                saved["content_type"],
                saved["size_bytes"],
                now_iso(),
            ),
        )


def save_contractor_photos(contractor_id: int, files) -> None:
    for file in files:
        saved = save_upload(file, f"contractors/{contractor_id}")
        if not saved:
            continue
        get_db().execute(
            """
            INSERT INTO contractor_photos
                (contractor_id, original_filename, stored_path, content_type, size_bytes,
                 is_hidden, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (
                contractor_id,
                saved["original_filename"],
                saved["stored_path"],
                saved["content_type"],
                saved["size_bytes"],
                now_iso(),
            ),
        )


def save_upload(file, prefix: str) -> dict | None:
    if file is None or not file.filename:
        return None
    original = secure_filename(file.filename)
    if "." not in original:
        return None
    ext = original.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return None
    content_type = file.mimetype or "application/octet-stream"
    if not content_type.startswith("image/"):
        return None
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    safe_prefix = "/".join(segment for segment in prefix.split("/") if segment)
    stored_path = f"{safe_prefix}/{stored_name}"
    target_dir = Path(current_app.config["UPLOAD_ROOT"]) / safe_prefix
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / stored_name
    file.save(target)
    return {
        "original_filename": original,
        "stored_path": stored_path,
        "content_type": content_type,
        "size_bytes": target.stat().st_size,
    }


def send_private_file(stored_path: str, content_type: str, original_filename: str):
    root = Path(current_app.config["UPLOAD_ROOT"]).resolve()
    full_path = (root / stored_path).resolve()
    try:
        common = os.path.commonpath([str(root), str(full_path)])
    except ValueError:
        abort(404)
    if common != str(root) or not full_path.exists():
        abort(404)
    return send_file(
        full_path,
        mimetype=content_type,
        download_name=original_filename,
        conditional=True,
    )


def money_filter(value) -> str:
    if value in (None, ""):
        return ""
    return str(value)


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


def date_label_filter(value) -> str:
    if value in (None, ""):
        return ""
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    return parsed.strftime("%b %d").replace(" 0", " ")


def datetime_label_filter(value) -> str:
    if value in (None, ""):
        return ""
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    return parsed.strftime("%b %d, %I:%M %p").replace(" 0", " ")
