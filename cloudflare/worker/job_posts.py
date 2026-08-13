from __future__ import annotations

from datetime import date, datetime, timezone


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
MAX_JOB_POST_BODY_BYTES = 8192
JOB_LOCATION_PRIVACY_NOTICE = "Approximate city or ZIP-level pins only."

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
        super().__init__("; ".join(errors))


def compact_spaces(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def digits_only(value: str | None, limit: int = 5) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())[:limit]


def cleaned_job_payload(payload: dict) -> dict[str, str]:
    return {
        "title": compact_spaces(payload.get("title")),
        "category": compact_spaces(payload.get("category")),
        "desired_date": compact_spaces(payload.get("desired_date")),
        "city": compact_spaces(payload.get("city")),
        "state": compact_spaces(payload.get("state")).upper(),
        "zip_code": digits_only(payload.get("zip_code")),
        "description": (payload.get("description") or "").strip(),
    }


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def validate_job_payload(form: dict[str, str], today: date | None = None) -> list[str]:
    today = today or today_utc()
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
            parsed_date = date.fromisoformat(form["desired_date"])
        except ValueError:
            errors.append("Use a valid desired date.")
        else:
            if parsed_date < today:
                errors.append("Choose today or a future desired date.")
    return errors


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
