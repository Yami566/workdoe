from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import secrets
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from flask import (
    Flask,
    Response,
    abort,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from .bid_comparison import bid_comparison, normalize_credential_filter
from .bid_windows import (
    DEFAULT_BID_LIMIT,
    bid_window,
    default_bidding_closes_at,
    extended_bidding_closes_at,
)
from .client_profiles import (
    CLIENT_ACCOUNT_TYPES,
    CLIENT_NOTIFICATION_OPTIONS,
    CLIENT_ORGANIZATION_MAX_LENGTH,
    CLIENT_PROFILE_NOTE_MAX_LENGTH,
    SAVED_LOCATION_CITY_MAX_LENGTH,
    SAVED_LOCATION_LABEL_MAX_LENGTH,
    SAVED_LOCATION_LIMIT,
    ClientProfileError,
    SavedLocationError,
    client_profile_payload,
    client_profile_response,
    saved_location_payload,
)
from .client_project_templates import (
    PROJECT_TEMPLATE_LIMIT,
    PROJECT_TEMPLATE_NAME_MAX_LENGTH,
    ProjectTemplateError,
    project_template_job_form,
    project_template_request_payload,
    project_template_response,
    project_template_values,
)
from .contractor_credentials import (
    CREDENTIAL_IDENTIFIER_MAX_LENGTH,
    CREDENTIAL_JURISDICTIONS,
    CREDENTIAL_NAME_MAX_LENGTH,
    CREDENTIAL_REVIEW_NOTE_MAX_LENGTH,
    CREDENTIAL_TYPES,
    ContractorCredentialError,
    contractor_credential_claim_payload,
    contractor_credential_review_payload,
    credential_response,
    public_credential_responses,
)
from .contractor_preferences import (
    AVAILABILITY_OPTIONS,
    LEAD_ALERT_OPTIONS,
    ContractorPreferenceError,
    availability_payload,
    contractor_preferences_response,
    saved_lead_view_payload,
    saved_lead_view_url,
)
from .contractor_proposal_templates import (
    PROPOSAL_TEMPLATE_LIMIT,
    PROPOSAL_TEMPLATE_NAME_MAX_LENGTH,
    ProposalTemplateError,
    proposal_template_bid_form,
    proposal_template_request_payload,
    proposal_template_response,
    proposal_template_values,
)
from .contractor_public_profiles import contractor_choice_context
from .contractor_reputation import contractor_reputation
from .idempotency import (
    IdempotencyError,
    idempotency_action,
    idempotency_key_hash,
    idempotency_resource_type,
    new_idempotency_key,
    normalize_idempotency_key,
)
from .job_outcomes import (
    LEAD_QUALITY_REASONS,
    OUTCOME_NOTE_MAX_LENGTH,
    PROJECT_CLOSE_REASONS,
    JobOutcomeError,
    lead_quality_reason_label,
    project_close_reason_label,
    validate_lead_quality_payload,
    validate_project_close_payload,
)
from .market_fit import (
    DMV_SERVICE_ZONES,
    ZONE_BY_SLUG,
    annotate_job_fits,
    infer_service_slugs_from_trades,
    infer_zone_slugs_from_area,
    job_zone_slug,
    legacy_trades_for_services,
    normalize_service_slugs,
    normalize_zone_slugs,
    service_area_label,
)
from .match_completions import (
    MatchCompletionError,
    completion_label,
    completion_state,
    validate_completion_confirmation,
)
from .match_reviews import (
    REVIEW_COMMENT_MAX_LENGTH,
    REVIEW_DIMENSIONS,
    REVIEW_RATING_OPTIONS,
    REVIEW_REPORT_MAX_LENGTH,
    REVIEW_RESPONSE_MAX_LENGTH,
    WOULD_WORK_AGAIN_OPTIONS,
    MatchReviewError,
    review_response,
    review_subject_id,
    validate_review_eligibility,
    validate_review_payload,
    validate_review_report,
    validate_review_response,
)
from .pilot_metrics import pilot_cell_metrics
from .project_readiness import project_brief_readiness
from .project_settings import (
    PROJECT_SETTING_BY_VALUE,
    PROJECT_SETTINGS,
    normalize_project_setting,
    project_setting_label,
)
from .public_job_query import (
    PublicJobQueryError,
    encode_public_cursor,
    parse_public_cursor,
    parse_public_viewport,
    public_viewport_sql,
)
from .repeat_provider_invitations import (
    RepeatProviderInvitationError,
    repeat_invitation_response,
    validate_invitation_action,
    validate_repeat_invitation_service,
    validate_repeat_invitation_source,
)
from .service_activation import (
    ACTIVATION_NOT_OPEN_MESSAGE,
    PILOT_ALLOWED_SCOPE,
    PILOT_EXCLUDED_SCOPE,
    PILOT_REQUIREMENTS,
    PILOT_SERVICE_SLUGS,
    PILOT_ZONE_SLUGS,
    activation_is_live,
    enabled_flag,
)
from .service_policy import (
    service_policy,
    service_policy_error,
)
from .service_scope import (
    SCOPE_SCHEMA_VERSION,
    SERVICE_SCOPE_QUESTIONS,
    clean_scope_answers,
    scope_answer_projection,
    validate_scope_answers,
)
from .service_taxonomy import (
    GROUP_BY_SLUG,
    LEGACY_CATEGORY_DEFAULTS,
    SERVICE_ALIASES,
    SERVICE_BY_SLUG,
    SERVICE_GROUPS,
    service_icon,
    service_label,
    service_selection,
)

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
ALLOWED_IMAGE_MIME = {
    "gif": "image/gif",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}
DMV_STATES = {"DC", "MD", "VA"}
JOB_TITLE_MAX_LENGTH = 90
JOB_CITY_MAX_LENGTH = 80
JOB_DESCRIPTION_MIN_LENGTH = 20
JOB_DESCRIPTION_MAX_LENGTH = 1200
JOB_BUDGET_MAX = 10_000_000
JOB_DRAFT_TTL_HOURS = 24
JOB_DRAFT_SESSION_KEY = "job_draft_token"
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
    ("review", "Review"),
    ("open", "Open"),
    ("closed", "Closed"),
)
BID_VIEW_OPTIONS = (
    ("all", "All"),
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
)
MESSAGE_THREAD_VIEW_OPTIONS = (
    ("all", "All"),
    ("unread", "Unread"),
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
PROFILE_WEBSITE_ERROR = "Use a public HTTPS website such as https://example.com."
PROFILE_HOST_LABEL_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_POSTS = 40
_POST_RATE_LIMITS: dict[tuple[str, str], list[float]] = {}
TURNSTILE_TOKEN_MAX_LENGTH = 2048
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_PROTECTED_ENDPOINTS = {
    "login",
    "start",
    "post_project",
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
CLERK_CHALLENGE_ORIGIN = "https://challenges.cloudflare.com"
CLERK_PROTECT_ORIGIN = "https://*.protect.clerk.com"
CLERK_IMAGE_ORIGIN = "https://img.clerk.com"
CLERK_TELEMETRY_ORIGINS = (
    "https://clerk-telemetry.com",
    "https://*.clerk-telemetry.com",
)
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
    "img-src 'self' data: https://tile.openstreetmap.org",
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
        MAP_TILE_URL=os.environ.get(
            "WORKDOE_MAP_TILE_URL",
            "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        ),
        MAP_TILE_ATTRIBUTION=(
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        ),
        SHOW_LOCAL_LOGIN_CODE=not is_production,
        ENFORCE_SERVICE_ACTIVATION=is_production
        or enabled_flag(os.environ.get("WORKDOE_ENFORCE_SERVICE_ACTIVATION")),
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
    app.jinja_env.globals["new_idempotency_key"] = new_idempotency_key
    app.jinja_env.globals["job_categories"] = JOB_CATEGORIES
    app.jinja_env.globals["service_groups"] = SERVICE_GROUPS
    app.jinja_env.globals["service_icon"] = service_icon
    app.jinja_env.globals["service_scope_sets"] = SERVICE_SCOPE_QUESTIONS
    app.jinja_env.globals["service_policy_for"] = service_policy
    app.jinja_env.globals["job_sort_options"] = JOB_SORT_OPTIONS
    app.jinja_env.globals["report_reason_max"] = REPORT_REASON_MAX_LENGTH
    app.jinja_env.globals["filter_query_max"] = FILTER_QUERY_MAX_LENGTH
    app.jinja_env.globals["home_job_limit"] = HOME_JOB_LIMIT
    app.jinja_env.globals["entry_job_limit"] = ENTRY_JOB_LIMIT
    app.jinja_env.globals["lead_board_job_limit"] = LEAD_BOARD_JOB_LIMIT
    app.jinja_env.globals["project_close_reasons"] = PROJECT_CLOSE_REASONS
    app.jinja_env.globals["lead_quality_reasons"] = LEAD_QUALITY_REASONS
    app.jinja_env.globals["outcome_note_max"] = OUTCOME_NOTE_MAX_LENGTH
    app.jinja_env.globals["map_jobs_api_url"] = map_jobs_api_url
    app.jinja_env.globals["turnstile_enabled"] = turnstile_enabled
    app.jinja_env.globals["turnstile_site_key"] = turnstile_site_key
    app.jinja_env.globals["clerk_entry_enabled"] = clerk_entry_enabled
    app.jinja_env.globals["clerk_publishable_key"] = clerk_publishable_key
    app.jinja_env.globals["clerk_frontend_api_url"] = clerk_frontend_api_url
    app.jinja_env.globals["clerk_proxy_url"] = clerk_proxy_url
    app.jinja_env.globals["embedded_dialog_mode"] = embedded_dialog_mode
    app.jinja_env.globals["project_settings"] = PROJECT_SETTINGS
    app.jinja_env.filters["money"] = money_filter
    app.jinja_env.filters["service_name"] = service_name_filter
    app.jinja_env.filters["budget_label"] = budget_label
    app.jinja_env.filters["date_label"] = date_label_filter
    app.jinja_env.filters["datetime_label"] = datetime_label_filter
    app.jinja_env.filters["photo_count_label"] = photo_count_label
    app.jinja_env.filters["message_count_label"] = message_count_label
    app.jinja_env.filters["completion_label"] = completion_label
    app.jinja_env.filters["completion_state"] = completion_state
    app.jinja_env.filters["project_close_reason_label"] = project_close_reason_label
    app.jinja_env.filters["lead_quality_reason_label"] = lead_quality_reason_label
    app.jinja_env.filters["service_activation_live"] = activation_is_live
    app.jinja_env.filters["project_setting_label"] = project_setting_label

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
    if app.config.get("TURNSTILE_VERIFY_URL") != TURNSTILE_VERIFY_URL:
        missing.append(f"WORKDOE_TURNSTILE_VERIFY_URL={TURNSTILE_VERIFY_URL}")
    if auth_provider == "clerk":
        for env_name, config_name in (
            ("CLERK_PUBLISHABLE_KEY", "CLERK_PUBLISHABLE_KEY"),
            ("CLERK_SECRET_KEY", "CLERK_SECRET_KEY"),
            ("CLERK_WEBHOOK_SECRET", "CLERK_WEBHOOK_SECRET"),
            ("CLERK_JWT_KEY", "CLERK_JWT_KEY"),
        ):
            if not app.config.get(config_name):
                missing.append(env_name)
        normalized_frontend_api_url = normalize_clerk_frontend_api_url(
            app.config.get("CLERK_FRONTEND_API_URL")
        )
        parsed_frontend_api_url = urlparse(normalized_frontend_api_url)
        if not normalized_frontend_api_url or not is_workdoe_domain(
            parsed_frontend_api_url.hostname
        ):
            missing.append("CLERK_FRONTEND_API_URL=https://workdoe.com/__clerk")
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


def service_activation_record(service_slug: str, zone_slug: str):
    if not service_slug or not zone_slug:
        return None
    return get_db().execute(
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
        (service_slug, zone_slug, service_slug, zone_slug),
    ).fetchone()


def service_activation_records():
    return get_db().execute(
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
        """
    ).fetchall()


def service_activation_for_form(form: dict[str, str]):
    zone_slug = job_zone_slug(form.get("city"), form.get("state"), form.get("zip_code"))
    return zone_slug, service_activation_record(form.get("service_slug", ""), zone_slug)


def service_activation_open_for_form(form: dict[str, str]) -> tuple[bool, str]:
    zone_slug, activation = service_activation_for_form(form)
    return activation_is_live(activation), zone_slug


def service_activation_required() -> bool:
    return bool(current_app.config.get("ENFORCE_SERVICE_ACTIVATION"))


def live_service_activation_sql(job_alias: str = "jobs") -> str:
    if job_alias != "jobs":
        raise ValueError("Unsupported job alias.")
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

    client_profile_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(client_profiles)").fetchall()
    }
    if "account_type" not in client_profile_columns:
        db.execute(
            "ALTER TABLE client_profiles ADD COLUMN account_type TEXT NOT NULL DEFAULT 'household'"
        )
    if "notification_preference" not in client_profile_columns:
        db.execute(
            "ALTER TABLE client_profiles ADD COLUMN notification_preference TEXT NOT NULL DEFAULT 'workdoe'"
        )
    if "profile_note" not in client_profile_columns:
        db.execute(
            "ALTER TABLE client_profiles ADD COLUMN profile_note TEXT NOT NULL DEFAULT ''"
        )
    if "updated_at" not in client_profile_columns:
        db.execute(
            "ALTER TABLE client_profiles ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''"
        )
    if "email_reminder_consent_at" not in client_profile_columns:
        db.execute(
            "ALTER TABLE client_profiles ADD COLUMN email_reminder_consent_at TEXT"
        )
        db.execute(
            "UPDATE client_profiles SET notification_preference = 'workdoe'"
        )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS client_saved_locations (
            id INTEGER PRIMARY KEY,
            client_id INTEGER NOT NULL
                REFERENCES client_profiles(user_id) ON DELETE CASCADE,
            label TEXT NOT NULL COLLATE NOCASE,
            city TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('DC', 'MD', 'VA')),
            zip_code TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (client_id, label)
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_client_saved_locations_owner
        ON client_saved_locations(client_id, updated_at DESC)
        """
    )
    db.execute(
        """
        UPDATE client_profiles
        SET updated_at = COALESCE(
            NULLIF(updated_at, ''),
            (SELECT users.created_at FROM users WHERE users.id = client_profiles.user_id),
            ?
        )
        WHERE updated_at = ''
        """,
        (now_iso(),),
    )

    contractor_preference_columns = {
        row["name"]
        for row in db.execute(
            "PRAGMA table_info(contractor_lead_preferences)"
        ).fetchall()
    }
    if "saved_service_group_slug" not in contractor_preference_columns:
        db.execute(
            "ALTER TABLE contractor_lead_preferences "
            "ADD COLUMN saved_service_group_slug TEXT NOT NULL DEFAULT ''"
        )
    if "saved_service_slug" not in contractor_preference_columns:
        db.execute(
            "ALTER TABLE contractor_lead_preferences "
            "ADD COLUMN saved_service_slug TEXT NOT NULL DEFAULT ''"
        )
    if "lead_alert_preference" not in contractor_preference_columns:
        db.execute(
            "ALTER TABLE contractor_lead_preferences "
            "ADD COLUMN lead_alert_preference TEXT NOT NULL DEFAULT 'workdoe'"
        )
    if "lead_alert_consent_at" not in contractor_preference_columns:
        db.execute(
            "ALTER TABLE contractor_lead_preferences "
            "ADD COLUMN lead_alert_consent_at TEXT"
        )
        db.execute(
            "UPDATE contractor_lead_preferences "
            "SET lead_alert_preference = 'workdoe', lead_alert_consent_at = NULL"
        )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_contractor_lead_preferences_family
        ON contractor_lead_preferences(saved_service_group_slug, saved_at)
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_contractor_lead_preferences_service
        ON contractor_lead_preferences(saved_service_slug, saved_at)
        """
    )
    db.execute(
        """
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
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_contractor_lead_alert_deliveries_status
        ON contractor_lead_alert_deliveries(status, updated_at)
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
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS service_groups (
            slug TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            icon_name TEXT NOT NULL,
            sort_order INTEGER NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS service_types (
            slug TEXT PRIMARY KEY,
            group_slug TEXT NOT NULL REFERENCES service_groups(slug),
            name TEXT NOT NULL,
            legacy_category TEXT NOT NULL,
            icon_name TEXT NOT NULL,
            sort_order INTEGER NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            UNIQUE(group_slug, name)
        )
        """
    )
    service_type_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(service_types)").fetchall()
    }
    if "icon_name" not in service_type_columns:
        db.execute("ALTER TABLE service_types ADD COLUMN icon_name TEXT")
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS service_aliases (
            alias TEXT PRIMARY KEY COLLATE NOCASE,
            service_slug TEXT NOT NULL REFERENCES service_types(slug) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS service_zones (
            slug TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL CHECK (state IN ('DC', 'MD', 'VA')),
            sort_order INTEGER NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS contractor_service_capabilities (
            contractor_id INTEGER NOT NULL
                REFERENCES contractor_profiles(user_id) ON DELETE CASCADE,
            service_slug TEXT NOT NULL
                REFERENCES service_types(slug) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            PRIMARY KEY (contractor_id, service_slug)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS contractor_service_zones (
            contractor_id INTEGER NOT NULL
                REFERENCES contractor_profiles(user_id) ON DELETE CASCADE,
            zone_slug TEXT NOT NULL
                REFERENCES service_zones(slug) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            PRIMARY KEY (contractor_id, zone_slug)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_contractor_capabilities_service "
        "ON contractor_service_capabilities(service_slug, contractor_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_contractor_zones_zone "
        "ON contractor_service_zones(zone_slug, contractor_id)"
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS service_zone_activations (
            service_slug TEXT NOT NULL
                REFERENCES service_types(slug) ON DELETE CASCADE,
            zone_slug TEXT NOT NULL
                REFERENCES service_zones(slug) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'candidate'
                CHECK (status IN ('candidate', 'active', 'paused', 'retired')),
            allowed_scope TEXT NOT NULL DEFAULT '',
            excluded_scope TEXT NOT NULL DEFAULT '',
            requirements_summary TEXT NOT NULL DEFAULT '',
            minimum_eligible_contractors INTEGER NOT NULL DEFAULT 3
                CHECK (minimum_eligible_contractors BETWEEN 1 AND 100),
            approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            approved_at TEXT,
            reviewed_at TEXT,
            expires_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (service_slug, zone_slug)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_service_zone_activations_status "
        "ON service_zone_activations(status, zone_slug, service_slug)"
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS match_completions (
            match_request_id INTEGER PRIMARY KEY
                REFERENCES match_requests(id) ON DELETE CASCADE,
            client_confirmed_at TEXT,
            contractor_confirmed_at TEXT,
            verified_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_match_completions_verified
        ON match_completions(verified_at, updated_at)
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS match_reviews (
            id INTEGER PRIMARY KEY,
            match_request_id INTEGER NOT NULL
                REFERENCES match_requests(id) ON DELETE CASCADE,
            reviewer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            subject_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            reviewer_role TEXT NOT NULL
                CHECK (reviewer_role IN ('client', 'contractor')),
            communication TEXT NOT NULL
                CHECK (communication IN ('met', 'mixed', 'concern', 'not_applicable')),
            scope_accuracy TEXT NOT NULL
                CHECK (scope_accuracy IN ('met', 'mixed', 'concern', 'not_applicable')),
            timeliness TEXT NOT NULL
                CHECK (timeliness IN ('met', 'mixed', 'concern', 'not_applicable')),
            work_outcome TEXT NOT NULL
                CHECK (work_outcome IN ('met', 'mixed', 'concern', 'not_applicable')),
            would_work_again TEXT NOT NULL
                CHECK (would_work_again IN ('yes', 'unsure', 'no')),
            comment TEXT NOT NULL DEFAULT '',
            response TEXT NOT NULL DEFAULT '',
            response_at TEXT,
            is_hidden INTEGER NOT NULL DEFAULT 0 CHECK (is_hidden IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(match_request_id, reviewer_id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS match_review_reports (
            id INTEGER PRIMARY KEY,
            review_id INTEGER NOT NULL REFERENCES match_reviews(id) ON DELETE CASCADE,
            reporter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'resolved')),
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            UNIQUE(review_id, reporter_id)
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_match_reviews_subject
        ON match_reviews(subject_id, reviewer_role, is_hidden, created_at DESC)
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_match_review_reports_status
        ON match_review_reports(status, created_at DESC)
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS repeat_provider_invitations (
            id INTEGER PRIMARY KEY,
            job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
            source_job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
            source_match_request_id INTEGER
                REFERENCES match_requests(id) ON DELETE SET NULL,
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
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_repeat_provider_invitations_contractor
        ON repeat_provider_invitations(contractor_id, status, updated_at DESC)
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_repeat_provider_invitations_client
        ON repeat_provider_invitations(client_id, status, updated_at DESC)
        """
    )
    job_columns = {row["name"] for row in db.execute("PRAGMA table_info(jobs)").fetchall()}
    if "budget_min" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN budget_min INTEGER")
    if "budget_max" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN budget_max INTEGER")
    if "service_group_slug" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN service_group_slug TEXT")
    if "service_slug" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN service_slug TEXT")
    if "service_zone_slug" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN service_zone_slug TEXT")
    if "bid_limit" not in job_columns:
        db.execute(
            "ALTER TABLE jobs ADD COLUMN bid_limit INTEGER NOT NULL DEFAULT 4"
        )
    if "bidding_closes_at" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN bidding_closes_at TEXT")
    if "close_reason" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN close_reason TEXT")
    if "close_note" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN close_note TEXT NOT NULL DEFAULT ''")
    if "closed_at" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN closed_at TEXT")
    if "project_setting" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN project_setting TEXT NOT NULL DEFAULT ''")
    db.execute(
        "UPDATE jobs SET bid_limit = ? "
        "WHERE bid_limit IS NULL OR bid_limit < 1 OR bid_limit > 8",
        (DEFAULT_BID_LIMIT,),
    )
    db.execute(
        """
        UPDATE jobs
        SET bidding_closes_at = ?
        WHERE (bidding_closes_at IS NULL OR bidding_closes_at = '')
          AND status = 'open'
        """,
        (default_bidding_closes_at(),),
    )
    db.execute(
        """
        UPDATE jobs
        SET bidding_closes_at = COALESCE(NULLIF(created_at, ''), ?)
        WHERE bidding_closes_at IS NULL OR bidding_closes_at = ''
        """,
        (now_iso(),),
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_bidding_window "
        "ON jobs(status, bidding_closes_at)"
    )
    db.execute(
        """
        UPDATE jobs
        SET close_reason = CASE
                WHEN EXISTS (
                    SELECT 1 FROM match_requests
                    WHERE match_requests.job_id = jobs.id
                      AND match_requests.status = 'approved'
                ) THEN 'workdoe-match'
                ELSE 'other'
            END,
            close_note = COALESCE(close_note, ''),
            closed_at = COALESCE(NULLIF(closed_at, ''), NULLIF(updated_at, ''), NULLIF(created_at, ''), ?)
        WHERE status = 'closed'
          AND (close_reason IS NULL OR close_reason = '')
        """,
        (now_iso(),),
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS job_lead_feedback (
            id INTEGER PRIMARY KEY,
            job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            contractor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            reason_code TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(job_id, contractor_id)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_lead_feedback_reason "
        "ON job_lead_feedback(reason_code, created_at)"
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS job_drafts (
            id INTEGER PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            zip_code TEXT NOT NULL,
            description TEXT NOT NULL,
            desired_date TEXT DEFAULT '',
            budget_min INTEGER,
            budget_max INTEGER,
            service_group_slug TEXT,
            service_slug TEXT,
            expires_at TEXT NOT NULL,
            consumed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_drafts_expires ON job_drafts(expires_at, consumed_at)"
    )
    draft_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(job_drafts)").fetchall()
    }
    if "service_group_slug" not in draft_columns:
        db.execute("ALTER TABLE job_drafts ADD COLUMN service_group_slug TEXT")
    if "service_slug" not in draft_columns:
        db.execute("ALTER TABLE job_drafts ADD COLUMN service_slug TEXT")
    if "project_setting" not in draft_columns:
        db.execute(
            "ALTER TABLE job_drafts ADD COLUMN project_setting TEXT NOT NULL DEFAULT ''"
        )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS job_scope_answers (
            job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            schema_version INTEGER NOT NULL,
            question_key TEXT NOT NULL,
            answer_code TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (job_id, question_key)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS job_draft_scope_answers (
            draft_id INTEGER NOT NULL REFERENCES job_drafts(id) ON DELETE CASCADE,
            schema_version INTEGER NOT NULL,
            question_key TEXT NOT NULL,
            answer_code TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (draft_id, question_key)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_scope_answers_bucket "
        "ON job_scope_answers(question_key, answer_code, schema_version)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_draft_scope_answers_bucket "
        "ON job_draft_scope_answers(question_key, answer_code, schema_version)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_service_status "
        "ON jobs(status, service_group_slug, service_slug)"
    )
    backfill_service_buckets(db, "jobs")
    backfill_service_buckets(db, "job_drafts")


def seed_reference_data(db: sqlite3.Connection) -> None:
    for category in JOB_CATEGORIES:
        db.execute(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)",
            (category,),
        )
    for position, group in enumerate(SERVICE_GROUPS, start=1):
        db.execute(
            """
            INSERT OR IGNORE INTO service_groups
                (slug, name, description, icon_name, sort_order, active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (group["slug"], group["name"], group["description"], group["icon"], position),
        )
        for service_position, service in enumerate(group["services"], start=1):
            db.execute(
                """
                INSERT OR IGNORE INTO service_types
                    (slug, group_slug, name, legacy_category, icon_name, sort_order, active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    service[0],
                    group["slug"],
                    service[1],
                    service[2],
                    service_icon(service[0], group["icon"]),
                    service_position,
                ),
            )
            db.execute(
                "UPDATE service_types SET icon_name = ? WHERE slug = ?",
                (service_icon(service[0], group["icon"]), service[0]),
            )
    for alias, service_slug in SERVICE_ALIASES.items():
        db.execute(
            "INSERT OR REPLACE INTO service_aliases (alias, service_slug) VALUES (?, ?)",
            (alias, service_slug),
        )
    for position, zone in enumerate(DMV_SERVICE_ZONES, start=1):
        db.execute(
            """
            INSERT OR IGNORE INTO service_zones
                (slug, name, state, sort_order, active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (zone["slug"], zone["name"], zone["state"], position),
        )
    seed_service_zone_candidates(db)
    backfill_job_service_zones(db)
    backfill_contractor_market_fit(db)


def seed_service_zone_candidates(db: sqlite3.Connection) -> None:
    timestamp = now_iso()
    for service_slug in PILOT_SERVICE_SLUGS:
        for zone_slug in PILOT_ZONE_SLUGS:
            db.execute(
                """
                INSERT OR IGNORE INTO service_zone_activations
                    (service_slug, zone_slug, status, allowed_scope, excluded_scope,
                     requirements_summary, minimum_eligible_contractors,
                     created_at, updated_at)
                VALUES (?, ?, 'candidate', ?, ?, ?, 3, ?, ?)
                """,
                (
                    service_slug,
                    zone_slug,
                    PILOT_ALLOWED_SCOPE,
                    PILOT_EXCLUDED_SCOPE,
                    PILOT_REQUIREMENTS,
                    timestamp,
                    timestamp,
                ),
            )


def backfill_job_service_zones(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """
        SELECT id, city, state, zip_code
        FROM jobs
        WHERE service_zone_slug IS NULL OR service_zone_slug = ''
        """
    ).fetchall()
    for row in rows:
        zone_slug = job_zone_slug(row["city"], row["state"], row["zip_code"])
        if zone_slug:
            db.execute(
                "UPDATE jobs SET service_zone_slug = ? WHERE id = ?",
                (zone_slug, row["id"]),
            )


def backfill_contractor_market_fit(db: sqlite3.Connection) -> None:
    profiles = db.execute(
        "SELECT user_id, trades, service_area FROM contractor_profiles"
    ).fetchall()
    timestamp = now_iso()
    for profile in profiles:
        contractor_id = int(profile["user_id"])
        has_services = db.execute(
            "SELECT 1 FROM contractor_service_capabilities WHERE contractor_id = ? LIMIT 1",
            (contractor_id,),
        ).fetchone()
        if not has_services:
            for service_slug in infer_service_slugs_from_trades(profile["trades"]):
                db.execute(
                    """
                    INSERT OR IGNORE INTO contractor_service_capabilities
                        (contractor_id, service_slug, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (contractor_id, service_slug, timestamp),
                )
        has_zones = db.execute(
            "SELECT 1 FROM contractor_service_zones WHERE contractor_id = ? LIMIT 1",
            (contractor_id,),
        ).fetchone()
        if not has_zones:
            for zone_slug in infer_zone_slugs_from_area(profile["service_area"]):
                db.execute(
                    """
                    INSERT OR IGNORE INTO contractor_service_zones
                        (contractor_id, zone_slug, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (contractor_id, zone_slug, timestamp),
                )


def backfill_service_buckets(db: sqlite3.Connection, table_name: str) -> None:
    update_queries = {
        "jobs": """
            UPDATE jobs
            SET service_group_slug = ?, service_slug = ?
            WHERE category = ? AND (service_slug IS NULL OR service_slug = '')
        """,
        "job_drafts": """
            UPDATE job_drafts
            SET service_group_slug = ?, service_slug = ?
            WHERE category = ? AND (service_slug IS NULL OR service_slug = '')
        """,
    }
    other_queries = {
        "jobs": """
            UPDATE jobs
            SET service_group_slug = 'repairs-installation', service_slug = 'other-service'
            WHERE category = 'Other' AND service_slug = 'general-handyman'
        """,
        "job_drafts": """
            UPDATE job_drafts
            SET service_group_slug = 'repairs-installation', service_slug = 'other-service'
            WHERE category = 'Other' AND service_slug = 'general-handyman'
        """,
    }
    if table_name not in update_queries:
        raise ValueError("Unsupported service bucket table.")
    for category, service_slug in LEGACY_CATEGORY_DEFAULTS.items():
        service = SERVICE_BY_SLUG[service_slug]
        db.execute(
            update_queries[table_name],
            (service["group_slug"], service_slug, category),
        )
    db.execute(other_queries[table_name])


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
    backfill_contractor_market_fit(db)

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
        service = service_selection("", "", category)
        db.execute(
            """
            INSERT INTO jobs
                (client_id, title, category, service_group_slug, service_slug,
                 service_zone_slug, city, state, zip_code, description,
                 desired_date, status, approx_lat, approx_lng,
                 bid_limit, bidding_closes_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?)
            """,
            (
                client_id,
                title,
                category,
                service["service_group_slug"],
                service["service_slug"],
                job_zone_slug(city, state, zip_code),
                city,
                state,
                zip_code,
                description,
                desired_date,
                lat,
                lng,
                DEFAULT_BID_LIMIT,
                default_bidding_closes_at(),
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
    draft_token = session.get(JOB_DRAFT_SESSION_KEY)
    session.clear()
    if draft_token:
        session[JOB_DRAFT_SESSION_KEY] = draft_token
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


def record_local_contractor_lead_alert_candidates(
    db: sqlite3.Connection,
    job_id: int,
) -> int:
    candidates = db.execute(
        """
        SELECT users.id AS contractor_id
        FROM jobs
        JOIN users
          ON users.role = 'contractor' AND users.status = 'active'
        JOIN contractor_lead_preferences
          ON contractor_lead_preferences.contractor_id = users.id
        WHERE jobs.id = ?
          AND jobs.status = 'open'
          AND datetime(jobs.bidding_closes_at) > datetime('now')
          AND contractor_lead_preferences.saved_at IS NOT NULL
          AND contractor_lead_preferences.lead_alert_preference = 'email'
          AND contractor_lead_preferences.lead_alert_consent_at IS NOT NULL
          AND contractor_lead_preferences.availability_status != 'unavailable'
          AND (
              contractor_lead_preferences.saved_category = ''
              OR contractor_lead_preferences.saved_category = jobs.category
          )
          AND (
              contractor_lead_preferences.saved_service_group_slug = ''
              OR contractor_lead_preferences.saved_service_group_slug = jobs.service_group_slug
          )
          AND (
              contractor_lead_preferences.saved_service_slug = ''
              OR contractor_lead_preferences.saved_service_slug = jobs.service_slug
          )
          AND (
              contractor_lead_preferences.saved_query = ''
              OR instr(
                  lower(
                      jobs.title || ' ' || jobs.category || ' ' ||
                      jobs.city || ' ' || jobs.state
                  ),
                  lower(contractor_lead_preferences.saved_query)
              ) > 0
          )
          AND EXISTS (
              SELECT 1 FROM contractor_service_capabilities
              WHERE contractor_service_capabilities.contractor_id = users.id
                AND contractor_service_capabilities.service_slug = jobs.service_slug
          )
          AND EXISTS (
              SELECT 1 FROM contractor_service_zones
              WHERE contractor_service_zones.contractor_id = users.id
                AND contractor_service_zones.zone_slug = jobs.service_zone_slug
          )
          AND NOT EXISTS (
              SELECT 1 FROM match_requests
              WHERE match_requests.job_id = jobs.id
                AND match_requests.contractor_id = users.id
          )
        ORDER BY users.id
        LIMIT 50
        """,
        (job_id,),
    ).fetchall()
    timestamp = now_iso()
    created = 0
    for candidate in candidates:
        result = db.execute(
            """
            INSERT OR IGNORE INTO contractor_lead_alert_deliveries
                (contractor_id, job_id, status, created_at, queued_at,
                 sent_at, updated_at)
            VALUES (?, ?, 'pending', ?, NULL, NULL, ?)
            """,
            (candidate["contractor_id"], job_id, timestamp, timestamp),
        )
        created += int(result.rowcount == 1)
    if created:
        record_automation_event(
            db,
            "contractor-lead-alert-candidates",
            target_type="job",
            target_id=job_id,
            payload={"candidate_count": created},
        )
    return created


def register_routes(app: Flask) -> None:
    @app.route("/")
    def home():
        filters = public_job_filters()
        open_jobs, map_jobs = public_open_jobs(limit=HOME_JOB_LIMIT, filters=filters, target="login")
        selected_family = GROUP_BY_SLUG.get(filters.get("family", ""))
        selected_service = SERVICE_BY_SLUG.get(filters.get("service", ""))
        selected_family_number = ""
        if selected_family:
            selected_family_number = f"{next(index for index, group in enumerate(SERVICE_GROUPS, start=1) if group['slug'] == selected_family['slug']):02d}"
        return render_template(
            "home.html",
            open_jobs=open_jobs,
            map_jobs=map_jobs,
            filters=filters,
            has_filters=public_filters_active(filters),
            selected_family=selected_family,
            selected_service=selected_service,
            selected_family_number=selected_family_number,
            family_filter_links=service_family_filter_links(
                "home", filters, anchor="home-family-title"
            ),
        )

    @app.route("/api/jobs/open")
    def api_open_jobs():
        limit = parse_limit(request.args.get("limit"), default=24, maximum=50)
        filters = public_job_filters()
        target = normalize_public_job_target(request.args.get("target"))
        lead_view = normalize_lead_view(request.args.get("view"))
        try:
            viewport = parse_public_viewport(request.args)
            cursor_offset = parse_public_cursor(request.args.get("cursor"))
        except PublicJobQueryError as exc:
            response = jsonify({"ok": False, "error": str(exc)})
            response.status_code = 400
            response.headers["Cache-Control"] = "no-store"
            return response
        jobs, map_jobs, has_more = public_open_jobs_page(
            limit=limit,
            filters=filters,
            target=target,
            viewport=viewport,
            offset=cursor_offset,
        )
        page_count = len(jobs)
        if lead_view != "all" and g.user and g.user["role"] == "contractor":
            jobs = attach_contractor_request_status(jobs, g.user["id"])
            jobs = filter_jobs_by_lead_view(jobs, lead_view)
            map_jobs = filter_map_jobs_by_jobs(map_jobs, jobs)
        next_cursor = (
            encode_public_cursor(cursor_offset + page_count) if has_more else ""
        )
        response = jsonify(
            {
                "count": len(map_jobs),
                "result_count": len(map_jobs),
                "jobs": map_jobs,
                "next_cursor": next_cursor,
                "truncated": has_more,
                "viewport": viewport,
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
        next_url = safe_next_url(request.values.get("next"))
        parsed_next = urlparse(next_url)
        requested_intent = request.values.get("intent")
        intent = normalize_intent(
            requested_intent
            or ("find-work" if parsed_next.path == url_for("leads") else "post-job")
        )
        filter_values = request.args
        explicit_filter = any(
            request.args.get(key)
            for key in ("category", "family", "service", "q", "sort")
        )
        if parsed_next.path == url_for("leads") and not explicit_filter:
            filter_values = parse_qs(parsed_next.query)
        filters = public_job_filters(filter_values)
        next_url = lead_next_url_with_filters(next_url, filters)
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
                if next_url_for_role(next_url, role):
                    session["login_next_url"] = next_url
                else:
                    session.pop("login_next_url", None)
                return redirect(url_for("verify_start"))
        open_jobs, map_jobs = public_open_jobs(limit=ENTRY_JOB_LIMIT, filters=filters)
        selected_family = GROUP_BY_SLUG.get(filters.get("family", ""))
        return render_template(
            "start.html",
            intent=intent,
            open_jobs=open_jobs,
            map_jobs=map_jobs,
            selected_job=selected_job,
            next_url=next_url,
            clear_next_url=cleared_lead_next_url(next_url),
            filters=filters,
            selected_family=selected_family,
            has_filters=public_filters_active(filters),
            family_filter_links=service_family_filter_links(
                request.endpoint or "start",
                filters,
                base_args={
                    "intent": intent,
                    "job_id": selected_job["id"] if selected_job else "",
                    "next": next_url,
                },
                anchor="live-jobs",
            ),
            form_email=form_email,
            form_display_name=form_display_name,
            form_company_name=form_company_name,
            draft_saved=bool(request.args.get("draft") == "saved" and current_job_draft()),
        )

    @app.route("/create-account", methods=("GET", "POST"))
    def create_account():
        return start()

    @app.route("/post-project", methods=("GET", "POST"))
    def post_project():
        if g.user and g.user["role"] != "client":
            abort(403)
        requested_family = compact_spaces(request.values.get("family"))
        if requested_family not in GROUP_BY_SLUG:
            requested_family = ""
        requested_service = compact_spaces(request.values.get("service"))
        service = SERVICE_BY_SLUG.get(requested_service)
        if not service or requested_family and service["group_slug"] != requested_family:
            requested_service = ""
        elif not requested_family:
            requested_family = service["group_slug"]
        if request.method == "GET" and g.user:
            return redirect(
                url_for(
                    "new_job",
                    family=requested_family or None,
                    service=requested_service or None,
                )
            )

        draft = current_job_draft()
        form = job_to_form(draft) if draft else blank_job_form()
        if not draft and requested_family:
            form["service_group_slug"] = requested_family
        if not draft and requested_service:
            form.update(service_selection(requested_service, requested_family))
        errors: list[str] = []
        if request.method == "POST":
            form = cleaned_job_form(request.form)
            errors = validate_job_form(form)
            if not errors and service_activation_required():
                activation_open, _zone_slug = service_activation_open_for_form(form)
                if not activation_open:
                    errors.append(ACTIVATION_NOT_OPEN_MESSAGE)
            if not errors:
                save_job_draft(form)
                if g.user:
                    return redirect(url_for("new_job"))
                return redirect(url_for("create_account", intent="post-job", draft="saved"))
        return render_template(
            "job_draft.html",
            form=form,
            error_feedback=job_error_feedback(errors),
            today=today_iso(),
            title_max=JOB_TITLE_MAX_LENGTH,
            city_max=JOB_CITY_MAX_LENGTH,
            dmv_city_options=dmv_city_options(),
            dmv_zip_options=dmv_zip_options(),
            description_min=JOB_DESCRIPTION_MIN_LENGTH,
            description_max=JOB_DESCRIPTION_MAX_LENGTH,
            budget_max=JOB_BUDGET_MAX,
        )

    @app.route("/start/verify", methods=("GET", "POST"))
    def verify_start():
        code_id = session.get("start_code_id")
        code_error = ""
        if not code_id:
            flash("Start with your email so we can send a one-time code.", "error")
            return redirect(url_for("create_account"))
        login_code = get_db().execute(
            "SELECT * FROM login_codes WHERE id = ?",
            (code_id,),
        ).fetchone()
        if not login_code or login_code["used_at"] or login_code["expires_at"] < now_iso():
            session.pop("start_code_id", None)
            session.pop("local_login_code", None)
            session.pop("login_next_url", None)
            flash("That one-time code expired. Start again.", "error")
            return redirect(url_for("create_account"))

        if request.method == "POST":
            submitted = normalize_login_code_submission(request.form.get("code"))
            if not re.fullmatch(r"\d{6}", submitted):
                code_error = "Enter the 6-digit code."
            elif not secrets.compare_digest(hash_token(submitted), login_code["code_hash"]):
                code_error = "That code did not match."
            else:
                consumed_at = now_iso()
                consumed = get_db().execute(
                    """
                    UPDATE login_codes
                    SET used_at = ?
                    WHERE id = ? AND used_at IS NULL AND expires_at >= ?
                    """,
                    (consumed_at, code_id, consumed_at),
                )
                if consumed.rowcount != 1:
                    get_db().rollback()
                    session.pop("start_code_id", None)
                    session.pop("local_login_code", None)
                    session.pop("login_next_url", None)
                    flash("That one-time code expired. Start again.", "error")
                    return redirect(url_for("create_account"))
                user_id = get_or_create_user_from_login_code(login_code)
                user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                if user["status"] != "active":
                    get_db().commit()
                    flash("This account is not active. Contact the Workdoe admin.", "error")
                    return redirect(url_for("login"))
                get_db().commit()
                login_next_url = safe_next_url(session.get("login_next_url"))
                sign_in_workdoe_user(user_id)
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

    @app.route("/privacy")
    def privacy():
        return render_template("privacy.html")

    @app.route("/terms")
    def terms():
        return render_template("terms.html")

    @app.route("/robots.txt")
    def robots_txt():
        return Response(public_robots_txt(), mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap_xml():
        return Response(public_sitemap_xml(), mimetype="application/xml")

    @app.route("/.well-known/security.txt")
    def security_txt():
        return Response(public_security_txt(), mimetype="text/plain")

    @app.route("/signup", methods=("GET", "POST"))
    def signup():
        if request.method != "POST":
            return redirect(url_for("create_account"))

        role = request.form.get("role", "")
        intent = "find-work" if role == "contractor" else "post-job"
        email = (request.form.get("email") or "").strip().lower()
        display_name = (request.form.get("display_name") or "").strip()
        company_name = (request.form.get("company_name") or "").strip()
        existing_user = None
        if email and "@" in email:
            existing_user = get_db().execute(
                "SELECT * FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            if existing_user:
                role = existing_user["role"]
                intent = "find-work" if role == "contractor" else "post-job"
                display_name = display_name or existing_user["display_name"]
                company_name = company_name or existing_user["company_name"] or ""

        if role not in {"client", "contractor"}:
            flash("Choose whether this account is for a client or contractor.", "error")
        elif not email or "@" not in email:
            flash("Enter a valid email address.", "error")
        elif not existing_user and not display_name:
            flash("Add your name to create a Workdoe workspace.", "error")
        else:
            issue_login_code(email, role, display_name, company_name, intent, None)
            flash("Use the one-time email code to finish starting.", "success")
            return redirect(url_for("verify_start"))
        return redirect(url_for("create_account", intent=intent))

    @app.route("/login", methods=("GET", "POST"))
    def login():
        next_url = safe_next_url(request.values.get("next"))
        filter_values = request.args
        parsed_next = urlparse(next_url)
        explicit_filter = any(
            request.args.get(key)
            for key in ("category", "family", "service", "q", "sort")
        )
        if parsed_next.path == url_for("leads") and not explicit_filter:
            filter_values = parse_qs(parsed_next.query)
        filters = public_job_filters(filter_values)
        next_url = lead_next_url_with_filters(next_url, filters)
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
                    return redirect(start_url_for_email(email, selected_job, next_url))
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
                sign_in_workdoe_user(int(user["id"]))
                flash("Signed in.", "success")
                return redirect(next_url_for_role(next_url, user["role"]) or url_for("dashboard"))
        open_jobs, map_jobs = public_open_jobs(
            limit=ENTRY_JOB_LIMIT,
            filters=filters,
            target="login",
        )
        selected_family = GROUP_BY_SLUG.get(filters.get("family", ""))
        return render_template(
            "login.html",
            open_jobs=open_jobs,
            map_jobs=map_jobs,
            next_url=next_url,
            clear_next_url=cleared_lead_next_url(next_url),
            login_sign_up_url=start_url_for_email("", selected_job, next_url),
            selected_job=selected_job,
            filters=filters,
            selected_family=selected_family,
            has_filters=public_filters_active(filters),
            family_filter_links=service_family_filter_links(
                "login",
                filters,
                base_args={"next": next_url},
                anchor="live-jobs",
            ),
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

    @app.route("/logout", methods=("POST",))
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

    @app.route("/account")
    @login_required
    def account():
        profile_endpoint = {
            "client": "client_profile",
            "contractor": "contractor_profile",
            "admin": "admin_dashboard",
        }.get(g.user["role"], "dashboard")
        return render_template(
            "account.html",
            profile_url=url_for(profile_endpoint),
        )

    @app.route("/client/dashboard")
    @role_required("client")
    def client_dashboard():
        job_view = normalize_client_job_view(request.args.get("view"))
        jobs, stats, project_history = client_jobs_workspace(g.user["id"], job_view)
        return render_template(
            "client_dashboard.html",
            jobs=jobs,
            project_history=project_history,
            stats=stats,
            job_view=job_view,
            job_view_links=client_job_view_links(),
        )

    @app.route("/client/profile", methods=("GET", "POST"))
    @role_required("client")
    def client_profile():
        profile = ensure_client_profile(g.user)
        profile_form = client_profile_response(profile)
        profile_errors: list[str] = []
        profile_field_errors: dict[str, list[str]] = {}
        if request.method == "POST":
            try:
                profile_form = client_profile_payload(request.form)
            except ClientProfileError as exc:
                profile_errors = exc.errors
                profile_field_errors = exc.field_errors
            else:
                updated_at = now_iso()
                email_reminder_consent_at = (
                    updated_at
                    if profile_form["notification_preference"] == "email"
                    else None
                )
                get_db().execute(
                    """
                    UPDATE client_profiles
                    SET organization_name = ?, account_type = ?,
                        notification_preference = ?,
                        email_reminder_consent_at = ?,
                        profile_note = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (
                        profile_form["organization_name"],
                        profile_form["account_type"],
                        profile_form["notification_preference"],
                        email_reminder_consent_at,
                        profile_form["profile_note"],
                        updated_at,
                        g.user["id"],
                    ),
                )
                get_db().commit()
                flash("Consumer workspace updated.", "success")
                return redirect(url_for("client_profile"))
        return render_client_profile(
            profile_form,
            profile_errors=profile_errors,
            profile_field_errors=profile_field_errors,
            template_form={"source_job_id": request.args.get("source_job", "")},
        )

    @app.route("/client/profile/locations", methods=("POST",))
    @role_required("client")
    def add_client_saved_location():
        try:
            location_form = saved_location_payload(request.form)
        except SavedLocationError as exc:
            return render_client_profile(
                client_profile_response(ensure_client_profile(g.user)),
                location_form=request.form,
                location_errors=exc.errors,
                location_field_errors=exc.field_errors,
            )

        db = get_db()
        count = db.execute(
            "SELECT COUNT(*) AS count FROM client_saved_locations WHERE client_id = ?",
            (g.user["id"],),
        ).fetchone()["count"]
        if count >= SAVED_LOCATION_LIMIT:
            return render_client_profile(
                client_profile_response(ensure_client_profile(g.user)),
                location_form=location_form,
                location_errors=[
                    f"Keep up to {SAVED_LOCATION_LIMIT} saved project areas in this workspace."
                ],
            )
        duplicate = db.execute(
            """
            SELECT 1 FROM client_saved_locations
            WHERE client_id = ? AND label = ? COLLATE NOCASE
            LIMIT 1
            """,
            (g.user["id"], location_form["label"]),
        ).fetchone()
        if duplicate:
            return render_client_profile(
                client_profile_response(ensure_client_profile(g.user)),
                location_form=location_form,
                location_errors=["Use a different name for this saved project area."],
                location_field_errors={
                    "label": ["Use a different name for this saved project area."]
                },
            )
        timestamp = now_iso()
        db.execute(
            """
            INSERT INTO client_saved_locations
                (client_id, label, city, state, zip_code, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                g.user["id"],
                location_form["label"],
                location_form["city"],
                location_form["state"],
                location_form["zip_code"],
                timestamp,
                timestamp,
            ),
        )
        db.commit()
        flash("Project area saved.", "success")
        return redirect(url_for("client_profile") + "#saved-project-areas")

    @app.route("/client/profile/locations/<int:location_id>/delete", methods=("POST",))
    @role_required("client")
    def delete_client_saved_location(location_id: int):
        deleted = get_db().execute(
            "DELETE FROM client_saved_locations WHERE id = ? AND client_id = ?",
            (location_id, g.user["id"]),
        )
        if deleted.rowcount != 1:
            get_db().rollback()
            abort(404)
        get_db().commit()
        flash("Saved project area removed.", "success")
        return redirect(url_for("client_profile") + "#saved-project-areas")

    @app.route("/client/profile/templates", methods=("POST",))
    @role_required("client")
    def add_client_project_template():
        try:
            template_form = project_template_request_payload(request.form)
        except ProjectTemplateError as exc:
            return render_client_profile(
                client_profile_response(ensure_client_profile(g.user)),
                template_form=request.form,
                template_errors=exc.errors,
                template_field_errors=exc.field_errors,
            )
        db = get_db()
        source_job = db.execute(
            "SELECT * FROM jobs WHERE id = ? AND client_id = ?",
            (template_form["source_job_id"], g.user["id"]),
        ).fetchone()
        if not source_job:
            return render_client_profile(
                client_profile_response(ensure_client_profile(g.user)),
                template_form=template_form,
                template_errors=["Choose one of your projects."],
                template_field_errors={"source_job_id": ["Choose one of your projects."]},
            )
        count = db.execute(
            "SELECT COUNT(*) AS count FROM client_project_templates WHERE client_id = ?",
            (g.user["id"],),
        ).fetchone()["count"]
        if count >= PROJECT_TEMPLATE_LIMIT:
            return render_client_profile(
                client_profile_response(ensure_client_profile(g.user)),
                template_form=template_form,
                template_errors=[
                    f"Keep up to {PROJECT_TEMPLATE_LIMIT} reusable project templates."
                ],
            )
        values = project_template_values(
            template_form["name"],
            {**job_to_form(source_job), "id": source_job["id"]},
        )
        timestamp = now_iso()
        try:
            db.execute(
                """
                INSERT INTO client_project_templates
                    (client_id, name, source_job_id, service_group_slug,
                     service_slug, category, title, description,
                     project_setting, budget_min, budget_max,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    g.user["id"],
                    values["name"],
                    values["source_job_id"],
                    values["service_group_slug"] or None,
                    values["service_slug"] or None,
                    values["category"],
                    values["title"],
                    values["description"],
                    values["project_setting"],
                    values["budget_min"],
                    values["budget_max"],
                    timestamp,
                    timestamp,
                ),
            )
        except sqlite3.IntegrityError:
            db.rollback()
            return render_client_profile(
                client_profile_response(ensure_client_profile(g.user)),
                template_form=template_form,
                template_errors=["Use a different name for this project template."],
                template_field_errors={
                    "name": ["Use a different name for this project template."]
                },
            )
        db.commit()
        flash("Project template saved.", "success")
        return redirect(url_for("client_profile") + "#project-templates")

    @app.route("/client/profile/templates/<int:template_id>/delete", methods=("POST",))
    @role_required("client")
    def delete_client_project_template(template_id: int):
        deleted = get_db().execute(
            "DELETE FROM client_project_templates WHERE id = ? AND client_id = ?",
            (template_id, g.user["id"]),
        )
        if deleted.rowcount != 1:
            get_db().rollback()
            abort(404)
        get_db().commit()
        flash("Project template removed.", "success")
        return redirect(url_for("client_profile") + "#project-templates")

    @app.route("/client/requests")
    @role_required("client")
    def client_requests():
        jobs, stats, _history = client_jobs_workspace(g.user["id"], "review")
        return render_template("client_requests.html", jobs=jobs, stats=stats)

    @app.route("/jobs/new", methods=("GET", "POST"))
    @role_required("client")
    def new_job():
        draft = current_job_draft()
        repeat_job = None
        repeat_invitation = None
        project_template = None
        saved_location = None
        repeat_job_id = parse_positive_int(
            request.args.get("repeat") or request.form.get("repeat_source_job_id")
        )
        if not draft and repeat_job_id:
            repeat_job = get_db().execute(
                """
                SELECT *
                FROM jobs
                WHERE id = ? AND client_id = ?
                """,
                (repeat_job_id, g.user["id"]),
            ).fetchone()
        invite_match_id = parse_positive_int(
            request.args.get("invite") or request.form.get("repeat_match_request_id")
        )
        if not draft and repeat_job and invite_match_id:
            source = repeat_invitation_source_record(
                g.user["id"], repeat_job_id, invite_match_id
            )
            try:
                repeat_invitation = validate_repeat_invitation_source(g.user, source)
            except RepeatProviderInvitationError as exc:
                abort(exc.status, str(exc))
        project_template_id = parse_positive_int(request.args.get("template"))
        if not draft and not repeat_job and project_template_id:
            project_template = get_db().execute(
                """
                SELECT * FROM client_project_templates
                WHERE id = ? AND client_id = ?
                """,
                (project_template_id, g.user["id"]),
            ).fetchone()
            if not project_template:
                abort(404)
        saved_location_id = parse_positive_int(request.args.get("location"))
        if not draft and not repeat_job and saved_location_id:
            saved_location = get_db().execute(
                """
                SELECT * FROM client_saved_locations
                WHERE id = ? AND client_id = ?
                """,
                (saved_location_id, g.user["id"]),
            ).fetchone()
        if draft or repeat_job:
            form = job_to_form(draft or repeat_job)
        elif project_template:
            form = project_template_job_form(project_template)
        else:
            form = blank_job_form()
            requested_family = compact_spaces(request.args.get("family"))
            if requested_family in GROUP_BY_SLUG:
                form["service_group_slug"] = requested_family
            requested_service = compact_spaces(request.args.get("service"))
            service = SERVICE_BY_SLUG.get(requested_service)
            if service and (
                not form["service_group_slug"]
                or service["group_slug"] == form["service_group_slug"]
            ):
                form.update(
                    service_selection(requested_service, form["service_group_slug"])
                )
        if saved_location:
            form.update(
                {
                    "city": saved_location["city"],
                    "state": saved_location["state"],
                    "zip_code": saved_location["zip_code"],
                }
            )
        if repeat_job:
            form["desired_date"] = ""
        if request.method == "POST":
            form = cleaned_job_form(request.form)
            errors = validate_job_form(form)
            idempotency_key = ""
            try:
                idempotency_key = request_idempotency_key()
            except IdempotencyError as exc:
                errors.append(str(exc))
            activation_open, service_zone_slug = service_activation_open_for_form(form)
            if not errors and service_activation_required() and not activation_open:
                errors.append(ACTIVATION_NOT_OPEN_MESSAGE)
            if not errors and repeat_invitation:
                try:
                    validate_repeat_invitation_service(
                        repeat_invitation, form["service_slug"]
                    )
                except RepeatProviderInvitationError as exc:
                    errors.append(str(exc))
            if errors:
                return render_job_form(
                    form,
                    mode="new",
                    errors=errors,
                    repeat_invitation=repeat_invitation,
                )
            else:
                lat, lng = approximate_location(form["city"], form["state"], form["zip_code"])
                db = get_db()
                replay_record = begin_idempotent_write(
                    db,
                    g.user["id"],
                    "job-create",
                    "job",
                    idempotency_key,
                )
                replay_job_id = completed_idempotent_resource(replay_record, "job")
                if replay_job_id:
                    db.rollback()
                    flash("Project already posted. Opening the original project.", "success")
                    return redirect(url_for("client_job_detail", job_id=replay_job_id))
                cur = db.execute(
                    """
                    INSERT INTO jobs
                        (client_id, title, category, service_group_slug, service_slug,
                         service_zone_slug, project_setting, city, state, zip_code, description,
                         desired_date, budget_min, budget_max, status, approx_lat, approx_lng,
                         bid_limit, bidding_closes_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        g.user["id"],
                        form["title"],
                        form["category"],
                        form["service_group_slug"],
                        form["service_slug"],
                        service_zone_slug,
                        form["project_setting"],
                        form["city"],
                        form["state"],
                        form["zip_code"],
                        form["description"],
                        form["desired_date"],
                        budget_database_value(form["budget_min"]),
                        budget_database_value(form["budget_max"]),
                        lat,
                        lng,
                        DEFAULT_BID_LIMIT,
                        default_bidding_closes_at(),
                        now_iso(),
                        now_iso(),
                    ),
                )
                job_id = int(cur.lastrowid)
                record_service_policy_acknowledgement(
                    db,
                    user_id=g.user["id"],
                    actor_role="client",
                    context="project-post",
                    service_slug=form["service_slug"],
                    acknowledgement_version=form["service_policy_acknowledgement"],
                    job_id=job_id,
                )
                replace_job_scope_answers(
                    db,
                    job_id,
                    form["service_slug"],
                    form.get("scope_answers", {}),
                )
                if repeat_invitation:
                    timestamp = now_iso()
                    db.execute(
                        """
                        INSERT INTO repeat_provider_invitations
                            (job_id, source_job_id, source_match_request_id,
                             client_id, contractor_id, service_slug, status,
                             created_at, responded_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, NULL, ?)
                        """,
                        (
                            job_id,
                            repeat_invitation["source_job_id"],
                            repeat_invitation["source_match_request_id"],
                            g.user["id"],
                            repeat_invitation["contractor_id"],
                            repeat_invitation["service_slug"],
                            timestamp,
                            timestamp,
                        ),
                    )
                    record_automation_event(
                        db,
                        "repeat-provider-invited",
                        target_type="job",
                        target_id=job_id,
                        payload={
                            "source_job_id": repeat_invitation["source_job_id"],
                            "source_match_request_id": repeat_invitation[
                                "source_match_request_id"
                            ],
                            "contractor_id": repeat_invitation["contractor_id"],
                        },
                    )
                record_local_contractor_lead_alert_candidates(db, job_id)
                save_job_photos(job_id, g.user["id"], request.files.getlist("photos"))
                consume_job_draft()
                complete_idempotent_write(
                    db,
                    g.user["id"],
                    "job-create",
                    "job",
                    idempotency_key,
                    job_id,
                )
                db.commit()
                flash(
                    (
                        f"Job posted. {repeat_invitation['contractor_name']} was invited "
                        "to send a new mini bid."
                    )
                    if repeat_invitation
                    else "Job posted. Contractors can now request a match.",
                    "success",
                )
                return redirect(url_for("client_job_detail", job_id=job_id))
        return render_job_form(
            form,
            mode="new",
            repeat_invitation=repeat_invitation,
        )

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
            submitted = request.form.copy()
            submitted["category"] = job["category"]
            submitted["service_group_slug"] = job["service_group_slug"]
            submitted["service_slug"] = job["service_slug"]
            form = cleaned_job_form(submitted)
            errors = validate_job_form(form)
            activation_open, service_zone_slug = service_activation_open_for_form(form)
            if not errors and service_activation_required() and not activation_open:
                errors.append(ACTIVATION_NOT_OPEN_MESSAGE)
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
                        service_group_slug = ?,
                        service_slug = ?,
                        service_zone_slug = ?,
                        project_setting = ?,
                        city = ?,
                        state = ?,
                        zip_code = ?,
                        description = ?,
                        desired_date = ?,
                        budget_min = ?,
                        budget_max = ?,
                        approx_lat = ?,
                        approx_lng = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        form["title"],
                        form["category"],
                        form["service_group_slug"],
                        form["service_slug"],
                        service_zone_slug,
                        form["project_setting"],
                        form["city"],
                        form["state"],
                        form["zip_code"],
                        form["description"],
                        form["desired_date"],
                        budget_database_value(form["budget_min"]),
                        budget_database_value(form["budget_max"]),
                        lat,
                        lng,
                        now_iso(),
                        job_id,
                    ),
                )
                replace_job_scope_answers(
                    db,
                    job_id,
                    form["service_slug"],
                    form.get("scope_answers", {}),
                )
                if g.user["role"] == "client":
                    record_service_policy_acknowledgement(
                        db,
                        user_id=g.user["id"],
                        actor_role="client",
                        context="project-post",
                        service_slug=form["service_slug"],
                        acknowledgement_version=form[
                            "service_policy_acknowledgement"
                        ],
                        job_id=job_id,
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
        credential_filter = normalize_credential_filter(
            request.args.get("credentials")
        )
        db = get_db()
        photos = db.execute(
            "SELECT * FROM job_photos WHERE job_id = ? ORDER BY created_at",
            (job_id,),
        ).fetchall()
        requests = db.execute(
            """
            SELECT match_requests.*, users.display_name, users.company_name,
                   contractor_profiles.business_name, contractor_profiles.trades,
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
            "verified": sum(1 for item in all_requests if item["verified_at"]),
        }
        bidding = bid_window(job, len(all_requests))
        invitation = repeat_invitation_for_job(job_id)
        reviews_by_request = match_reviews_by_request(
            [int(item["id"]) for item in all_requests]
        )
        scope_answers = scope_answer_projection(
            job["service_slug"], load_job_scope_answers(job_id)
        )
        comparison = bid_comparison(
            all_requests,
            bid_view,
            credential_filter,
            job_id,
        )
        comparison["credential_filter_options"] = bid_credential_filter_links(
            job_id,
            bid_view,
            comparison["credential_filter_options"],
        )
        return render_template(
            "client_job_detail.html",
            job=job,
            photos=photos,
            requests=requests,
            approved_request=next(
                (item for item in all_requests if item["status"] == "approved"),
                None,
            ),
            request_stats=request_stats,
            bid_comparison=comparison,
            bid_window=bidding,
            bid_view=bid_view,
            bid_view_links=bid_view_links(job_id, credential_filter),
            repeat_invitation=(
                repeat_invitation_response(invitation) if invitation else None
            ),
            reviews_by_request=reviews_by_request,
            scope_answers=scope_answers,
            brief_readiness=project_brief_readiness(
                job,
                scope_answer_count=len(scope_answers),
                photo_count=len(photos),
            ),
            review_dimensions=REVIEW_DIMENSIONS,
            review_rating_options=REVIEW_RATING_OPTIONS,
            would_work_again_options=WOULD_WORK_AGAIN_OPTIONS,
            review_comment_max=REVIEW_COMMENT_MAX_LENGTH,
            review_response_max=REVIEW_RESPONSE_MAX_LENGTH,
            review_report_max=REVIEW_REPORT_MAX_LENGTH,
        )

    @app.route("/client/jobs/<int:job_id>/extend-bids", methods=("POST",))
    @role_required("client")
    def extend_job_bids(job_id: int):
        job = fetch_job(job_id)
        if not job:
            abort(404)
        if job["client_id"] != g.user["id"]:
            abort(403)
        if job["status"] != "open":
            flash("Only open projects can extend bidding.", "error")
            return redirect(url_for("client_job_detail", job_id=job_id))
        db = get_db()
        request_count = db.execute(
            "SELECT COUNT(*) AS total FROM match_requests WHERE job_id = ?",
            (job_id,),
        ).fetchone()["total"]
        bidding = bid_window(job, request_count)
        if bidding["is_full"]:
            flash("This project has received its full set of mini bids.", "error")
            return redirect(url_for("client_job_detail", job_id=job_id))
        if not bidding["is_expired"]:
            flash("Bidding is still open for this project.", "error")
            return redirect(url_for("client_job_detail", job_id=job_id))
        extended_at = extended_bidding_closes_at(job["bidding_closes_at"])
        updated_at = now_iso()
        changed = db.execute(
            """
            UPDATE jobs
            SET bidding_closes_at = ?, updated_at = ?
            WHERE id = ?
              AND client_id = ?
              AND status = 'open'
              AND (SELECT COUNT(*) FROM match_requests WHERE job_id = jobs.id) < bid_limit
            """,
            (extended_at, updated_at, job_id, g.user["id"]),
        )
        if changed.rowcount != 1:
            db.rollback()
            flash("The bid window could not be extended.", "error")
            return redirect(url_for("client_job_detail", job_id=job_id))
        record_automation_event(
            db,
            "job-bidding-extended",
            target_type="job",
            target_id=job_id,
            payload={"client_id": g.user["id"], "bidding_closes_at": extended_at},
        )
        db.commit()
        flash("Bidding extended by 7 days.", "success")
        return redirect(url_for("client_job_detail", job_id=job_id))

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
        db = get_db()
        if action == "reopen":
            completion_started = db.execute(
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
                (job_id,),
            ).fetchone()
            if completion_started:
                flash(
                    "A project with completion confirmation cannot be reopened.",
                    "error",
                )
                return redirect(url_for("client_job_detail", job_id=job_id))
        close_outcome = None
        if action == "close":
            has_approved_match = bool(
                db.execute(
                    """
                    SELECT 1 FROM match_requests
                    WHERE job_id = ? AND status = 'approved'
                    LIMIT 1
                    """,
                    (job_id,),
                ).fetchone()
            )
            try:
                close_outcome = validate_project_close_payload(
                    request.form,
                    has_approved_match=has_approved_match,
                )
            except JobOutcomeError as exc:
                flash(str(exc), "error")
                return redirect(url_for("client_job_detail", job_id=job_id) + "#job-controls")
        status = "closed" if action == "close" else "open"
        bidding_closes_at = job["bidding_closes_at"]
        if action == "reopen":
            request_count = db.execute(
                "SELECT COUNT(*) AS total FROM match_requests WHERE job_id = ?",
                (job_id,),
            ).fetchone()["total"]
            reopened_window = bid_window(
                {**dict(job), "status": "open"},
                request_count,
            )
            if reopened_window["is_expired"] and not reopened_window["is_full"]:
                bidding_closes_at = extended_bidding_closes_at(bidding_closes_at)
        timestamp = now_iso()
        db.execute(
            """
            UPDATE jobs
            SET status = ?,
                bidding_closes_at = ?,
                close_reason = ?,
                close_note = ?,
                closed_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                bidding_closes_at,
                close_outcome["reason_code"] if close_outcome else None,
                close_outcome["note"] if close_outcome else "",
                timestamp if close_outcome else None,
                timestamp,
                job_id,
            ),
        )
        if status == "closed":
            db.execute(
                """
                UPDATE repeat_provider_invitations
                SET status = 'withdrawn', responded_at = ?, updated_at = ?
                WHERE job_id = ? AND status = 'pending'
                """,
                (timestamp, timestamp, job_id),
            )
        record_automation_event(
            db,
            "job-closed" if status == "closed" else "job-reopened",
            target_type="job",
            target_id=job_id,
            payload={
                "action": action,
                "client_id": g.user["id"],
                "previous_status": job["status"],
                "status": status,
                **(
                    {"reason_code": close_outcome["reason_code"]}
                    if close_outcome
                    else {}
                ),
            },
        )
        db.commit()
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
        if match["status"] != "pending":
            if match["status"] != status:
                abort(409)
            if status == "approved":
                thread_id = ensure_thread_for_match(match)
                db.commit()
                flash("Match was already approved. The private message thread is open.", "success")
                return redirect(url_for("thread_detail", thread_id=thread_id))
            flash("Request was already rejected.", "success")
            return redirect(url_for("client_job_detail", job_id=match["job_id"]))
        updated = db.execute(
            """
            UPDATE match_requests
            SET status = ?, updated_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (status, now_iso(), request_id),
        )
        if updated.rowcount != 1:
            db.rollback()
            abort(409)
        if status == "approved":
            thread_id = ensure_thread_for_match(match)
            flash("Match approved. A private message thread is open.", "success")
            db.commit()
            return redirect(url_for("thread_detail", thread_id=thread_id))
        db.commit()
        flash("Request rejected.", "success")
        return redirect(url_for("client_job_detail", job_id=match["job_id"]))

    @app.route("/matches/<int:request_id>/complete", methods=("POST",))
    @role_required("client", "contractor")
    def confirm_match_completion(request_id: int):
        db = get_db()
        match = db.execute(
            """
            SELECT match_requests.id, match_requests.contractor_id,
                   match_requests.status AS match_status,
                   jobs.id AS job_id, jobs.client_id,
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
            """,
            (request_id,),
        ).fetchone()
        try:
            role = validate_completion_confirmation(g.user, match)
        except MatchCompletionError as exc:
            abort(exc.status, str(exc))

        timestamp = now_iso()
        db.execute(
            """
            INSERT OR IGNORE INTO match_completions
                (match_request_id, client_confirmed_at, contractor_confirmed_at,
                 verified_at, created_at, updated_at)
            VALUES (?, NULL, NULL, NULL, ?, ?)
            """,
            (request_id, timestamp, timestamp),
        )
        if role == "client":
            confirmation = db.execute(
                """
                UPDATE match_completions
                SET client_confirmed_at = ?, updated_at = ?
                WHERE match_request_id = ? AND client_confirmed_at IS NULL
                """,
                (timestamp, timestamp, request_id),
            )
        else:
            confirmation = db.execute(
                """
                UPDATE match_completions
                SET contractor_confirmed_at = ?, updated_at = ?
                WHERE match_request_id = ? AND contractor_confirmed_at IS NULL
                """,
                (timestamp, timestamp, request_id),
            )
        completion = db.execute(
            "SELECT * FROM match_completions WHERE match_request_id = ?",
            (request_id,),
        ).fetchone()
        verified_now = bool(
            completion["client_confirmed_at"]
            and completion["contractor_confirmed_at"]
        )
        if verified_now and not completion["verified_at"]:
            db.execute(
                """
                UPDATE match_completions
                SET verified_at = ?, updated_at = ?
                WHERE match_request_id = ? AND verified_at IS NULL
                """,
                (timestamp, timestamp, request_id),
            )
        if confirmation.rowcount == 1:
            record_automation_event(
                db,
                "match-completion-confirmed",
                target_type="match_request",
                target_id=request_id,
                payload={"participant_role": role, "verified": verified_now},
            )
        db.commit()
        flash(
            "Work completion verified by both participants."
            if verified_now
            else "Completion confirmed. Waiting for the other participant.",
            "success",
        )
        if role == "client":
            return redirect(url_for("client_job_detail", job_id=match["job_id"]))
        return redirect(url_for("contractor_dashboard") + "#completed-work")

    @app.route("/matches/<int:request_id>/review", methods=("POST",))
    @role_required("client", "contractor")
    def create_match_review(request_id: int):
        db = get_db()
        match = match_for_review(request_id)
        existing = db.execute(
            """
            SELECT id FROM match_reviews
            WHERE match_request_id = ? AND reviewer_id = ?
            LIMIT 1
            """,
            (request_id, g.user["id"]),
        ).fetchone()
        try:
            role = validate_review_eligibility(g.user, match, existing)
            values = validate_review_payload(request.form)
        except MatchReviewError as exc:
            flash(str(exc), "error")
            return redirect(review_return_url(match, role=g.user["role"]))
        timestamp = now_iso()
        try:
            db.execute(
                """
                INSERT INTO match_reviews
                    (match_request_id, reviewer_id, subject_id, reviewer_role,
                     communication, scope_accuracy, timeliness, work_outcome,
                     would_work_again, comment, response, response_at,
                     is_hidden, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', NULL, 0, ?, ?)
                """,
                (
                    request_id,
                    g.user["id"],
                    review_subject_id(role, match),
                    role,
                    values["communication"],
                    values["scope_accuracy"],
                    values["timeliness"],
                    values["work_outcome"],
                    values["would_work_again"],
                    values["comment"],
                    timestamp,
                    timestamp,
                ),
            )
        except sqlite3.IntegrityError:
            db.rollback()
            abort(409)
        review_id = int(db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
        record_automation_event(
            db,
            "match-review-created",
            target_type="match_review",
            target_id=review_id,
            payload={
                "match_request_id": request_id,
                "reviewer_role": role,
                "dimension_codes": {
                    key: values[key] for key, _label in REVIEW_DIMENSIONS
                },
                "would_work_again": values["would_work_again"],
                "has_comment": bool(values["comment"]),
            },
        )
        db.commit()
        flash("Completed-work feedback recorded.", "success")
        return redirect(review_return_url(match, role=role))

    @app.route("/reviews/<int:review_id>/response", methods=("POST",))
    @role_required("client", "contractor")
    def respond_match_review(review_id: int):
        db = get_db()
        review = match_review_for_id(review_id)
        try:
            response = validate_review_response(
                g.user, review, request.form.get("response")
            )
        except MatchReviewError as exc:
            flash(str(exc), "error")
            return redirect(review_return_url(review, role=g.user["role"]))
        timestamp = now_iso()
        changed = db.execute(
            """
            UPDATE match_reviews
            SET response = ?, response_at = ?, updated_at = ?
            WHERE id = ? AND subject_id = ? AND response = '' AND is_hidden = 0
            """,
            (response, timestamp, timestamp, review_id, g.user["id"]),
        )
        if changed.rowcount != 1:
            db.rollback()
            abort(409)
        record_automation_event(
            db,
            "match-review-response-created",
            target_type="match_review",
            target_id=review_id,
            payload={"responder_role": g.user["role"], "has_response": True},
        )
        db.commit()
        flash("Feedback response recorded.", "success")
        return redirect(review_return_url(review, role=g.user["role"]))

    @app.route("/reviews/<int:review_id>/report", methods=("POST",))
    @role_required("client", "contractor")
    def report_match_review(review_id: int):
        db = get_db()
        review = match_review_for_id(review_id)
        try:
            reason = validate_review_report(
                g.user, review, request.form.get("reason")
            )
        except MatchReviewError as exc:
            flash(str(exc), "error")
            return redirect(review_return_url(review, role=g.user["role"]))
        timestamp = now_iso()
        try:
            db.execute(
                """
                INSERT INTO match_review_reports
                    (review_id, reporter_id, reason, status, created_at, resolved_at)
                VALUES (?, ?, ?, 'open', ?, NULL)
                """,
                (review_id, g.user["id"], reason, timestamp),
            )
        except sqlite3.IntegrityError:
            db.rollback()
            flash("You already reported this feedback.", "error")
            return redirect(review_return_url(review, role=g.user["role"]))
        record_automation_event(
            db,
            "match-review-reported",
            target_type="match_review",
            target_id=review_id,
            payload={"reporter_role": g.user["role"]},
        )
        db.commit()
        flash("Feedback sent to moderation.", "success")
        return redirect(review_return_url(review, role=g.user["role"]))

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
                   jobs.description, jobs.desired_date, jobs.status AS job_status,
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
            ORDER BY match_requests.created_at DESC
            """,
            (g.user["id"],),
        ).fetchall()
        all_requests = requests
        requests = filter_bids_by_view(all_requests, bid_view)
        completed_work = [
            item
            for item in all_requests
            if item["status"] == "approved"
            and item["job_status"] == "closed"
            and item["close_reason"] == "workdoe-match"
        ]
        stats = {
            "visible_requests": len(requests),
            "total_requests": len(all_requests),
            "pending_requests": sum(1 for item in all_requests if item["status"] == "pending"),
            "approved_requests": sum(1 for item in all_requests if item["status"] == "approved"),
            "rejected_requests": sum(1 for item in all_requests if item["status"] == "rejected"),
            "verified_completions": sum(1 for item in all_requests if item["verified_at"]),
        }
        public_credentials = public_credential_responses(
            contractor_credentials_for_user(g.user["id"])
        )
        reputation = contractor_reputation(
            stats["verified_completions"],
            len(public_credentials),
            sum(
                1
                for credential in public_credentials
                if credential["credential_type"] == "trade_license"
            ),
        )
        reviews_by_request = match_reviews_by_request(
            [int(item["id"]) for item in all_requests]
        )
        return render_template(
            "contractor_dashboard.html",
            profile=profile,
            requests=requests,
            completed_work=completed_work,
            repeat_invitations=contractor_repeat_invitations(g.user["id"]),
            stats=stats,
            reputation=reputation,
            bid_view=bid_view,
            bid_view_links=contractor_bid_view_links(),
            reviews_by_request=reviews_by_request,
            review_dimensions=REVIEW_DIMENSIONS,
            review_rating_options=REVIEW_RATING_OPTIONS,
            would_work_again_options=WOULD_WORK_AGAIN_OPTIONS,
            review_comment_max=REVIEW_COMMENT_MAX_LENGTH,
            review_response_max=REVIEW_RESPONSE_MAX_LENGTH,
            review_report_max=REVIEW_REPORT_MAX_LENGTH,
            proposal_templates=[
                proposal_template_response(item)
                for item in contractor_proposal_templates(g.user["id"])
            ],
            proposal_template_limit=PROPOSAL_TEMPLATE_LIMIT,
        )

    @app.route("/contractor/proposal-templates", methods=("POST",))
    @role_required("contractor")
    def add_contractor_proposal_template():
        try:
            template_form = proposal_template_request_payload(request.form)
        except ProposalTemplateError as exc:
            flash(" ".join(exc.errors), "error")
            return redirect(url_for("contractor_dashboard") + "#proposal-templates")
        db = get_db()
        source_bid = db.execute(
            """
            SELECT * FROM match_requests
            WHERE id = ? AND contractor_id = ?
            LIMIT 1
            """,
            (template_form["source_match_request_id"], g.user["id"]),
        ).fetchone()
        if not source_bid:
            abort(404)
        count = db.execute(
            """
            SELECT COUNT(*) AS count FROM contractor_proposal_templates
            WHERE contractor_id = ?
            """,
            (g.user["id"],),
        ).fetchone()["count"]
        if count >= PROPOSAL_TEMPLATE_LIMIT:
            flash(
                f"Keep up to {PROPOSAL_TEMPLATE_LIMIT} proposal templates.",
                "error",
            )
            return redirect(
                url_for("contractor_job_detail", job_id=source_bid["job_id"])
                + "#mini-bid"
            )
        values = proposal_template_values(template_form["name"], source_bid)
        timestamp = now_iso()
        try:
            created = db.execute(
                """
                INSERT INTO contractor_proposal_templates
                    (contractor_id, name, source_match_request_id, scope_note,
                     timeline, experience, questions, availability,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    g.user["id"],
                    values["name"],
                    values["source_match_request_id"],
                    values["scope_note"],
                    values["timeline"],
                    values["experience"],
                    values["questions"],
                    values["availability"],
                    timestamp,
                    timestamp,
                ),
            )
        except sqlite3.IntegrityError:
            db.rollback()
            flash("Use a different name for this proposal template.", "error")
            return redirect(
                url_for("contractor_job_detail", job_id=source_bid["job_id"])
                + "#mini-bid"
            )
        record_automation_event(
            db,
            "contractor-proposal-template-created",
            target_type="contractor_proposal_template",
            target_id=created.lastrowid,
            payload={
                "contractor_id": g.user["id"],
                "source_match_request_id": source_bid["id"],
            },
        )
        db.commit()
        flash("Proposal template saved. Prices always start blank.", "success")
        return redirect(
            url_for("contractor_job_detail", job_id=source_bid["job_id"])
            + "#mini-bid"
        )

    @app.route(
        "/contractor/proposal-templates/<int:template_id>/delete",
        methods=("POST",),
    )
    @role_required("contractor")
    def delete_contractor_proposal_template(template_id: int):
        db = get_db()
        deleted = db.execute(
            """
            DELETE FROM contractor_proposal_templates
            WHERE id = ? AND contractor_id = ?
            """,
            (template_id, g.user["id"]),
        )
        if deleted.rowcount != 1:
            db.rollback()
            abort(404)
        record_automation_event(
            db,
            "contractor-proposal-template-deleted",
            target_type="contractor_proposal_template",
            target_id=template_id,
            payload={"contractor_id": g.user["id"]},
        )
        db.commit()
        flash("Proposal template removed.", "success")
        return redirect(url_for("contractor_dashboard") + "#proposal-templates")

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
        credentials = contractor_credentials_for_user(g.user["id"])
        preferences = contractor_preferences_for_user(g.user["id"])
        if request.method == "POST":
            form = cleaned_contractor_profile_form(request.form)
            errors = validate_contractor_profile_form(form)
            if errors:
                return render_contractor_profile_form(
                    form, photos, credentials, preferences, errors=errors
                )

            form["website"] = normalized_profile_website(form["website"])

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
                    "",
                    now_iso(),
                    g.user["id"],
                ),
            )
            replace_contractor_market_fit(
                g.user["id"],
                form["service_slugs"],
                form["service_zone_slugs"],
            )
            save_contractor_photos(g.user["id"], request.files.getlist("portfolio_photos"))
            db.commit()
            flash("Contractor profile updated.", "success")
            return redirect(url_for("contractor_profile"))

        market_fit = contractor_market_fit(g.user["id"], profile)
        return render_contractor_profile_form(
            contractor_profile_to_form(profile, market_fit),
            photos,
            credentials,
            preferences,
        )

    @app.route("/contractor/preferences/availability", methods=("POST",))
    @role_required("contractor")
    def contractor_availability_update():
        try:
            availability = availability_payload(request.form.to_dict())
        except ContractorPreferenceError as exc:
            flash(" ".join(exc.errors), "error")
            return redirect(url_for("contractor_profile") + "#work-availability")
        timestamp = now_iso()
        get_db().execute(
            """
            INSERT INTO contractor_lead_preferences
                (contractor_id, availability_status, available_from, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(contractor_id) DO UPDATE SET
                availability_status = excluded.availability_status,
                available_from = excluded.available_from,
                updated_at = excluded.updated_at
            """,
            (
                g.user["id"],
                availability["availability_status"],
                availability["available_from"] or None,
                timestamp,
            ),
        )
        get_db().commit()
        flash("Work availability updated.", "success")
        return redirect(url_for("contractor_profile") + "#work-availability")

    @app.route("/contractor/preferences/lead-view", methods=("POST",))
    @role_required("contractor")
    def contractor_saved_lead_view_update():
        try:
            saved_view = saved_lead_view_payload(
                request.form.to_dict(),
                categories=JOB_CATEGORIES,
                sorts={value for value, _label in JOB_SORT_OPTIONS},
                families=GROUP_BY_SLUG,
            )
        except ContractorPreferenceError as exc:
            flash(" ".join(exc.errors), "error")
            return redirect(url_for("leads"))
        timestamp = now_iso()
        alert_consent_at = (
            timestamp if saved_view["lead_alert_preference"] == "email" else None
        )
        db = get_db()
        db.execute(
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
            (
                g.user["id"],
                saved_view["saved_query"],
                saved_view["saved_category"],
                saved_view["saved_service_group_slug"],
                saved_view["saved_service_slug"],
                saved_view["saved_sort"],
                timestamp,
                saved_view["lead_alert_preference"],
                alert_consent_at,
                timestamp,
            ),
        )
        record_automation_event(
            db,
            "contractor-lead-view-saved",
            target_type="user",
            target_id=g.user["id"],
            payload={
                "fields": sorted(saved_view),
                "lead_alert_enabled": saved_view["lead_alert_preference"] == "email",
            },
        )
        db.commit()
        flash("Lead view saved.", "success")
        args = {
            key: value
            for key, value in {
                "category": saved_view["saved_category"],
                "family": saved_view["saved_service_group_slug"],
                "service": saved_view["saved_service_slug"],
                "q": saved_view["saved_query"],
                "sort": saved_view["saved_sort"],
            }.items()
            if value and not (key == "sort" and value == DEFAULT_JOB_SORT)
        }
        return redirect(url_for("leads", **args))

    @app.route("/contractor/credentials", methods=("POST",))
    @role_required("contractor")
    def contractor_credential_create():
        try:
            claim = contractor_credential_claim_payload(request.form.to_dict())
        except ContractorCredentialError as exc:
            flash(" ".join(exc.errors), "error")
            return redirect(url_for("contractor_profile") + "#credential-claims")
        timestamp = now_iso()
        try:
            get_db().execute(
                """
                INSERT INTO contractor_credentials
                    (contractor_id, credential_type, jurisdiction,
                     claimed_identifier, claimed_name, status, source_url,
                     checked_at, expires_at, reviewed_by, review_note,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'self_reported', ?, NULL, ?, NULL, '', ?, ?)
                """,
                (
                    g.user["id"],
                    claim["credential_type"],
                    claim["jurisdiction"],
                    claim["claimed_identifier"],
                    claim["claimed_name"],
                    claim["source_url"],
                    claim["expires_at"] or None,
                    timestamp,
                    timestamp,
                ),
            )
        except sqlite3.IntegrityError:
            flash("That credential claim is already on your profile.", "error")
            return redirect(url_for("contractor_profile") + "#credential-claims")
        get_db().commit()
        flash("Credential claim sent for review.", "success")
        return redirect(url_for("contractor_profile") + "#credential-claims")

    @app.route("/contractor/credentials/<int:credential_id>/remove", methods=("POST",))
    @role_required("contractor")
    def contractor_credential_remove(credential_id: int):
        credential = get_db().execute(
            """
            SELECT id, status FROM contractor_credentials
            WHERE id = ? AND contractor_id = ?
            """,
            (credential_id, g.user["id"]),
        ).fetchone()
        if not credential:
            abort(404)
        if credential["status"] not in {"self_reported", "pending", "rejected"}:
            abort(409)
        get_db().execute(
            "DELETE FROM contractor_credentials WHERE id = ? AND contractor_id = ?",
            (credential_id, g.user["id"]),
        )
        get_db().commit()
        flash("Credential claim removed.", "success")
        return redirect(url_for("contractor_profile") + "#credential-claims")

    @app.route("/contractors/<int:contractor_id>")
    def contractor_public_profile(contractor_id: int):
        db = get_db()
        contractor = db.execute(
            """
            SELECT users.id, users.display_name, users.company_name, users.status,
                   contractor_profiles.*,
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
        market_fit = contractor_market_fit(contractor_id, contractor)
        services = [SERVICE_BY_SLUG[slug] for slug in market_fit["service_slugs"]]
        zones = [ZONE_BY_SLUG[slug] for slug in market_fit["service_zone_slugs"]]
        website_visible = can_view_contractor_website(g.user, contractor_id, db)
        credentials = public_credential_responses(
            contractor_credentials_for_user(contractor_id)
        )
        reputation = contractor_reputation(
            contractor["verified_completions"],
            len(credentials),
            sum(
                1
                for credential in credentials
                if credential["credential_type"] == "trade_license"
            ),
        )
        availability = contractor_preferences_response(
            contractor_preferences_for_user(contractor_id)
        )["availability"]
        public_website = (
            normalized_profile_website(contractor["website"])
            if website_visible
            else ""
        )
        completed_work_reviews = (
            visible_contractor_reviews(contractor_id) if website_visible else []
        )
        relationship = None
        requested_job_id = request.args.get("job_id", type=int)
        if requested_job_id and g.user and g.user["role"] == "client":
            relationship = db.execute(
                """
                SELECT jobs.id AS job_id,
                       jobs.title AS job_title,
                       jobs.client_id,
                       match_requests.contractor_id,
                       match_requests.id AS request_id,
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
                (requested_job_id, g.user["id"], contractor_id),
            ).fetchone()
        choice_context = contractor_choice_context(
            g.user,
            contractor_id,
            relationship,
        )
        return render_template(
            "contractor_public.html",
            contractor=contractor,
            photos=photos,
            services=services,
            service_zones=zones,
            public_website=public_website,
            website_label=profile_website_label(public_website),
            credentials=credentials,
            reputation=reputation,
            availability=availability,
            completed_work_reviews=completed_work_reviews,
            choice_context=choice_context,
            review_dimensions=REVIEW_DIMENSIONS,
            review_response_max=REVIEW_RESPONSE_MAX_LENGTH,
            review_report_max=REVIEW_REPORT_MAX_LENGTH,
        )

    @app.route("/leads")
    @role_required("contractor")
    def leads():
        filters = public_job_filters()
        selected_family = GROUP_BY_SLUG.get(filters.get("family", ""))
        lead_view = normalize_lead_view(request.args.get("view"))
        jobs, map_jobs = public_open_jobs(limit=LEAD_BOARD_JOB_LIMIT, filters=filters)
        jobs = attach_contractor_request_status(jobs, g.user["id"])
        market_fit = contractor_market_fit(g.user["id"])
        jobs = annotate_job_fits(
            jobs,
            market_fit["service_slugs"],
            market_fit["service_zone_slugs"],
        )
        for job in jobs:
            job["bid_window"] = bid_window(job)
            job["brief_readiness"] = project_brief_readiness(job)
        all_jobs = jobs
        jobs = filter_jobs_by_lead_view(all_jobs, lead_view)
        map_jobs = filter_map_jobs_by_jobs(map_jobs, jobs)
        jobs_by_id = {job["id"]: job for job in jobs}
        for map_job in map_jobs:
            card = jobs_by_id.get(map_job["id"])
            if not card:
                continue
            detail_url = url_for("contractor_job_detail", job_id=card["id"])
            map_job.update(
                {
                    "description": card["description"],
                    "request_status": card["request_status"],
                    "bid_window": card["bid_window"],
                    "brief_readiness": card["brief_readiness"],
                    "fit_score": card["fit_score"],
                    "fit_label": card["fit_label"],
                    "row_cue": "Sent" if card["request_status"] else "View",
                    "action_label": (
                        "View bid status"
                        if card["request_status"]
                        else "Review and bid"
                    ),
                    "url": detail_url,
                    "detail_url": detail_url,
                }
            )
        requested_job_id = request.args.get("job_id", type=int)
        selected_job = next(
            (job for job in jobs if job["id"] == requested_job_id),
            jobs[0] if jobs else None,
        )
        stats = {
            "visible_jobs": len(jobs),
            "all_jobs": len(all_jobs),
            "new_jobs": sum(1 for job in all_jobs if not job["request_status"]),
            "sent_bids": sum(1 for job in all_jobs if job["request_status"]),
        }
        has_query_filters = public_filters_active(filters)
        preferences_row = contractor_preferences_for_user(g.user["id"])
        preferences = contractor_preferences_response(preferences_row)
        return render_template(
            "leads.html",
            jobs=jobs,
            filters=filters,
            selected_family=selected_family,
            selected_job=selected_job,
            map_jobs=map_jobs,
            map_jobs_api_url=map_jobs_api_url(
                filters,
                limit=LEAD_BOARD_JOB_LIMIT,
                view=lead_view,
            ),
            has_filters=has_query_filters or lead_view != "all",
            has_query_filters=has_query_filters,
            lead_view=lead_view,
            lead_view_links=lead_view_links(filters),
            family_filter_links=service_family_filter_links(
                "leads",
                filters,
                base_args={"view": lead_view if lead_view != "all" else ""},
                anchor="lead-results",
            ),
            stats=stats,
            preferences=preferences,
            saved_lead_view_url=saved_lead_view_url(preferences_row),
            lead_alert_options=LEAD_ALERT_OPTIONS,
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
        lead_feedback = None
        repeat_invitation = None
        proposal_templates = []
        selected_proposal_template = None
        if g.user["role"] == "contractor":
            existing_request = db.execute(
                """
                SELECT * FROM match_requests
                WHERE job_id = ? AND contractor_id = ?
                """,
                (job_id, g.user["id"]),
            ).fetchone()
            lead_feedback = db.execute(
                """
                SELECT reason_code, note, updated_at
                FROM job_lead_feedback
                WHERE job_id = ? AND contractor_id = ?
                LIMIT 1
                """,
                (job_id, g.user["id"]),
            ).fetchone()
            invitation_row = db.execute(
                """
                SELECT repeat_provider_invitations.*,
                       jobs.title AS project_title,
                       jobs.city,
                       jobs.state,
                       jobs.desired_date,
                       jobs.status AS job_status
                FROM repeat_provider_invitations
                JOIN jobs ON jobs.id = repeat_provider_invitations.job_id
                WHERE repeat_provider_invitations.job_id = ?
                  AND repeat_provider_invitations.contractor_id = ?
                LIMIT 1
                """,
                (job_id, g.user["id"]),
            ).fetchone()
            if invitation_row:
                repeat_invitation = repeat_invitation_response(invitation_row)
            proposal_templates = contractor_proposal_templates(g.user["id"])
            selected_template_id = parse_positive_int(
                request.args.get("proposal_template")
            )
            if selected_template_id and not existing_request:
                selected_proposal_template = db.execute(
                    """
                    SELECT * FROM contractor_proposal_templates
                    WHERE id = ? AND contractor_id = ?
                    LIMIT 1
                    """,
                    (selected_template_id, g.user["id"]),
                ).fetchone()
                if not selected_proposal_template:
                    abort(404)
            if service_activation_required() and not existing_request:
                activation = service_activation_record(
                    job["service_slug"], job["service_zone_slug"]
                )
                if not activation_is_live(activation):
                    abort(404)
        request_count = db.execute(
            "SELECT COUNT(*) AS total FROM match_requests WHERE job_id = ?",
            (job_id,),
        ).fetchone()["total"]
        bidding = bid_window(job, request_count)
        scope_answers = scope_answer_projection(
            job["service_slug"], load_job_scope_answers(job_id)
        )
        return render_template(
            "contractor_job_detail.html",
            job=job,
            photos=photos,
            existing_request=existing_request,
            lead_feedback=lead_feedback,
            bid_window=bidding,
            bid_form=(
                proposal_template_bid_form(selected_proposal_template)
                if selected_proposal_template
                else blank_bid_form()
            ),
            bid_limits=bid_limits(),
            bid_error_feedback=bid_error_feedback([]),
            repeat_invitation=repeat_invitation,
            scope_answers=scope_answers,
            brief_readiness=project_brief_readiness(
                job,
                scope_answer_count=len(scope_answers),
                photo_count=len(photos),
            ),
            proposal_templates=[
                proposal_template_response(item) for item in proposal_templates
            ],
            selected_proposal_template=(
                proposal_template_response(selected_proposal_template)
                if selected_proposal_template
                else None
            ),
            proposal_template_limit=PROPOSAL_TEMPLATE_LIMIT,
            proposal_template_name_max=PROPOSAL_TEMPLATE_NAME_MAX_LENGTH,
        )

    @app.route(
        "/repeat-invitations/<int:invitation_id>/<action>", methods=("POST",)
    )
    @role_required("client", "contractor")
    def respond_repeat_invitation(invitation_id: int, action: str):
        db = get_db()
        invitation = db.execute(
            "SELECT * FROM repeat_provider_invitations WHERE id = ?",
            (invitation_id,),
        ).fetchone()
        try:
            validate_invitation_action(g.user, invitation, action)
        except RepeatProviderInvitationError as exc:
            abort(exc.status, str(exc))
        next_status = "declined" if action == "decline" else "withdrawn"
        timestamp = now_iso()
        changed = db.execute(
            """
            UPDATE repeat_provider_invitations
            SET status = ?, responded_at = ?, updated_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (next_status, timestamp, timestamp, invitation_id),
        )
        if changed.rowcount != 1:
            db.rollback()
            abort(409)
        record_automation_event(
            db,
            f"repeat-provider-invitation-{next_status}",
            target_type="job",
            target_id=invitation["job_id"],
            payload={
                "invitation_id": invitation_id,
                "contractor_id": invitation["contractor_id"],
            },
        )
        db.commit()
        flash(
            "Invitation declined. The consumer can still review other mini bids."
            if action == "decline"
            else "Repeat invitation withdrawn. The project remains open to ordinary bids.",
            "success",
        )
        if action == "decline":
            return redirect(url_for("contractor_dashboard") + "#repeat-invitations")
        return redirect(url_for("client_job_detail", job_id=invitation["job_id"]))

    @app.route("/jobs/<int:job_id>/quality-feedback", methods=("POST",))
    @role_required("contractor")
    def submit_job_quality_feedback(job_id: int):
        db = get_db()
        job = fetch_job(job_id)
        existing_request = db.execute(
            """
            SELECT id FROM match_requests
            WHERE job_id = ? AND contractor_id = ?
            LIMIT 1
            """,
            (job_id, g.user["id"]),
        ).fetchone()
        if not job or job["status"] == "hidden" or not existing_request:
            abort(403)
        try:
            feedback = validate_lead_quality_payload(request.form)
        except JobOutcomeError as exc:
            flash(str(exc), "error")
            return redirect(url_for("contractor_job_detail", job_id=job_id) + "#lead-quality")
        timestamp = now_iso()
        db.execute(
            """
            INSERT INTO job_lead_feedback
                (job_id, contractor_id, reason_code, note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id, contractor_id) DO UPDATE SET
                reason_code = excluded.reason_code,
                note = excluded.note,
                updated_at = excluded.updated_at
            """,
            (
                job_id,
                g.user["id"],
                feedback["reason_code"],
                feedback["note"],
                timestamp,
                timestamp,
            ),
        )
        record_automation_event(
            db,
            "lead-quality-feedback-recorded",
            target_type="job",
            target_id=job_id,
            payload={
                "contractor_id": g.user["id"],
                "reason_code": feedback["reason_code"],
            },
        )
        db.commit()
        flash("Lead feedback saved for marketplace quality review.", "success")
        return redirect(url_for("contractor_job_detail", job_id=job_id) + "#lead-quality")

    @app.route("/jobs/<int:job_id>/request", methods=("POST",))
    @role_required("contractor")
    def request_match(job_id: int):
        job = fetch_job(job_id)
        if not job or job["status"] != "open":
            abort(404)
        db = get_db()
        if service_activation_required():
            activation = service_activation_record(
                job["service_slug"], job["service_zone_slug"]
            )
            if not activation_is_live(activation):
                flash(ACTIVATION_NOT_OPEN_MESSAGE, "error")
                return redirect(url_for("leads"))
        existing = db.execute(
            "SELECT id FROM match_requests WHERE job_id = ? AND contractor_id = ?",
            (job_id, g.user["id"]),
        ).fetchone()
        if existing:
            flash("You already requested a match for this job.", "error")
            return redirect(url_for("contractor_job_detail", job_id=job_id))

        bid_form = cleaned_bid_form(request.form)
        errors = validate_bid_form(bid_form)
        policy_error = service_policy_error(
            job["service_slug"],
            bid_form["service_policy_acknowledgement"],
        )
        if policy_error:
            errors.append(policy_error)
        if errors:
            photos = db.execute(
                """
                SELECT * FROM job_photos
                WHERE job_id = ? AND is_hidden = 0
                ORDER BY created_at
                """,
                (job_id,),
            ).fetchall()
            request_count = db.execute(
                "SELECT COUNT(*) AS total FROM match_requests WHERE job_id = ?",
                (job_id,),
            ).fetchone()["total"]
            scope_answers = scope_answer_projection(
                job["service_slug"], load_job_scope_answers(job_id)
            )
            return render_template(
                "contractor_job_detail.html",
                job=job,
                photos=photos,
                existing_request=None,
                bid_window=bid_window(job, request_count),
                bid_form=bid_form,
                bid_limits=bid_limits(),
                bid_error_feedback=bid_error_feedback(errors),
                repeat_invitation=(
                    repeat_invitation_response(repeat_invitation_for_job(job_id))
                    if repeat_invitation_for_job(job_id)
                    else None
                ),
                scope_answers=scope_answers,
                brief_readiness=project_brief_readiness(
                    job,
                    scope_answer_count=len(scope_answers),
                    photo_count=len(photos),
                ),
                proposal_templates=[
                    proposal_template_response(item)
                    for item in contractor_proposal_templates(g.user["id"])
                ],
                selected_proposal_template=None,
                proposal_template_limit=PROPOSAL_TEMPLATE_LIMIT,
                proposal_template_name_max=PROPOSAL_TEMPLATE_NAME_MAX_LENGTH,
            )

        created = db.execute(
            """
            INSERT OR IGNORE INTO match_requests
                (job_id, contractor_id, scope_note, price_range, timeline,
                 experience, questions, availability, status, created_at, updated_at)
            SELECT jobs.id, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?
            FROM jobs
            WHERE jobs.id = ?
              AND jobs.status = 'open'
              AND datetime(jobs.bidding_closes_at) > datetime(?)
              AND (
                SELECT COUNT(*)
                FROM match_requests
                WHERE match_requests.job_id = jobs.id
              ) < jobs.bid_limit
            """,
            (
                g.user["id"],
                bid_form["scope_note"],
                bid_form["price_range"],
                bid_form["timeline"],
                bid_form["experience"],
                bid_form["questions"],
                bid_form["availability"],
                now_iso(),
                now_iso(),
                job_id,
                now_iso(),
            ),
        )
        if created.rowcount != 1:
            duplicate = db.execute(
                "SELECT id FROM match_requests WHERE job_id = ? AND contractor_id = ?",
                (job_id, g.user["id"]),
            ).fetchone()
            if duplicate:
                flash("You already requested a match for this job.", "error")
                return redirect(url_for("contractor_job_detail", job_id=job_id))
            latest = db.execute(
                """
                SELECT jobs.*,
                       (SELECT COUNT(*) FROM match_requests WHERE job_id = jobs.id)
                           AS request_count
                FROM jobs
                WHERE jobs.id = ?
                """,
                (job_id,),
            ).fetchone()
            if not latest or latest["status"] != "open":
                abort(404)
            bidding = bid_window(latest)
            if bidding["is_full"]:
                flash("This project has received its full set of mini bids.", "error")
            elif bidding["is_expired"]:
                flash("Bidding has closed for this project.", "error")
            else:
                flash("This lead is not available for a new mini bid.", "error")
            return redirect(url_for("contractor_job_detail", job_id=job_id))
        match_request_id = int(created.lastrowid)
        record_service_policy_acknowledgement(
            db,
            user_id=g.user["id"],
            actor_role="contractor",
            context="mini-bid",
            service_slug=job["service_slug"],
            acknowledgement_version=bid_form["service_policy_acknowledgement"],
            job_id=job_id,
            match_request_id=match_request_id,
        )
        timestamp = now_iso()
        invitation_changed = db.execute(
            """
            UPDATE repeat_provider_invitations
            SET status = 'bid_sent', responded_at = ?, updated_at = ?
            WHERE job_id = ? AND contractor_id = ? AND status = 'pending'
            """,
            (timestamp, timestamp, job_id, g.user["id"]),
        )
        if invitation_changed.rowcount == 1:
            record_automation_event(
                db,
                "repeat-provider-invitation-bid-sent",
                target_type="job",
                target_id=job_id,
                payload={"contractor_id": g.user["id"]},
            )
        db.commit()
        flash("Mini bid sent. The client can approve it to open messaging.", "success")
        return redirect(url_for("contractor_job_detail", job_id=job_id))

    @app.route("/messages")
    @role_required("client", "contractor")
    def message_threads():
        all_threads = get_db().execute(
            """
            SELECT threads.*, jobs.title, jobs.category, jobs.city, jobs.state,
                   client.display_name AS client_name,
                   contractor.display_name AS contractor_name,
                   (
                       SELECT body FROM messages
                       WHERE messages.thread_id = threads.id AND messages.is_hidden = 0
                       ORDER BY messages.id DESC
                       LIMIT 1
                   ) AS last_message,
                   (
                       SELECT created_at FROM messages
                       WHERE messages.thread_id = threads.id AND messages.is_hidden = 0
                       ORDER BY messages.id DESC
                       LIMIT 1
                   ) AS last_message_at,
                   (
                       SELECT id FROM messages
                       WHERE messages.thread_id = threads.id AND messages.is_hidden = 0
                       ORDER BY messages.id DESC
                       LIMIT 1
                   ) AS last_message_id,
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
            WHERE threads.client_id = ? OR threads.contractor_id = ?
            ORDER BY COALESCE(last_message_at, threads.created_at) DESC,
                     COALESCE(last_message_id, 0) DESC
            """,
            (g.user["id"], g.user["id"], g.user["id"], g.user["id"]),
        ).fetchall()
        thread_view = normalize_message_thread_view(request.args.get("view"))
        stats = {
            "threads": len(all_threads),
            "messages": sum(thread["message_count"] or 0 for thread in all_threads),
            "unread": sum(thread["unread_count"] or 0 for thread in all_threads),
            "unread_threads": sum(
                1 for thread in all_threads if (thread["unread_count"] or 0) > 0
            ),
        }
        threads = (
            [thread for thread in all_threads if (thread["unread_count"] or 0) > 0]
            if thread_view == "unread"
            else all_threads
        )
        return render_template(
            "messages.html",
            threads=threads,
            stats=stats,
            thread_view=thread_view,
            thread_view_links=message_thread_view_links(),
        )

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
        message_errors = []
        if request.method == "POST":
            if is_admin:
                abort(403)
            draft_body = (request.form.get("body") or "").strip()
            if not draft_body:
                message_errors.append("Write a message before sending.")
            elif len(draft_body) > MESSAGE_BODY_MAX_LENGTH:
                message_errors.append(f"Keep messages under {MESSAGE_BODY_MAX_LENGTH} characters.")
            try:
                idempotency_key = request_idempotency_key()
            except IdempotencyError as exc:
                message_errors.append(str(exc))
                idempotency_key = ""
            if not message_errors:
                action = idempotency_action("message-create", thread_id)
                replay_record = begin_idempotent_write(
                    db,
                    g.user["id"],
                    action,
                    "message",
                    idempotency_key,
                )
                replay_message_id = completed_idempotent_resource(
                    replay_record, "message"
                )
                if replay_message_id:
                    db.rollback()
                    flash("Message already sent.", "success")
                    return redirect(url_for("thread_detail", thread_id=thread_id))
                created_at = now_iso()
                result = db.execute(
                    """
                    INSERT INTO messages (thread_id, sender_id, body, is_hidden, created_at)
                    VALUES (?, ?, ?, 0, ?)
                    """,
                    (thread_id, g.user["id"], draft_body, created_at),
                )
                mark_thread_read(
                    db,
                    thread_id,
                    g.user["id"],
                    int(result.lastrowid),
                    created_at,
                )
                complete_idempotent_write(
                    db,
                    g.user["id"],
                    action,
                    "message",
                    idempotency_key,
                    int(result.lastrowid),
                )
                db.commit()
                flash("Message sent.", "success")
                return redirect(url_for("thread_detail", thread_id=thread_id))
        message_query = (
            """
            SELECT messages.*, users.display_name
            FROM messages
            JOIN users ON users.id = messages.sender_id
            WHERE messages.thread_id = ?
            ORDER BY messages.id
            """
            if is_admin
            else """
            SELECT messages.*, users.display_name
            FROM messages
            JOIN users ON users.id = messages.sender_id
            WHERE messages.thread_id = ? AND messages.is_hidden = 0
            ORDER BY messages.id
            """
        )
        messages = db.execute(
            message_query,
            (thread_id,),
        ).fetchall()
        if not is_admin and request.method != "HEAD":
            last_message = messages[-1] if messages else None
            mark_thread_read(
                db,
                thread_id,
                g.user["id"],
                int(last_message["id"]) if last_message else 0,
                last_message["created_at"] if last_message else thread["created_at"],
            )
            db.commit()
            g.unread_message_count = unread_message_count(
                db,
                g.user["id"],
                g.user["role"],
            )
        return render_template(
            "thread_detail.html",
            thread=thread,
            messages=messages,
            draft_body=draft_body,
            message_max=MESSAGE_BODY_MAX_LENGTH,
            message_error_feedback=message_error_feedback(message_errors),
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
        if not report_target_visible_to_user(g.user, target_type, target_id):
            flash("That item is no longer available to report.", "error")
            return redirect(return_url)
        try:
            idempotency_key = request_idempotency_key()
        except IdempotencyError as exc:
            flash(str(exc), "error")
            return redirect(return_url)
        db = get_db()
        action = idempotency_action(f"report-{target_type}", target_id)
        replay_record = begin_idempotent_write(
            db,
            g.user["id"],
            action,
            "report",
            idempotency_key,
        )
        replay_report_id = completed_idempotent_resource(replay_record, "report")
        if replay_report_id:
            db.rollback()
            flash("Report already sent to moderation.", "success")
            return redirect(return_url)
        result = db.execute(
            """
            INSERT INTO reports (reporter_id, target_type, target_id, reason, status, created_at, resolved_at)
            VALUES (?, ?, ?, ?, 'open', ?, NULL)
            """,
            (g.user["id"], target_type, target_id, reason, now_iso()),
        )
        complete_idempotent_write(
            db,
            g.user["id"],
            action,
            "report",
            idempotency_key,
            int(result.lastrowid),
        )
        db.commit()
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
        lead_feedback = db.execute(
            """
            SELECT job_lead_feedback.*, jobs.title AS job_title,
                   users.email AS contractor_email
            FROM job_lead_feedback
            JOIN jobs ON jobs.id = job_lead_feedback.job_id
            JOIN users ON users.id = job_lead_feedback.contractor_id
            ORDER BY job_lead_feedback.updated_at DESC
            LIMIT 20
            """
        ).fetchall()
        close_outcomes = [
            {
                "reason_code": row["close_reason"],
                "label": project_close_reason_label(row["close_reason"]),
                "count": int(row["total"] or 0),
            }
            for row in db.execute(
                """
                SELECT close_reason, COUNT(*) AS total
                FROM jobs
                WHERE status = 'closed' AND close_reason IS NOT NULL
                GROUP BY close_reason
                ORDER BY total DESC, close_reason
                """
            ).fetchall()
        ]
        lead_quality_outcomes = [
            {
                "reason_code": row["reason_code"],
                "label": lead_quality_reason_label(row["reason_code"]),
                "count": int(row["total"] or 0),
            }
            for row in db.execute(
                """
                SELECT reason_code, COUNT(*) AS total
                FROM job_lead_feedback
                GROUP BY reason_code
                ORDER BY total DESC, reason_code
                """
            ).fetchall()
        ]
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
        credentials = db.execute(
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
            """
        ).fetchall()
        recent_match_reviews = db.execute(
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
            """
        ).fetchall()
        review_reports = db.execute(
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
            """
        ).fetchall()
        match_review_row = db.execute(
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
            """
        ).fetchone()
        match_review_metrics = {
            key: int(value or 0) for key, value in dict(match_review_row).items()
        }
        match_review_metrics["open_reports"] = len(review_reports)
        hidden_content_count = db.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM jobs WHERE status = 'hidden') +
                (SELECT COUNT(*) FROM job_photos WHERE is_hidden = 1) +
                (SELECT COUNT(*) FROM contractor_photos WHERE is_hidden = 1) +
                (SELECT COUNT(*) FROM messages WHERE is_hidden = 1) +
                (SELECT COUNT(*) FROM match_reviews WHERE is_hidden = 1) AS total
            """
        ).fetchone()["total"]
        audit_action_count = db.execute(
            "SELECT COUNT(*) AS total FROM moderation_actions"
        ).fetchone()["total"]
        automation_event_count = db.execute(
            "SELECT COUNT(*) AS total FROM automation_events"
        ).fetchone()["total"]
        marketplace_row = db.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM jobs WHERE status != 'hidden')
                    AS published_projects,
                (
                    SELECT COUNT(DISTINCT match_requests.job_id)
                    FROM match_requests
                    JOIN jobs ON jobs.id = match_requests.job_id
                    WHERE jobs.status != 'hidden'
                ) AS projects_with_bids,
                (
                    SELECT COUNT(DISTINCT match_requests.job_id)
                    FROM match_requests
                    JOIN jobs ON jobs.id = match_requests.job_id
                    WHERE jobs.status != 'hidden'
                      AND match_requests.status = 'approved'
                ) AS matched_projects,
                (
                    SELECT COUNT(*) FROM match_requests
                    JOIN jobs ON jobs.id = match_requests.job_id
                    WHERE jobs.status != 'hidden'
                      AND match_requests.status = 'approved'
                ) AS approved_matches,
                (
                    SELECT COUNT(*) FROM match_completions
                    WHERE client_confirmed_at IS NOT NULL
                       OR contractor_confirmed_at IS NOT NULL
                ) AS completion_signals,
                (
                    SELECT COUNT(*) FROM match_completions
                    WHERE verified_at IS NOT NULL
                ) AS verified_completions,
                (
                    SELECT COUNT(*) FROM jobs
                    WHERE status = 'closed'
                ) AS closed_projects,
                (
                    SELECT COUNT(*) FROM jobs
                    WHERE status = 'closed' AND close_reason = 'workdoe-match'
                ) AS workdoe_match_outcomes,
                (
                    SELECT COUNT(*) FROM job_lead_feedback
                ) AS lead_quality_signals
            """
        ).fetchone()
        marketplace_metrics = {
            key: int(value or 0) for key, value in dict(marketplace_row).items()
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
        pilot_project_rows = db.execute(
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
                   SUM(CASE WHEN match_completions.verified_at IS NOT NULL THEN 1 ELSE 0 END)
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
            LEFT JOIN match_completions
              ON match_completions.match_request_id = match_requests.id
            WHERE jobs.status != 'hidden'
              AND lower(project_owners.email) NOT LIKE '%@workdoe.local'
              AND jobs.created_at >= ?
            GROUP BY jobs.id
            ORDER BY jobs.created_at DESC
            """,
            ((datetime.now(timezone.utc) - timedelta(days=84)).isoformat(),),
        ).fetchall()
        service_activations = service_activation_records()
        pilot_metrics = pilot_cell_metrics(
            pilot_project_rows,
            [
                {
                    "service_slug": activation["service_slug"],
                    "zone_slug": activation["zone_slug"],
                    "current_eligible_contractors": activation["eligible_contractors"],
                    "minimum_eligible_contractors": activation[
                        "minimum_eligible_contractors"
                    ],
                    "activation_status": activation["status"],
                    "service_name": activation["service_name"],
                    "zone_name": activation["zone_name"],
                }
                for activation in service_activations
            ],
            as_of=datetime.now(timezone.utc).date().isoformat(),
        )
        repeat_work_row = db.execute(
            """
            SELECT
                COUNT(*) AS invitations_created,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END)
                    AS invitations_pending,
                SUM(CASE WHEN status = 'bid_sent' THEN 1 ELSE 0 END)
                    AS invitations_bid_sent,
                SUM(CASE WHEN status = 'declined' THEN 1 ELSE 0 END)
                    AS invitations_declined,
                SUM(CASE WHEN status = 'withdrawn' THEN 1 ELSE 0 END)
                    AS invitations_withdrawn,
                SUM(
                    CASE WHEN EXISTS (
                        SELECT 1
                        FROM match_requests
                        JOIN match_completions
                          ON match_completions.match_request_id = match_requests.id
                        WHERE match_requests.job_id = repeat_provider_invitations.job_id
                          AND match_requests.contractor_id = repeat_provider_invitations.contractor_id
                          AND match_requests.status = 'approved'
                          AND match_completions.verified_at IS NOT NULL
                    ) THEN 1 ELSE 0 END
                ) AS verified_repeat_projects
            FROM repeat_provider_invitations
            """
        ).fetchone()
        repeat_work_metrics = {
            key: int(value or 0) for key, value in dict(repeat_work_row).items()
        }
        repeat_work_metrics["invitation_bid_rate"] = percentage_rate(
            repeat_work_metrics["invitations_bid_sent"],
            repeat_work_metrics["invitations_created"],
        )
        repeat_work_metrics["verified_repeat_rate"] = percentage_rate(
            repeat_work_metrics["verified_repeat_projects"],
            repeat_work_metrics["invitations_bid_sent"],
        )
        repeat_invitations = db.execute(
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
            """
        ).fetchall()
        lead_alert_row = db.execute(
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
            """
        ).fetchone()
        lead_alert_metrics = {
            key: int(value or 0) for key, value in dict(lead_alert_row).items()
        }
        recent_lead_alerts = db.execute(
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
            """
        ).fetchall()
        stats = {
            "open_reports": len(reports) + len(review_reports),
            "suspended_users": sum(1 for user in users if user["status"] == "suspended"),
            "hidden_content": hidden_content_count,
            "audit_actions": audit_action_count,
            "automation_events": automation_event_count,
        }
        return render_template(
            "admin_dashboard.html",
            users=users,
            jobs=jobs,
            lead_feedback=lead_feedback,
            close_outcomes=close_outcomes,
            lead_quality_outcomes=lead_quality_outcomes,
            reports=reports,
            messages=messages,
            actions=actions,
            automation_events=automation_events,
            photos=photos,
            contractor_photos=contractor_photos,
            credentials=[
                credential_response(item, include_private=True)
                | {
                    "contractor_email": item["contractor_email"],
                    "business_name": item["business_name"],
                }
                for item in credentials
            ],
            credential_review_note_max=CREDENTIAL_REVIEW_NOTE_MAX_LENGTH,
            stats=stats,
            marketplace_metrics=marketplace_metrics,
            pilot_metrics=pilot_metrics,
            repeat_work_metrics=repeat_work_metrics,
            repeat_invitations=repeat_invitations,
            lead_alert_metrics=lead_alert_metrics,
            recent_lead_alerts=recent_lead_alerts,
            recent_match_reviews=[
                review_response(item, include_private=True)
                | {
                    "project_title": item["project_title"],
                    "reviewer_email": item["reviewer_email"],
                    "subject_email": item["subject_email"],
                }
                for item in recent_match_reviews
            ],
            match_review_reports=review_reports,
            match_review_metrics=match_review_metrics,
            service_activations=service_activations,
        )

    @app.route("/admin/users/<int:user_id>/<action>", methods=("POST",))
    @role_required("admin")
    def admin_user_action(user_id: int, action: str):
        if action not in {"suspend", "activate"}:
            abort(404)
        target = get_db().execute(
            "SELECT id, role FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not target:
            abort(404)
        if target["role"] == "admin":
            abort(400)
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

    @app.route("/admin/credentials/<int:credential_id>/<action>", methods=("POST",))
    @role_required("admin")
    def admin_credential_action(credential_id: int, action: str):
        credential = get_db().execute(
            "SELECT * FROM contractor_credentials WHERE id = ?",
            (credential_id,),
        ).fetchone()
        if not credential:
            abort(404)
        try:
            review = contractor_credential_review_payload(
                request.form.to_dict(),
                action,
                credential["source_url"],
            )
        except ContractorCredentialError as exc:
            flash(" ".join(exc.errors), "error")
            return redirect(url_for("admin_dashboard") + "#credential-review")
        checked_at = now_iso()
        expires_at = review["expires_at"]
        if action == "expire" and not expires_at:
            expires_at = today_iso()
        get_db().execute(
            """
            UPDATE contractor_credentials
            SET status = ?, source_url = ?, checked_at = ?, expires_at = ?,
                reviewed_by = ?, review_note = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                review["status"],
                review["source_url"],
                checked_at,
                expires_at,
                g.user["id"],
                review["review_note"],
                checked_at,
                credential_id,
            ),
        )
        log_action(
            action,
            "credential",
            credential_id,
            f"Set contractor credential status to {review['status']}.",
        )
        get_db().commit()
        flash("Credential review saved.", "success")
        return redirect(url_for("admin_dashboard") + "#credential-review")

    @app.route("/admin/messages/<int:message_id>/<action>", methods=("POST",))
    @role_required("admin")
    def admin_message_action(message_id: int, action: str):
        if action not in {"hide", "restore"}:
            abort(404)
        hidden = 1 if action == "hide" else 0
        get_db().execute("UPDATE messages SET is_hidden = ? WHERE id = ?", (hidden, message_id))
        log_action(action, "message", message_id, f"Set message hidden={hidden}.")
        get_db().commit()
        flash("Message hidden." if hidden else "Message restored.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/reviews/<int:review_id>/<action>", methods=("POST",))
    @role_required("admin")
    def admin_match_review_action(review_id: int, action: str):
        if action not in {"hide", "restore"}:
            abort(404)
        hidden = 1 if action == "hide" else 0
        changed = get_db().execute(
            "UPDATE match_reviews SET is_hidden = ?, updated_at = ? WHERE id = ?",
            (hidden, now_iso(), review_id),
        )
        if changed.rowcount != 1:
            get_db().rollback()
            abort(404)
        log_action(
            action,
            "match_review",
            review_id,
            f"Set completed-work feedback hidden={hidden}.",
        )
        get_db().commit()
        flash("Feedback moderation updated.", "success")
        return redirect(url_for("admin_dashboard") + "#completed-feedback-moderation")

    @app.route("/admin/review-reports/<int:report_id>/resolve", methods=("POST",))
    @role_required("admin")
    def admin_resolve_match_review_report(report_id: int):
        changed = get_db().execute(
            """
            UPDATE match_review_reports
            SET status = 'resolved', resolved_at = ?
            WHERE id = ? AND status = 'open'
            """,
            (now_iso(), report_id),
        )
        if changed.rowcount != 1:
            get_db().rollback()
            abort(404)
        log_action(
            "resolve",
            "match_review_report",
            report_id,
            "Marked completed-work feedback report resolved.",
        )
        get_db().commit()
        flash("Feedback report resolved.", "success")
        return redirect(url_for("admin_dashboard") + "#completed-feedback-moderation")

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
        return send_private_file(
            photo["stored_path"],
            photo["content_type"],
            f"workdoe-photo-{photo['id']}",
        )

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
        return send_private_file(
            photo["stored_path"],
            photo["content_type"],
            f"workdoe-photo-{photo['id']}",
        )


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
            secondary_url=secondary_url or url_for("create_account"),
        ),
        status_code,
    )


def load_logged_in_user() -> None:
    user_id = session.get("user_id")
    g.user = None
    g.unread_message_count = 0
    if user_id is not None:
        g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if g.user and g.user["status"] != "active" and request.endpoint != "logout":
            session.clear()
            flash("Your account is not active.", "error")
            g.user = None
        elif g.user and g.user["role"] in {"client", "contractor"}:
            g.unread_message_count = unread_message_count(
                get_db(),
                g.user["id"],
                g.user["role"],
            )


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
    response.headers.setdefault(
        "Content-Security-Policy",
        content_security_policy(),
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault(
        "X-Frame-Options",
        "DENY",
    )
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
        clerk_sources = {
            "script-src": (
                clerk_origin,
                CLERK_CHALLENGE_ORIGIN,
                CLERK_PROTECT_ORIGIN,
            ),
            "connect-src": (
                clerk_origin,
                CLERK_CHALLENGE_ORIGIN,
                CLERK_PROTECT_ORIGIN,
                CLERK_IMAGE_ORIGIN,
                *CLERK_TELEMETRY_ORIGINS,
            ),
            "img-src": (clerk_origin, CLERK_IMAGE_ORIGIN),
            "style-src": ("'unsafe-inline'",),
            "style-src-elem": ("'unsafe-inline'", clerk_origin),
        }
        for source_directive, sources in clerk_sources.items():
            for source in sources:
                directives = [
                    add_csp_source(directive, source_directive, source)
                    for directive in directives
                ]
        directives = [
            "worker-src 'self' blob:"
            if directive.startswith("worker-src ")
            else directive
            for directive in directives
        ]
        frame_sources.extend(
            (
                clerk_origin,
                CLERK_CHALLENGE_ORIGIN,
                CLERK_PROTECT_ORIGIN,
            )
        )
    if frame_sources:
        directives.append("frame-src " + " ".join(dict.fromkeys(frame_sources)))
    return "; ".join(directives)


def embedded_dialog_mode() -> bool:
    return request.args.get("embed") == "1"


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
        or not (
            is_workdoe_domain(parsed.hostname)
            or is_clerk_development_domain(parsed.hostname)
        )
    ):
        return ""
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def is_workdoe_domain(hostname: str | None) -> bool:
    host = (hostname or "").strip().lower().rstrip(".")
    return host == WORKDOE_PUBLIC_DOMAIN or host.endswith(f".{WORKDOE_PUBLIC_DOMAIN}")


def is_clerk_development_domain(hostname: str | None) -> bool:
    host = (hostname or "").strip().lower().rstrip(".")
    return bool(host and host.endswith(".clerk.accounts.dev"))


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
        # Production config pins this request to Cloudflare's HTTPS siteverify endpoint.
        with urlopen(verify_request, timeout=4) as response:  # nosec B310
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


def request_idempotency_key() -> str:
    raw_key = request.form.get("idempotency_key") or request.headers.get(
        "Idempotency-Key"
    )
    key = normalize_idempotency_key(raw_key)
    return key or new_idempotency_key()


def begin_idempotent_write(
    db: sqlite3.Connection,
    actor_id: int,
    action: str,
    resource_type: str,
    key: str,
):
    normalized_action = idempotency_action(action)
    normalized_resource = idempotency_resource_type(resource_type)
    key_hash = idempotency_key_hash(key)
    timestamp = datetime.now(timezone.utc)
    created_at = timestamp.isoformat(timespec="seconds")
    expires_at = (timestamp + timedelta(hours=24)).isoformat(timespec="seconds")
    db.execute("DELETE FROM idempotency_requests WHERE expires_at < ?", (created_at,))
    existing = db.execute(
        """
        SELECT * FROM idempotency_requests
        WHERE actor_id = ? AND action = ? AND key_hash = ?
        LIMIT 1
        """,
        (int(actor_id), normalized_action, key_hash),
    ).fetchone()
    if existing:
        return existing
    try:
        db.execute(
            """
            INSERT INTO idempotency_requests
                (actor_id, action, key_hash, resource_type, resource_id,
                 status, created_at, completed_at, expires_at)
            VALUES (?, ?, ?, ?, NULL, 'processing', ?, NULL, ?)
            """,
            (
                int(actor_id),
                normalized_action,
                key_hash,
                normalized_resource,
                created_at,
                expires_at,
            ),
        )
    except sqlite3.IntegrityError:
        existing = db.execute(
            """
            SELECT * FROM idempotency_requests
            WHERE actor_id = ? AND action = ? AND key_hash = ?
            LIMIT 1
            """,
            (int(actor_id), normalized_action, key_hash),
        ).fetchone()
        if existing:
            return existing
        raise
    return None


def completed_idempotent_resource(record, resource_type: str) -> int | None:
    if not record:
        return None
    expected = idempotency_resource_type(resource_type)
    if record["resource_type"] != expected:
        abort(409)
    if record["status"] != "completed" or not record["resource_id"]:
        abort(409, "That request is still being processed. Try again shortly.")
    return int(record["resource_id"])


def complete_idempotent_write(
    db: sqlite3.Connection,
    actor_id: int,
    action: str,
    resource_type: str,
    key: str,
    resource_id: int,
) -> None:
    completed_at = now_iso()
    updated = db.execute(
        """
        UPDATE idempotency_requests
        SET resource_id = ?, status = 'completed', completed_at = ?
        WHERE actor_id = ? AND action = ? AND key_hash = ?
          AND resource_type = ? AND status = 'processing'
        """,
        (
            int(resource_id),
            completed_at,
            int(actor_id),
            idempotency_action(action),
            idempotency_key_hash(key),
            idempotency_resource_type(resource_type),
        ),
    )
    if updated.rowcount != 1:
        raise RuntimeError("Idempotent request completion failed.")


def load_job_scope_answers(job_id: int) -> dict[str, str]:
    rows = get_db().execute(
        "SELECT question_key, answer_code FROM job_scope_answers WHERE job_id = ?",
        (job_id,),
    ).fetchall()
    return {row["question_key"]: row["answer_code"] for row in rows}


def load_job_draft_scope_answers(draft_id: int) -> dict[str, str]:
    rows = get_db().execute(
        "SELECT question_key, answer_code FROM job_draft_scope_answers WHERE draft_id = ?",
        (draft_id,),
    ).fetchall()
    return {row["question_key"]: row["answer_code"] for row in rows}


def replace_job_scope_answers(
    db: sqlite3.Connection,
    job_id: int,
    service_slug: str,
    answers: dict[str, str],
) -> None:
    db.execute("DELETE FROM job_scope_answers WHERE job_id = ?", (job_id,))
    timestamp = now_iso()
    for answer in scope_answer_projection(service_slug, answers):
        db.execute(
            """
            INSERT INTO job_scope_answers
                (job_id, schema_version, question_key, answer_code, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                SCOPE_SCHEMA_VERSION,
                answer["question_key"],
                answer["answer_code"],
                timestamp,
                timestamp,
            ),
        )


def replace_job_draft_scope_answers(
    db: sqlite3.Connection,
    draft_id: int,
    service_slug: str,
    answers: dict[str, str],
) -> None:
    db.execute("DELETE FROM job_draft_scope_answers WHERE draft_id = ?", (draft_id,))
    timestamp = now_iso()
    for answer in scope_answer_projection(service_slug, answers):
        db.execute(
            """
            INSERT INTO job_draft_scope_answers
                (draft_id, schema_version, question_key, answer_code, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                draft_id,
                SCOPE_SCHEMA_VERSION,
                answer["question_key"],
                answer["answer_code"],
                timestamp,
                timestamp,
            ),
        )


def current_job_draft():
    token = session.get(JOB_DRAFT_SESSION_KEY)
    if not token:
        return None
    draft = get_db().execute(
        """
        SELECT * FROM job_drafts
        WHERE token_hash = ? AND consumed_at IS NULL AND expires_at >= ?
        LIMIT 1
        """,
        (hash_token(token), now_iso()),
    ).fetchone()
    if not draft:
        session.pop(JOB_DRAFT_SESSION_KEY, None)
        return None
    hydrated = dict(draft)
    hydrated["scope_answers"] = load_job_draft_scope_answers(int(draft["id"]))
    return hydrated


def save_job_draft(form: dict) -> None:
    db = get_db()
    now = now_iso()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=JOB_DRAFT_TTL_HOURS)
    ).isoformat(timespec="seconds")
    old_token = session.get(JOB_DRAFT_SESSION_KEY)
    if old_token:
        db.execute("DELETE FROM job_drafts WHERE token_hash = ?", (hash_token(old_token),))
    db.execute(
        "DELETE FROM job_drafts WHERE consumed_at IS NOT NULL OR expires_at < ?",
        (now,),
    )
    token = secrets.token_urlsafe(32)
    cursor = db.execute(
        """
        INSERT INTO job_drafts
            (token_hash, title, category, service_group_slug, service_slug,
             project_setting, city, state, zip_code, description,
             desired_date, budget_min, budget_max, expires_at, consumed_at,
             created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
        """,
        (
            hash_token(token),
            form["title"],
            form["category"],
            form["service_group_slug"],
            form["service_slug"],
            form["project_setting"],
            form["city"],
            form["state"],
            form["zip_code"],
            form["description"],
            form["desired_date"],
            budget_database_value(form["budget_min"]),
            budget_database_value(form["budget_max"]),
            expires_at,
            now,
            now,
        ),
    )
    replace_job_draft_scope_answers(
        db,
        int(cursor.lastrowid),
        form["service_slug"],
        form.get("scope_answers", {}),
    )
    db.commit()
    session[JOB_DRAFT_SESSION_KEY] = token


def consume_job_draft() -> None:
    token = session.pop(JOB_DRAFT_SESSION_KEY, None)
    if token:
        get_db().execute(
            "UPDATE job_drafts SET consumed_at = ?, updated_at = ? WHERE token_hash = ?",
            (now_iso(), now_iso(), hash_token(token)),
        )


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


def start_url_for_email(
    email: str,
    selected_job=None,
    next_url: str = "",
) -> str:
    safe_next = safe_next_url(next_url)
    next_route = urlparse(safe_next).path
    args = {
        "intent": "find-work" if selected_job or next_route == url_for("leads") else "post-job",
    }
    if email:
        args["email"] = email
    if selected_job:
        args["job_id"] = selected_job["id"]
    if safe_next:
        args["next"] = safe_next
    return url_for("create_account", **args)


def safe_next_url(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    if (
        len(value) > 500
        or not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
        or any(ord(character) < 32 for character in value)
    ):
        return ""
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return ""
    if value == url_for("logout"):
        return ""
    return value


def lead_next_url_with_filters(value: str, filters: dict[str, str]) -> str:
    parsed = urlparse(value)
    if parsed.path != url_for("leads"):
        return value
    existing = parse_qs(parsed.query)
    view_value = existing.get("view", [""])[0]
    view = normalize_lead_view(view_value)
    args = {
        key: filter_value
        for key, filter_value in {
            "category": filters.get("category", ""),
            "family": filters.get("family", ""),
            "service": filters.get("service", ""),
            "q": filters.get("q", ""),
            "sort": filters.get("sort", DEFAULT_JOB_SORT),
            "view": view if view != "all" else "",
        }.items()
        if filter_value and not (key == "sort" and filter_value == DEFAULT_JOB_SORT)
    }
    return url_for("leads", **args)


def cleared_lead_next_url(value: str) -> str:
    return lead_next_url_with_filters(
        value,
        {
            "category": "",
            "family": "",
            "service": "",
            "q": "",
            "sort": DEFAULT_JOB_SORT,
        },
    )


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


def blank_job_form() -> dict:
    return {
        "title": "",
        "category": JOB_CATEGORIES[0],
        "service_group_slug": "",
        "service_slug": "",
        "project_setting": "",
        "desired_date": "",
        "city": "",
        "state": "DC",
        "zip_code": "",
        "description": "",
        "budget_min": "",
        "budget_max": "",
        "service_policy_acknowledgement": "",
        "scope_answers": {},
    }


def job_to_form(job) -> dict:
    job_keys = set(job.keys())
    selection = service_selection(
        job["service_slug"] if "service_slug" in job_keys else "",
        job["service_group_slug"] if "service_group_slug" in job_keys else "",
        job["category"],
    )
    if "scope_answers" in job_keys:
        scope_answers = dict(job["scope_answers"] or {})
    elif "token_hash" in job_keys:
        scope_answers = load_job_draft_scope_answers(int(job["id"]))
    else:
        scope_answers = load_job_scope_answers(int(job["id"]))
    return {
        "title": job["title"],
        "category": selection["category"],
        "service_group_slug": selection["service_group_slug"],
        "service_slug": selection["service_slug"],
        "project_setting": normalize_project_setting(
            job["project_setting"] if "project_setting" in job_keys else ""
        ),
        "desired_date": job["desired_date"] or "",
        "city": job["city"],
        "state": job["state"],
        "zip_code": job["zip_code"],
        "description": job["description"],
        "budget_min": str(job["budget_min"]) if job["budget_min"] is not None else "",
        "budget_max": str(job["budget_max"]) if job["budget_max"] is not None else "",
        "service_policy_acknowledgement": "",
        "scope_answers": scope_answers,
    }


def ensure_client_profile(user):
    db = get_db()
    profile = db.execute(
        "SELECT * FROM client_profiles WHERE user_id = ?",
        (user["id"],),
    ).fetchone()
    if profile:
        return profile
    timestamp = now_iso()
    db.execute(
        """
        INSERT INTO client_profiles
            (user_id, organization_name, phone, account_type,
             notification_preference, email_reminder_consent_at,
             profile_note, updated_at)
        VALUES (?, ?, '', 'household', 'workdoe', NULL, '', ?)
        """,
        (user["id"], user["company_name"] or user["display_name"], timestamp),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM client_profiles WHERE user_id = ?",
        (user["id"],),
    ).fetchone()


def client_saved_locations(client_id: int):
    return get_db().execute(
        """
        SELECT * FROM client_saved_locations
        WHERE client_id = ?
        ORDER BY updated_at DESC, id DESC
        """,
        (client_id,),
    ).fetchall()


def client_project_templates(client_id: int):
    return get_db().execute(
        """
        SELECT * FROM client_project_templates
        WHERE client_id = ?
        ORDER BY updated_at DESC, id DESC
        """,
        (client_id,),
    ).fetchall()


def contractor_proposal_templates(contractor_id: int):
    return get_db().execute(
        """
        SELECT * FROM contractor_proposal_templates
        WHERE contractor_id = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT ?
        """,
        (contractor_id, PROPOSAL_TEMPLATE_LIMIT),
    ).fetchall()


def client_template_source_jobs(client_id: int):
    return get_db().execute(
        """
        SELECT id, title, category, status, updated_at
        FROM jobs
        WHERE client_id = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT 100
        """,
        (client_id,),
    ).fetchall()


def render_client_profile(
    profile_form,
    *,
    profile_errors: list[str] | None = None,
    profile_field_errors: dict[str, list[str]] | None = None,
    location_form=None,
    location_errors: list[str] | None = None,
    location_field_errors: dict[str, list[str]] | None = None,
    template_form=None,
    template_errors: list[str] | None = None,
    template_field_errors: dict[str, list[str]] | None = None,
):
    return render_template(
        "client_profile.html",
        profile=profile_form,
        profile_errors=profile_errors or [],
        profile_field_errors=profile_field_errors or {},
        location_form=location_form or {},
        location_errors=location_errors or [],
        location_field_errors=location_field_errors or {},
        saved_locations=client_saved_locations(g.user["id"]),
        account_types=CLIENT_ACCOUNT_TYPES,
        notification_options=CLIENT_NOTIFICATION_OPTIONS,
        organization_max=CLIENT_ORGANIZATION_MAX_LENGTH,
        profile_note_max=CLIENT_PROFILE_NOTE_MAX_LENGTH,
        location_label_max=SAVED_LOCATION_LABEL_MAX_LENGTH,
        location_city_max=SAVED_LOCATION_CITY_MAX_LENGTH,
        saved_location_limit=SAVED_LOCATION_LIMIT,
        project_templates=[
            project_template_response(item)
            for item in client_project_templates(g.user["id"])
        ],
        template_source_jobs=client_template_source_jobs(g.user["id"]),
        template_form=template_form or {},
        template_errors=template_errors or [],
        template_field_errors=template_field_errors or {},
        project_template_limit=PROJECT_TEMPLATE_LIMIT,
        project_template_name_max=PROJECT_TEMPLATE_NAME_MAX_LENGTH,
    )


def render_job_form(
    form: dict[str, str],
    mode: str,
    job=None,
    errors: list[str] | None = None,
    repeat_invitation: dict | None = None,
):
    is_edit = mode == "edit"
    cancel_url = url_for("client_job_detail", job_id=job["id"]) if is_edit and job else url_for("client_dashboard")
    return render_template(
        "job_form.html",
        form=form,
        error_feedback=job_error_feedback(errors or []),
        mode=mode,
        page_eyebrow="Consumer workspace",
        page_title="Edit project" if is_edit else "Post a project",
        page_intro=(
            "Keep scope, timing, and approximate location current."
            if is_edit
            else "Approximate location stays public. Exact details wait for approval."
        ),
        submit_label="Save changes" if is_edit else "Post project",
        cancel_url=cancel_url,
        today=today_iso(),
        title_max=JOB_TITLE_MAX_LENGTH,
        city_max=JOB_CITY_MAX_LENGTH,
        dmv_city_options=dmv_city_options(),
        dmv_zip_options=dmv_zip_options(),
        description_min=JOB_DESCRIPTION_MIN_LENGTH,
        description_max=JOB_DESCRIPTION_MAX_LENGTH,
        budget_max=JOB_BUDGET_MAX,
        project_settings=PROJECT_SETTINGS,
        saved_locations=(client_saved_locations(g.user["id"]) if not is_edit else []),
        repeat_invitation=repeat_invitation,
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
        [
            "title",
            "category",
            "service_group_slug",
            "service_slug",
            "project_setting",
            "desired_date",
            "city",
            "state",
            "zip_code",
            "budget_min",
            "budget_max",
            "description",
            "service_policy_acknowledgement",
        ],
    )


def job_error_field(message: str) -> str:
    if "job title" in message:
        return "title"
    if "curated category" in message:
        return "category"
    if "six work families" in message:
        return "service_group_slug"
    if "service inside" in message:
        return "service_slug"
    if "project setting" in message:
        return "project_setting"
    if "valid desired date" in message or "future desired date" in message:
        return "desired_date"
    if "city" in message:
        return "city"
    if "DC, MD, or VA" in message:
        return "state"
    if "ZIP code" in message:
        return "zip_code"
    if "minimum budget" in message:
        return "budget_min"
    if "maximum budget" in message or "budget maximum" in message:
        return "budget_max"
    if "about the work" in message or "description" in message:
        return "description"
    if "service safety advisory" in message:
        return "service_policy_acknowledgement"
    return ""


def contractor_market_fit(contractor_id: int, profile=None) -> dict[str, list[str]]:
    db = get_db()
    service_rows = db.execute(
        """
        SELECT service_slug
        FROM contractor_service_capabilities
        WHERE contractor_id = ?
        ORDER BY service_slug
        """,
        (contractor_id,),
    ).fetchall()
    zone_rows = db.execute(
        """
        SELECT zone_slug
        FROM contractor_service_zones
        WHERE contractor_id = ?
        ORDER BY zone_slug
        """,
        (contractor_id,),
    ).fetchall()
    if profile is None:
        profile = db.execute(
            "SELECT trades, service_area FROM contractor_profiles WHERE user_id = ?",
            (contractor_id,),
        ).fetchone()
    services = normalize_service_slugs([row["service_slug"] for row in service_rows])
    zones = normalize_zone_slugs([row["zone_slug"] for row in zone_rows])
    if profile and not services:
        services = infer_service_slugs_from_trades(profile["trades"])
    if profile and not zones:
        zones = infer_zone_slugs_from_area(profile["service_area"])
    return {"service_slugs": services, "service_zone_slugs": zones}


def replace_contractor_market_fit(
    contractor_id: int,
    service_slugs,
    service_zone_slugs,
) -> None:
    db = get_db()
    services = normalize_service_slugs(service_slugs)
    zones = normalize_zone_slugs(service_zone_slugs)
    timestamp = now_iso()
    db.execute(
        "DELETE FROM contractor_service_capabilities WHERE contractor_id = ?",
        (contractor_id,),
    )
    db.execute(
        "DELETE FROM contractor_service_zones WHERE contractor_id = ?",
        (contractor_id,),
    )
    db.executemany(
        """
        INSERT INTO contractor_service_capabilities
            (contractor_id, service_slug, created_at)
        VALUES (?, ?, ?)
        """,
        [(contractor_id, slug, timestamp) for slug in services],
    )
    db.executemany(
        """
        INSERT INTO contractor_service_zones
            (contractor_id, zone_slug, created_at)
        VALUES (?, ?, ?)
        """,
        [(contractor_id, slug, timestamp) for slug in zones],
    )


def contractor_profile_to_form(profile, market_fit=None) -> dict:
    if not profile:
        return {
            "business_name": "",
            "trades": "",
            "service_area": "DMV area",
            "service_slugs": [],
            "service_zone_slugs": [],
            "intro": "",
            "insurance_status": "",
            "license_number": "",
            "years_in_business": "",
            "website": "",
        }
    selections = market_fit or {
        "service_slugs": infer_service_slugs_from_trades(profile["trades"]),
        "service_zone_slugs": infer_zone_slugs_from_area(profile["service_area"]),
    }
    return {
        "business_name": profile["business_name"] or "",
        "trades": profile["trades"] or "",
        "service_area": profile["service_area"] or "",
        "service_slugs": selections["service_slugs"],
        "service_zone_slugs": selections["service_zone_slugs"],
        "intro": profile["intro"] or "",
        "insurance_status": profile["insurance_status"] or "",
        "license_number": profile["license_number"] or "",
        "years_in_business": (
            "" if profile["years_in_business"] is None else str(profile["years_in_business"])
        ),
        "website": profile["website"] or "",
    }


def contractor_credentials_for_user(contractor_id: int):
    return get_db().execute(
        """
        SELECT * FROM contractor_credentials
        WHERE contractor_id = ?
        ORDER BY updated_at DESC, id DESC
        """,
        (contractor_id,),
    ).fetchall()


def contractor_preferences_for_user(contractor_id: int):
    return get_db().execute(
        """
        SELECT * FROM contractor_lead_preferences
        WHERE contractor_id = ?
        LIMIT 1
        """,
        (contractor_id,),
    ).fetchone()


def render_contractor_profile_form(
    form: dict,
    photos,
    credentials=None,
    preferences=None,
    errors: list[str] | None = None,
):
    selected_services = set(normalize_service_slugs(form.get("service_slugs")))
    return render_template(
        "contractor_profile.html",
        form=form,
        photos=photos,
        credentials=[
            credential_response(item, include_private=True)
            for item in (credentials or [])
        ],
        credential_types=CREDENTIAL_TYPES,
        credential_jurisdictions=CREDENTIAL_JURISDICTIONS,
        credential_identifier_max=CREDENTIAL_IDENTIFIER_MAX_LENGTH,
        credential_name_max=CREDENTIAL_NAME_MAX_LENGTH,
        credential_review_note_max=CREDENTIAL_REVIEW_NOTE_MAX_LENGTH,
        selected_trades=parse_trades(form["trades"]),
        selected_services=selected_services,
        selected_service_groups={
            SERVICE_BY_SLUG[slug]["group_slug"] for slug in selected_services
        },
        selected_service_zones=set(normalize_zone_slugs(form.get("service_zone_slugs"))),
        service_groups=SERVICE_GROUPS,
        service_zones=DMV_SERVICE_ZONES,
        limits=contractor_profile_limits(),
        profile_readiness=contractor_profile_readiness(form, photos),
        error_feedback=profile_error_feedback(errors or []),
        preferences=contractor_preferences_response(preferences),
        availability_options=AVAILABILITY_OPTIONS,
    )


def cleaned_contractor_profile_form(form) -> dict:
    structured_market_fit = form.get("market_fit_version") == "1"
    if structured_market_fit:
        service_slugs = normalize_service_slugs(form.getlist("service_slugs"))
        service_zone_slugs = normalize_zone_slugs(form.getlist("service_zone_slugs"))
        trades = legacy_trades_for_services(service_slugs)
        service_area = service_area_label(service_zone_slugs)
    else:
        selected = set(form.getlist("trades"))
        trade_values = [category for category in JOB_CATEGORIES if category in selected]
        trades = ", ".join(trade_values)
        service_area = compact_spaces(form.get("service_area"))
        service_slugs = infer_service_slugs_from_trades(trades)
        service_zone_slugs = infer_zone_slugs_from_area(service_area)
    return {
        "business_name": compact_spaces(form.get("business_name")),
        "trades": trades,
        "service_area": service_area,
        "service_slugs": service_slugs,
        "service_zone_slugs": service_zone_slugs,
        "intro": (form.get("intro") or "").strip(),
        "insurance_status": compact_spaces(form.get("insurance_status")),
        "license_number": compact_spaces(form.get("license_number")),
        "years_in_business": compact_spaces(form.get("years_in_business")),
        "website": compact_spaces(form.get("website")),
    }


def validate_contractor_profile_form(form: dict) -> list[str]:
    errors: list[str] = []
    if not form["business_name"]:
        errors.append("Add a business name.")
    elif len(form["business_name"]) > PROFILE_BUSINESS_MAX_LENGTH:
        errors.append(f"Keep the business name under {PROFILE_BUSINESS_MAX_LENGTH} characters.")
    if not form["trades"]:
        errors.append("Choose at least one service.")
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
        elif not normalized_profile_website(form["website"]):
            errors.append(PROFILE_WEBSITE_ERROR)
    return errors


def profile_error_feedback(errors: list[str]) -> dict:
    return build_error_feedback(
        errors,
        profile_error_field,
        [
            "business_name",
            "trades",
            "service_area",
            "intro",
            "insurance_status",
            "license_number",
            "years_in_business",
            "website",
        ],
    )


def profile_error_field(message: str) -> str:
    if "business name" in message:
        return "business_name"
    if "service area" in message:
        return "service_area"
    if "trade" in message or "service" in message:
        return "trades"
    if "years in business" in message:
        return "years_in_business"
    if "business" in message or "intro" in message:
        return "intro"
    if "insurance" in message:
        return "insurance_status"
    if "license" in message:
        return "license_number"
    if "website" in message or "URL" in message:
        return "website"
    return ""


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
    }


def normalized_profile_website(value: str | None) -> str:
    raw_value = (value or "").strip()
    if not raw_value or any(
        character.isspace() or ord(character) < 32 or ord(character) == 127
        for character in raw_value
    ):
        return ""
    try:
        parsed = urlparse(raw_value)
        port = parsed.port
        hostname = (parsed.hostname or "").rstrip(".")
        ascii_hostname = hostname.encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError):
        return ""
    if (
        parsed.scheme.lower() != "https"
        or not ascii_hostname
        or parsed.username
        or parsed.password
        or port not in {None, 443}
        or ascii_hostname == "localhost"
        or "." not in ascii_hostname
        or any(
            not PROFILE_HOST_LABEL_RE.fullmatch(label)
            for label in ascii_hostname.split(".")
        )
    ):
        return ""
    try:
        ipaddress.ip_address(ascii_hostname)
    except ValueError:
        pass
    else:
        return ""
    return urlunparse(
        (
            "https",
            ascii_hostname,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def profile_website_label(value: str | None) -> str:
    safe_website = normalized_profile_website(value)
    hostname = urlparse(safe_website).hostname if safe_website else ""
    return (hostname or "").removeprefix("www.")


def contractor_profile_readiness(profile: dict, photos=None) -> dict:
    service_slugs = normalize_service_slugs(profile.get("service_slugs"))
    service_zone_slugs = normalize_zone_slugs(profile.get("service_zone_slugs"))
    items = [
        {"label": "Business name", "target": "profile-business-name", "complete": bool(profile.get("business_name"))},
        {"label": "About your work", "target": "profile-intro", "complete": len((profile.get("intro") or "").strip()) >= PROFILE_INTRO_MIN_LENGTH},
        {"label": "Services", "target": "profile-trades", "complete": bool(service_slugs or profile.get("trades"))},
        {"label": "Service zones", "target": "profile-service-area", "complete": bool(service_zone_slugs or profile.get("service_area"))},
        {"label": "Years active", "target": "profile-years-in-business", "complete": str(profile.get("years_in_business") or "").strip() != ""},
        {"label": "HTTPS website", "target": "profile-website", "complete": bool(normalized_profile_website(profile.get("website")))},
        {"label": "Portfolio photo", "target": "profile-photos", "complete": bool(photos)},
    ]
    complete_count = sum(1 for item in items if item["complete"])
    return {
        "items": items,
        "complete_count": complete_count,
        "total_count": len(items),
        "percent": round((complete_count / len(items)) * 100),
    }


def can_view_contractor_website(viewer, contractor_id: int, db) -> bool:
    if not viewer or viewer["status"] != "active":
        return False
    if viewer["role"] == "admin":
        return True
    if viewer["role"] == "contractor":
        return viewer["id"] == contractor_id
    if viewer["role"] != "client":
        return False
    return bool(
        db.execute(
            """
            SELECT 1
            FROM match_requests
            JOIN jobs ON jobs.id = match_requests.job_id
            WHERE match_requests.contractor_id = ?
              AND jobs.client_id = ?
            LIMIT 1
            """,
            (contractor_id, viewer["id"]),
        ).fetchone()
    )


def cleaned_job_form(form) -> dict:
    selection = service_selection(
        form.get("service_slug"),
        form.get("service_group_slug"),
        form.get("category"),
    )
    cleaned = {
        "title": compact_spaces(form.get("title")),
        **selection,
        "project_setting": (form.get("project_setting") or "").strip().lower(),
        "desired_date": (form.get("desired_date") or "").strip(),
        "city": compact_spaces(form.get("city")),
        "state": (form.get("state") or "").strip().upper(),
        "zip_code": "".join(ch for ch in (form.get("zip_code") or "") if ch.isdigit())[:5],
        "description": (form.get("description") or "").strip(),
        "budget_min": compact_spaces(form.get("budget_min")),
        "budget_max": compact_spaces(form.get("budget_max")),
        "service_policy_acknowledgement": compact_spaces(
            form.get("service_policy_acknowledgement")
        ),
    }
    cleaned["scope_answers"] = clean_scope_answers(cleaned["service_slug"], form)
    return cleaned


def validate_budget_value(value: str, label: str, errors: list[str]) -> int | None:
    if not value:
        return None
    if not re.fullmatch(r"\d+", value):
        errors.append(f"Use whole dollars for the {label} budget.")
        return None
    parsed = int(value)
    if parsed > JOB_BUDGET_MAX:
        errors.append(f"Keep the {label} budget at or below ${JOB_BUDGET_MAX:,}.")
        return None
    return parsed


def budget_database_value(value: str) -> int | None:
    return int(value) if value else None


def validate_job_form(form: dict) -> list[str]:
    errors: list[str] = []
    if not form["title"]:
        errors.append("Add a job title.")
    elif len(form["title"]) > JOB_TITLE_MAX_LENGTH:
        errors.append(f"Keep the job title under {JOB_TITLE_MAX_LENGTH} characters.")
    service = SERVICE_BY_SLUG.get(form.get("service_slug", ""))
    if not service:
        errors.append("Choose a curated category.")
    elif form.get("service_group_slug") not in GROUP_BY_SLUG:
        errors.append("Choose one of the six work families.")
    elif service["group_slug"] != form.get("service_group_slug"):
        errors.append("Choose a service inside the selected work family.")
    elif form["category"] not in JOB_CATEGORIES:
        errors.append("Choose a curated category.")
    if form.get("project_setting") and form["project_setting"] not in PROJECT_SETTING_BY_VALUE:
        errors.append("Choose a listed project setting.")
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
    budget_min = validate_budget_value(form["budget_min"], "minimum", errors)
    budget_max = validate_budget_value(form["budget_max"], "maximum", errors)
    if budget_min is not None and budget_max is not None and budget_min > budget_max:
        errors.append("Make the budget maximum at least the minimum budget.")
    errors.extend(
        validate_scope_answers(form.get("service_slug"), form.get("scope_answers", {}))
    )
    policy_error = service_policy_error(
        form.get("service_slug"),
        form.get("service_policy_acknowledgement"),
    )
    if policy_error:
        errors.append(policy_error)
    return errors


def blank_bid_form() -> dict[str, str]:
    return {
        "scope_note": "",
        "price_range": "",
        "timeline": "",
        "experience": "",
        "questions": "",
        "availability": "",
        "service_policy_acknowledgement": "",
    }


def cleaned_bid_form(form) -> dict[str, str]:
    return {
        "scope_note": (form.get("scope_note") or "").strip(),
        "price_range": compact_spaces(form.get("price_range")),
        "timeline": compact_spaces(form.get("timeline")),
        "experience": (form.get("experience") or "").strip(),
        "questions": (form.get("questions") or "").strip(),
        "availability": compact_spaces(form.get("availability")),
        "service_policy_acknowledgement": compact_spaces(
            form.get("service_policy_acknowledgement")
        ),
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
        [
            "scope_note",
            "price_range",
            "timeline",
            "experience",
            "questions",
            "availability",
            "service_policy_acknowledgement",
        ],
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
    if "service safety advisory" in message:
        return "service_policy_acknowledgement"
    return ""


def record_service_policy_acknowledgement(
    db: sqlite3.Connection,
    *,
    user_id: int,
    actor_role: str,
    context: str,
    service_slug: str,
    acknowledgement_version: str,
    job_id: int,
    match_request_id: int | None = None,
) -> None:
    policy = service_policy(service_slug)
    if not policy["acknowledgement_required"]:
        return
    if acknowledgement_version != policy["version"]:
        raise ValueError("The service policy acknowledgement is not current.")
    db.execute(
        """
        INSERT INTO service_policy_acknowledgements
            (user_id, actor_role, context, service_slug, policy_version,
             job_id, match_request_id, acknowledged_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            actor_role,
            context,
            service_slug,
            policy["version"],
            job_id,
            match_request_id,
            now_iso(),
        ),
    )


def message_error_feedback(errors: list[str]) -> dict:
    return build_error_feedback(errors, message_error_field, ["body"])


def message_error_field(message: str) -> str:
    if "message" in message or "1000" in message:
        return "body"
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


def match_for_review(request_id: int):
    return get_db().execute(
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
        (request_id,),
    ).fetchone()


def match_review_for_id(review_id: int):
    return get_db().execute(
        """
        SELECT match_reviews.*,
               match_requests.job_id,
               match_requests.contractor_id,
               match_requests.status AS match_status,
               jobs.client_id,
               match_completions.verified_at
        FROM match_reviews
        JOIN match_requests ON match_requests.id = match_reviews.match_request_id
        JOIN jobs ON jobs.id = match_requests.job_id
        JOIN match_completions
          ON match_completions.match_request_id = match_requests.id
        WHERE match_reviews.id = ?
        LIMIT 1
        """,
        (review_id,),
    ).fetchone()


def review_return_url(review_or_match, role: str) -> str:
    if role == "client":
        job_id = int(
            (review_or_match["job_id"] if review_or_match else 0) or 0
        )
        return (
            url_for("client_job_detail", job_id=job_id) + "#completed-feedback"
            if job_id
            else url_for("client_dashboard")
        )
    return url_for("contractor_dashboard") + "#completed-work"


def match_reviews_by_request(request_ids: list[int]) -> dict[int, dict[str, dict]]:
    if not request_ids:
        return {}
    placeholders = ",".join("?" for _ in request_ids)
    # The interpolated text contains only generated placeholders for integer IDs.
    rows = get_db().execute(
        f"""
        SELECT match_reviews.*, match_completions.verified_at
        FROM match_reviews
        JOIN match_completions
          ON match_completions.match_request_id = match_reviews.match_request_id
        WHERE match_reviews.match_request_id IN ({placeholders})
        ORDER BY match_reviews.created_at, match_reviews.id
        """,  # nosec B608
        request_ids,
    ).fetchall()
    grouped: dict[int, dict[str, dict]] = {}
    for row in rows:
        item = review_response(row, include_private=True)
        grouped.setdefault(item["match_request_id"], {})[
            item["reviewer_role"]
        ] = item
    return grouped


def visible_contractor_reviews(contractor_id: int) -> list[dict]:
    rows = get_db().execute(
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
        (contractor_id,),
    ).fetchall()
    reviews = []
    for row in rows:
        item = review_response(row, include_private=True)
        item["service_name"] = service_label(
            row["service_slug"], row["category"]
        )
        reviews.append(item)
    return reviews


def report_target_visible_to_user(user, target_type: str, target_id: int) -> bool:
    if not user or user["status"] != "active":
        return False
    role = user["role"]
    user_id = int(user["id"])
    db = get_db()
    if target_type == "job":
        job = db.execute(
            "SELECT id, client_id, status FROM jobs WHERE id = ?",
            (target_id,),
        ).fetchone()
        if not job:
            return False
        return role == "admin" or (role == "contractor" and job["status"] != "hidden")
    if target_type == "profile":
        contractor = db.execute(
            """
            SELECT contractor_profiles.user_id, users.status
            FROM contractor_profiles
            JOIN users ON users.id = contractor_profiles.user_id
            WHERE contractor_profiles.user_id = ? AND users.role = 'contractor'
            """,
            (target_id,),
        ).fetchone()
        if not contractor:
            return False
        return role == "admin" or (
            contractor["status"] == "active" and user_id != int(contractor["user_id"])
        )
    if target_type == "message":
        message = db.execute(
            """
            SELECT messages.id, messages.is_hidden,
                   threads.client_id, threads.contractor_id
            FROM messages
            JOIN threads ON threads.id = messages.thread_id
            WHERE messages.id = ?
            """,
            (target_id,),
        ).fetchone()
        if not message:
            return False
        return role == "admin" or (
            not message["is_hidden"]
            and user_id in {int(message["client_id"]), int(message["contractor_id"])}
        )
    return False


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
            next_url = safe_next_url(request.full_path.removesuffix("?"))
            return redirect(url_for("login", next=next_url or request.path))
        return view(**kwargs)

    return wrapped_view


def role_required(*roles: str):
    def decorator(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                flash("Sign in to continue.", "error")
                next_url = safe_next_url(request.full_path.removesuffix("?"))
                return redirect(url_for("login", next=next_url or request.path))
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
               match_requests.price_range, match_requests.timeline,
               match_requests.availability,
               client.display_name AS client_name,
               contractor.display_name AS contractor_name
        FROM threads
        JOIN jobs ON jobs.id = threads.job_id
        JOIN match_requests ON match_requests.id = threads.match_request_id
        JOIN users AS client ON client.id = threads.client_id
        JOIN users AS contractor ON contractor.id = threads.contractor_id
        WHERE threads.id = ?
        """,
        (thread_id,),
    ).fetchone()


def mark_thread_read(
    db: sqlite3.Connection,
    thread_id: int,
    user_id: int,
    last_read_message_id: int,
    last_read_at: str,
) -> None:
    db.execute(
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
        (thread_id, user_id, last_read_message_id, last_read_at),
    )


def unread_message_count(
    db: sqlite3.Connection,
    user_id: int,
    role: str,
) -> int:
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
    row = db.execute(
        query,
        (user_id, user_id, user_id),
    ).fetchone()
    return int(row["unread_count"] or 0)


def first_filter_value(values, key: str) -> str:
    value = values.get(key, "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "")


def public_job_filters(values=None) -> dict[str, str]:
    values = request.args if values is None else values
    category = first_filter_value(values, "category")
    if category not in JOB_CATEGORIES:
        category = ""
    family = compact_spaces(first_filter_value(values, "family"))
    if family not in GROUP_BY_SLUG:
        family = ""
    service = compact_spaces(first_filter_value(values, "service"))
    selected_service = SERVICE_BY_SLUG.get(service)
    if not selected_service or family and selected_service["group_slug"] != family:
        service = ""
    elif not family:
        family = selected_service["group_slug"]
    return {
        "category": category,
        "family": family,
        "service": service,
        "q": compact_spaces(first_filter_value(values, "q"))[:FILTER_QUERY_MAX_LENGTH],
        "sort": normalize_job_sort(first_filter_value(values, "sort")),
    }


def normalize_job_sort(value: str | None) -> str:
    allowed = {option[0] for option in JOB_SORT_OPTIONS}
    return value if value in allowed else DEFAULT_JOB_SORT


def public_filters_active(filters: dict[str, str]) -> bool:
    return bool(
        filters.get("category")
        or filters.get("family")
        or filters.get("service")
        or filters.get("q")
        or filters.get("sort", DEFAULT_JOB_SORT) != DEFAULT_JOB_SORT
    )


def service_family_filter_links(
    endpoint: str,
    filters: dict[str, str],
    base_args: dict[str, str | int] | None = None,
    anchor: str = "",
) -> list[dict[str, str | bool]]:
    shared: dict[str, str | int] = {
        key: value for key, value in (base_args or {}).items() if value not in {None, ""}
    }
    if filters.get("q"):
        shared["q"] = filters["q"]
    if filters.get("sort", DEFAULT_JOB_SORT) != DEFAULT_JOB_SORT:
        shared["sort"] = filters["sort"]
    current = filters.get("family", "")
    links: list[dict[str, str | bool]] = [
        {
            "slug": "",
            "number": "00",
            "name": "All work",
            "description": "Every open service",
            "icon": "",
            "active": not current,
            "url": url_for(endpoint, _anchor=anchor or None, **shared),
        }
    ]
    for index, group in enumerate(SERVICE_GROUPS, start=1):
        args = {**shared, "family": group["slug"]}
        links.append(
            {
                "slug": group["slug"],
                "number": f"{index:02d}",
                "name": group["name"],
                "description": group["description"],
                "icon": group["icon"],
                "active": current == group["slug"],
                "url": url_for(endpoint, _anchor=anchor or None, **args),
            }
        )
    return links


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
        if filters.get("family"):
            args["family"] = filters["family"]
        if filters.get("service"):
            args["service"] = filters["service"]
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


def normalize_message_thread_view(value: str | None) -> str:
    allowed = {option[0] for option in MESSAGE_THREAD_VIEW_OPTIONS}
    return value if value in allowed else "all"


def message_thread_view_links() -> list[dict[str, str]]:
    return [
        {
            "value": value,
            "label": label,
            "url": url_for("message_threads", **({"view": value} if value != "all" else {})),
        }
        for value, label in MESSAGE_THREAD_VIEW_OPTIONS
    ]


def bid_view_links(
    job_id: int,
    credential_filter: str = "all",
) -> list[dict[str, str]]:
    links = []
    for value, label in BID_VIEW_OPTIONS:
        args = {"bids": value} if value != "all" else {}
        if credential_filter != "all":
            args["credentials"] = credential_filter
        links.append(
            {
                "value": value,
                "label": label,
                "url": url_for("client_job_detail", job_id=job_id, **args),
            }
        )
    return links


def bid_credential_filter_links(
    job_id: int,
    bid_view: str,
    options: list[dict],
) -> list[dict]:
    links = []
    for option in options:
        value = option["value"]
        args = {}
        if bid_view != "all":
            args["bids"] = bid_view
        if value != "all":
            args["credentials"] = value
        links.append(
            {
                **option,
                "url": url_for("client_job_detail", job_id=job_id, **args)
                + "#mini-bids",
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
    if filters.get("family"):
        args["family"] = filters["family"]
    if filters.get("service"):
        args["service"] = filters["service"]
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
    annotated_jobs = [dict(row) for row in jobs]
    if not annotated_jobs:
        return annotated_jobs
    placeholders = ", ".join("?" for _ in annotated_jobs)
    params = [contractor_id, *(job["id"] for job in annotated_jobs)]
    # Only '?' placeholders are generated here; every value remains parameterized.
    status_query = f"""
        SELECT job_id, status
        FROM match_requests
        WHERE contractor_id = ? AND job_id IN ({placeholders})
        """  # nosec B608
    rows = get_db().execute(
        status_query,
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


def client_jobs_workspace(
    client_id: int,
    job_view: str,
) -> tuple[list[dict], dict[str, int], list[dict]]:
    rows = get_db().execute(
        """
        SELECT jobs.*,
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
               (
                   SELECT verified_request.id
                   FROM match_requests AS verified_request
                   JOIN match_completions AS verified_completion
                     ON verified_completion.match_request_id = verified_request.id
                   WHERE verified_request.job_id = jobs.id
                     AND verified_request.status = 'approved'
                     AND verified_completion.verified_at IS NOT NULL
                   ORDER BY verified_completion.verified_at DESC, verified_request.id DESC
                   LIMIT 1
               ) AS repeat_match_request_id,
               (
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
        ORDER BY jobs.created_at DESC
        """,
        (client_id,),
    ).fetchall()
    all_jobs = [dict(row) for row in rows]
    for job in all_jobs:
        job["bid_window"] = bid_window(job)
        job["brief_readiness"] = project_brief_readiness(job)
    jobs = filter_client_jobs_by_view(all_jobs, job_view)
    stats = {
        "visible_jobs": len(jobs),
        "total_jobs": len(all_jobs),
        "open_jobs": sum(1 for job in all_jobs if job["status"] == "open"),
        "closed_jobs": sum(1 for job in all_jobs if job["status"] == "closed"),
        "review_jobs": sum(1 for job in all_jobs if (job["pending_count"] or 0) > 0),
        "pending_requests": sum(job["pending_count"] or 0 for job in all_jobs),
        "approved_requests": sum(job["approved_count"] or 0 for job in all_jobs),
        "rejected_requests": sum(job["rejected_count"] or 0 for job in all_jobs),
        "verified_completions": sum(
            job["verified_completion_count"] or 0 for job in all_jobs
        ),
        "brief_ready_jobs": sum(
            1 for job in all_jobs if job["brief_readiness"]["state"] == "ready"
        ),
    }
    history = [job for job in all_jobs if job["status"] == "closed"]
    return jobs, stats, history


def repeat_invitation_source_record(
    client_id: int,
    source_job_id: int,
    source_match_request_id: int,
):
    return get_db().execute(
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
        (source_job_id, client_id, source_match_request_id),
    ).fetchone()


def repeat_invitation_for_job(job_id: int):
    return get_db().execute(
        """
        SELECT repeat_provider_invitations.*,
               jobs.title AS project_title,
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
        LIMIT 1
        """,
        (job_id,),
    ).fetchone()


def contractor_repeat_invitations(contractor_id: int) -> list[dict]:
    rows = get_db().execute(
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
              FROM match_requests AS own_request
              WHERE own_request.job_id = jobs.id
                AND own_request.contractor_id = repeat_provider_invitations.contractor_id
          )
        GROUP BY repeat_provider_invitations.id
        ORDER BY repeat_provider_invitations.created_at DESC
        """,
        (contractor_id, now_iso()),
    ).fetchall()
    invitations = []
    for row in rows:
        item = repeat_invitation_response(row)
        item["bid_window"] = bid_window(
            {
                **dict(row),
                "status": row["job_status"],
            },
            row["request_count"],
        )
        invitations.append(item)
    return invitations


def filter_bids_by_view(bids, bid_view: str) -> list:
    if bid_view == "all":
        return list(bids)
    return [bid for bid in bids if bid["status"] == bid_view]


def public_open_jobs(
    limit: int = 8,
    filters: dict[str, str] | None = None,
    target: str = "start",
):
    jobs, map_jobs, _has_more = public_open_jobs_page(
        limit=limit,
        filters=filters,
        target=target,
    )
    return jobs, map_jobs


def public_open_jobs_page(
    limit: int = 8,
    filters: dict[str, str] | None = None,
    target: str = "start",
    viewport: dict[str, float] | None = None,
    offset: int = 0,
):
    active_filters = filters or {
        "category": "",
        "family": "",
        "service": "",
        "q": "",
        "sort": DEFAULT_JOB_SORT,
    }
    public_target = normalize_public_job_target(target)
    sql = [
        """
        SELECT jobs.*,
               COUNT(job_photos.id) AS photo_count,
               (SELECT COUNT(*) FROM job_scope_answers
                WHERE job_scope_answers.job_id = jobs.id) AS scope_answer_count,
               (SELECT COUNT(*) FROM match_requests WHERE job_id = jobs.id)
                   AS request_count
        FROM jobs
        LEFT JOIN job_photos ON job_photos.job_id = jobs.id AND job_photos.is_hidden = 0
        WHERE jobs.status = 'open'
        """,
    ]
    params: list[str | int] = []
    if service_activation_required():
        sql.append(live_service_activation_sql())
    if active_filters["category"]:
        sql.append("AND jobs.category = ?")
        params.append(active_filters["category"])
    if active_filters.get("service"):
        sql.append("AND jobs.service_slug = ?")
        params.append(active_filters["service"])
    if active_filters.get("family"):
        sql.append("AND jobs.service_group_slug = ?")
        params.append(active_filters["family"])
    if active_filters["q"]:
        like = f"%{active_filters['q']}%"
        sql.append(
            "AND (jobs.city LIKE ? OR jobs.state LIKE ? OR jobs.zip_code LIKE ? OR jobs.title LIKE ?)"
        )
        params.extend([like, like, like, like])
    viewport_clause, viewport_params = public_viewport_sql(viewport)
    if viewport_clause:
        sql.append(viewport_clause)
        params.extend(viewport_params)
    sort_order = normalize_job_sort(active_filters.get("sort"))
    order_clauses = {
        "newest": "jobs.created_at DESC, jobs.id DESC",
        "soonest": (
            "CASE WHEN jobs.desired_date IS NULL OR jobs.desired_date = '' THEN 1 ELSE 0 END, "
            "jobs.desired_date ASC, jobs.created_at DESC, jobs.id DESC"
        ),
        "city": "jobs.city COLLATE NOCASE ASC, jobs.created_at DESC, jobs.id DESC",
    }
    sql.append(
        f"GROUP BY jobs.id ORDER BY {order_clauses[sort_order]} LIMIT ? OFFSET ?"
    )
    params.extend([limit + 1, max(0, offset)])
    page_rows = get_db().execute("\n".join(sql), params).fetchall()
    has_more = len(page_rows) > limit
    jobs = page_rows[:limit]
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
            make_url = lambda row: url_for("create_account", intent="find-work", job_id=row["id"])
            action_label = "Start"
    map_jobs = [
        {
            "id": row["id"],
            "title": row["title"],
            "category": row["category"],
            "service_group_slug": row["service_group_slug"],
            "service_slug": row["service_slug"],
            "service_name": service_label(row["service_slug"], row["category"]),
            "city": row["city"],
            "state": row["state"],
            "desired_date": row["desired_date"] or "",
            "photo_count": int(row["photo_count"] or 0),
            "lat": row["approx_lat"],
            "lng": row["approx_lng"],
            "url": make_url(row),
            "detail_url": make_url(row),
            "action_label": action_label,
            "budget": budget_label(row),
            "is_demo": False,
            "sample_label": "Open project",
        }
        for row in jobs
        if row["approx_lat"] and row["approx_lng"]
    ]
    return jobs, map_jobs, has_more


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
    if content_type != ALLOWED_IMAGE_MIME[ext] or not uploaded_file_signature_matches(file, ext):
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


def uploaded_file_signature_matches(file, extension: str) -> bool:
    try:
        position = file.stream.tell()
        prefix = file.stream.read(12)
        file.stream.seek(position)
    except (AttributeError, OSError, ValueError):
        return False
    ext = str(extension or "").lower()
    if ext == "png":
        return prefix.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in {"jpg", "jpeg"}:
        return prefix.startswith(b"\xff\xd8\xff")
    if ext == "gif":
        return prefix.startswith((b"GIF87a", b"GIF89a"))
    if ext == "webp":
        return len(prefix) >= 12 and prefix[:4] == b"RIFF" and prefix[8:12] == b"WEBP"
    return False


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


def service_name_filter(value, fallback: str = "") -> str:
    return service_label(value, fallback)


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


def money_filter(value) -> str:
    if value in (None, ""):
        return ""
    return str(value)


def budget_label(value) -> str:
    def get(name: str):
        if isinstance(value, dict):
            return value.get(name)
        try:
            return value[name]
        except (KeyError, TypeError, IndexError):
            return None

    minimum = get("budget_min")
    maximum = get("budget_max")
    if minimum is not None and maximum is not None:
        return f"${int(minimum):,}-${int(maximum):,}"
    if minimum is not None:
        return f"${int(minimum):,}+"
    if maximum is not None:
        return f"Up to ${int(maximum):,}"
    return "Budget open"


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


def percentage_rate(numerator, denominator) -> int:
    try:
        top = int(numerator or 0)
        bottom = int(denominator or 0)
    except (TypeError, ValueError):
        return 0
    if bottom <= 0:
        return 0
    return round((top / bottom) * 100)


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
