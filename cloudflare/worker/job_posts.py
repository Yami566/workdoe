from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from service_policy import service_policy_error
from service_scope import clean_scope_answers, validate_scope_answers
from service_taxonomy import GROUP_BY_SLUG, SERVICE_BY_SLUG, service_selection

JOB_CATEGORIES = {
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
}
DMV_STATES = {"DC", "MD", "VA"}
JOB_TITLE_MAX_LENGTH = 90
JOB_CITY_MAX_LENGTH = 80
JOB_DESCRIPTION_MIN_LENGTH = 20
JOB_DESCRIPTION_MAX_LENGTH = 1200
JOB_BUDGET_MAX = 10_000_000
MAX_JOB_POST_BODY_BYTES = 8192
JOB_LOCATION_PRIVACY_NOTICE = "Approximate city or ZIP-level pins only."
DEFAULT_BID_LIMIT = 4
BID_WINDOW_DAYS = 7
BID_EXTENSION_DAYS = 7
PROJECT_SETTINGS = (
    {"value": "house", "label": "House", "description": "A house or townhouse"},
    {
        "value": "apartment-condo",
        "label": "Apartment or condo",
        "description": "A private unit in a shared building",
    },
    {
        "value": "business-space",
        "label": "Business or office",
        "description": "A shop, office, or workspace",
    },
    {
        "value": "shared-building",
        "label": "Shared building area",
        "description": "A lobby, hallway, or shared room",
    },
    {
        "value": "outdoor-area",
        "label": "Outdoor area",
        "description": "A yard, patio, or other outdoor space",
    },
    {"value": "other", "label": "Other", "description": "Another project setting"},
)
PROJECT_SETTING_BY_VALUE = {
    setting["value"]: setting for setting in PROJECT_SETTINGS
}


def _row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return getattr(row, key, default)


def _utc_datetime(value=None) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif value:
        raw = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            parsed = datetime.now(timezone.utc)
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _bid_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def default_bidding_closes_at(now=None) -> str:
    return _bid_iso(_utc_datetime(now) + timedelta(days=BID_WINDOW_DAYS))


def extended_bidding_closes_at(value, now=None) -> str:
    current = _utc_datetime(value)
    current_time = _utc_datetime(now)
    return _bid_iso(max(current, current_time) + timedelta(days=BID_EXTENSION_DAYS))


def bid_window(job, bid_count=None, now=None) -> dict:
    current_time = _utc_datetime(now)
    raw_limit = _row_value(job, "bid_limit", DEFAULT_BID_LIMIT)
    try:
        limit = max(1, min(int(raw_limit or DEFAULT_BID_LIMIT), 8))
    except (TypeError, ValueError):
        limit = DEFAULT_BID_LIMIT
    raw_used = bid_count if bid_count is not None else _row_value(job, "request_count", 0)
    try:
        used = max(0, int(raw_used or 0))
    except (TypeError, ValueError):
        used = 0
    deadline_value = _row_value(job, "bidding_closes_at", "")
    deadline = _utc_datetime(deadline_value) if deadline_value else current_time + timedelta(days=BID_WINDOW_DAYS)
    status = str(_row_value(job, "status", "open") or "open")
    remaining = max(0, limit - used)
    is_full = remaining == 0
    is_expired = deadline <= current_time
    accepting = status == "open" and not is_full and not is_expired
    if status != "open":
        state, availability_label = "closed", "Project closed"
    elif is_full:
        state, availability_label = "full", "Bid pool full"
    elif is_expired:
        state, availability_label = "expired", "Bidding closed"
    else:
        state = "open"
        availability_label = f"{remaining} bid {'slot' if remaining == 1 else 'slots'} left"
    return {
        "limit": limit,
        "used": used,
        "remaining": remaining,
        "is_full": is_full,
        "is_expired": is_expired,
        "accepting": accepting,
        "can_extend": status == "open" and is_expired and not is_full,
        "state": state,
        "usage_label": f"{used} of {limit} bids",
        "availability_label": availability_label,
        "deadline": _bid_iso(deadline),
        "deadline_label": deadline.strftime("%b %d at %I:%M %p UTC").replace(" 0", " "),
    }

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


class JobPostError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        self.field_errors = job_field_errors(errors)
        super().__init__("; ".join(errors))


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def parse_job_update_id(path: str) -> int:
    prefix = "/api/jobs/"
    suffix = "/update"
    if not path.startswith(prefix) or not path.endswith(suffix):
        raise JobPostError(["Unsupported job update route."])
    raw_id = path[len(prefix) : -len(suffix)].strip("/")
    if not raw_id.isdigit() or int(raw_id) < 1:
        raise JobPostError(["Unsupported job update route."])
    return int(raw_id)


def can_update_job(user, job) -> bool:
    if not user or not job:
        return False
    if row_value(user, "status") != "active":
        return False
    return (
        row_value(user, "role") == "client"
        and row_value(user, "id") == row_value(job, "client_id")
        and row_value(job, "status") != "hidden"
    )


def compact_spaces(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def digits_only(value: str | None, limit: int = 5) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())[:limit]


def normalize_project_setting(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in PROJECT_SETTING_BY_VALUE else ""


def project_setting_label(value: str | None) -> str:
    setting = PROJECT_SETTING_BY_VALUE.get(normalize_project_setting(value))
    return setting["label"] if setting else "Not specified"


def cleaned_job_payload(payload: dict) -> dict:
    selection = service_selection(
        payload.get("service_slug"),
        payload.get("service_group_slug"),
        payload.get("category"),
    )
    cleaned = {
        "title": compact_spaces(payload.get("title")),
        **selection,
        "project_setting": compact_spaces(payload.get("project_setting")).lower(),
        "desired_date": compact_spaces(payload.get("desired_date")),
        "city": compact_spaces(payload.get("city")),
        "state": compact_spaces(payload.get("state")).upper(),
        "zip_code": digits_only(payload.get("zip_code")),
        "description": (payload.get("description") or "").strip(),
        "budget_min": compact_spaces(payload.get("budget_min")),
        "budget_max": compact_spaces(payload.get("budget_max")),
        "service_policy_acknowledgement": compact_spaces(
            payload.get("service_policy_acknowledgement")
        ),
    }
    cleaned["scope_answers"] = clean_scope_answers(cleaned["service_slug"], payload)
    return cleaned


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def validate_job_payload(form: dict, today: date | None = None) -> list[str]:
    today = today or today_utc()
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
            parsed_date = date.fromisoformat(form["desired_date"])
        except ValueError:
            errors.append("Use a valid desired date.")
        else:
            if parsed_date < today:
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


def validate_budget_value(value: str, label: str, errors: list[str]) -> int | None:
    if not value:
        return None
    if not value.isdigit():
        errors.append(f"Use whole dollars for the {label} budget.")
        return None
    parsed = int(value)
    if parsed > JOB_BUDGET_MAX:
        errors.append(f"Keep the {label} budget at or below ${JOB_BUDGET_MAX:,}.")
        return None
    return parsed


def budget_database_value(value: str) -> int | None:
    return int(value) if value else None


def budget_label(row) -> str:
    minimum = row_value(row, "budget_min")
    maximum = row_value(row, "budget_max")
    if minimum is not None and maximum is not None:
        return f"${int(minimum):,}-${int(maximum):,}"
    if minimum is not None:
        return f"${int(minimum):,}+"
    if maximum is not None:
        return f"Up to ${int(maximum):,}"
    return str(row_value(row, "budget", "") or "Budget open")


def job_field_for_error(message: str) -> str:
    if "job title" in message:
        return "title"
    if "category" in message:
        return "category"
    if "six work families" in message:
        return "service_group_slug"
    if "service inside" in message:
        return "service_slug"
    if "project setting" in message:
        return "project_setting"
    if "desired date" in message:
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
    if "work" in message or "description" in message:
        return "description"
    if "service safety advisory" in message:
        return "service_policy_acknowledgement"
    return ""


def job_field_errors(errors: list[str]) -> dict[str, list[str]]:
    field_errors: dict[str, list[str]] = {}
    for message in errors:
        field = job_field_for_error(message)
        if field:
            field_errors.setdefault(field, []).append(message)
    return field_errors


def approximate_location(city: str, state: str, zip_code: str) -> tuple[float, float]:
    zip_clean = digits_only(zip_code)
    if zip_clean in DMV_ZIPS:
        return DMV_ZIPS[zip_clean][2], DMV_ZIPS[zip_clean][3]
    key = f"{city.strip().lower()} {state.strip().lower()}"
    if key in CITY_COORDS:
        return CITY_COORDS[key]
    return 38.9072, -77.0369


def job_post_payload(payload: dict, today: date | None = None) -> dict:
    if not isinstance(payload, dict):
        raise JobPostError(["Job payload must be a JSON object."])
    form = cleaned_job_payload(payload)
    errors = validate_job_payload(form, today=today)
    if errors:
        raise JobPostError(errors)
    lat, lng = approximate_location(form["city"], form["state"], form["zip_code"])
    return {
        **form,
        "approx_lat": lat,
        "approx_lng": lng,
        "location_privacy": JOB_LOCATION_PRIVACY_NOTICE,
    }
