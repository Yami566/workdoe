from __future__ import annotations

from public_job_query import public_viewport_contains
from service_taxonomy import service_selection

DEMO_PROJECTS = [
    {
        "id": "demo-01",
        "title": "Power wash brick rowhouse exterior",
        "category": "Power washing",
        "city": "Washington",
        "state": "DC",
        "description": "Clean the front brick, entry steps, and rear patio of a two-story rowhouse. Water access is available outside.",
        "budget": "$240-$340",
        "desired_date": "2026-08-20",
        "approx_lat": 38.8832,
        "approx_lng": -76.9977,
        "created_at": "2026-08-15T14:30:00+00:00",
    },
    {
        "id": "demo-02",
        "title": "Clean windows on three-level townhouse",
        "category": "Window cleaning",
        "city": "Arlington",
        "state": "VA",
        "description": "Interior and exterior cleaning for 18 windows, including two upper-level windows above the front entry.",
        "budget": "$220-$320",
        "desired_date": "2026-08-22",
        "approx_lat": 38.8799,
        "approx_lng": -77.1068,
        "created_at": "2026-08-15T13:50:00+00:00",
    },
    {
        "id": "demo-03",
        "title": "Prep and stain backyard deck",
        "category": "Decks and patios",
        "city": "Bethesda",
        "state": "MD",
        "description": "Wash and stain a 12-by-18-foot wood deck with stairs. Homeowner will select and provide the stain.",
        "budget": "$650-$900",
        "desired_date": "2026-08-28",
        "approx_lat": 38.9847,
        "approx_lng": -77.0947,
        "created_at": "2026-08-15T13:10:00+00:00",
    },
    {
        "id": "demo-04",
        "title": "Clear gutters and check downspouts",
        "category": "General handyman",
        "city": "Silver Spring",
        "state": "MD",
        "description": "Clear gutters on a two-story detached home and confirm four downspouts are draining away from the foundation.",
        "budget": "$180-$260",
        "desired_date": "2026-08-19",
        "approx_lat": 38.9907,
        "approx_lng": -77.0261,
        "created_at": "2026-08-15T12:35:00+00:00",
    },
    {
        "id": "demo-05",
        "title": "Repair leaning privacy fence section",
        "category": "Fencing",
        "city": "Alexandria",
        "state": "VA",
        "description": "Reset two posts and replace six damaged cedar pickets along a side-yard privacy fence.",
        "budget": "$420-$620",
        "desired_date": "2026-08-25",
        "approx_lat": 38.8048,
        "approx_lng": -77.0469,
        "created_at": "2026-08-15T11:55:00+00:00",
    },
    {
        "id": "demo-06",
        "title": "Front-yard cleanup and fresh mulch",
        "category": "Landscaping",
        "city": "Rockville",
        "state": "MD",
        "description": "Edge two garden beds, remove weeds, trim small shrubs, and spread approximately two cubic yards of mulch.",
        "budget": "$380-$520",
        "desired_date": "2026-08-23",
        "approx_lat": 39.0839,
        "approx_lng": -77.1528,
        "created_at": "2026-08-15T11:15:00+00:00",
    },
    {
        "id": "demo-07",
        "title": "Patch and paint ceiling drywall",
        "category": "Drywall",
        "city": "Falls Church",
        "state": "VA",
        "description": "Repair a two-foot ceiling opening left after a plumbing inspection, then prime and blend the paint.",
        "budget": "$350-$500",
        "desired_date": "2026-08-21",
        "approx_lat": 38.8823,
        "approx_lng": -77.1711,
        "created_at": "2026-08-15T10:40:00+00:00",
    },
    {
        "id": "demo-08",
        "title": "Remove old sofa and basement shelving",
        "category": "Junk removal",
        "city": "Hyattsville",
        "state": "MD",
        "description": "Haul away one sectional sofa and disassembled wood shelving from a walk-out basement. Parking is available in the driveway.",
        "budget": "$190-$290",
        "desired_date": "2026-08-18",
        "approx_lat": 38.9559,
        "approx_lng": -76.9455,
        "created_at": "2026-08-15T10:05:00+00:00",
    },
    {
        "id": "demo-09",
        "title": "Install two ceiling fans",
        "category": "Electrical",
        "city": "Washington",
        "state": "DC",
        "description": "Replace existing ceiling lights with owner-provided fans in two bedrooms. Existing wall switches will remain.",
        "budget": "$300-$450",
        "desired_date": "2026-08-27",
        "approx_lat": 38.8766,
        "approx_lng": -77.0036,
        "created_at": "2026-08-15T09:25:00+00:00",
    },
    {
        "id": "demo-10",
        "title": "Reset loose patio pavers",
        "category": "Concrete and masonry",
        "city": "McLean",
        "state": "VA",
        "description": "Lift and level roughly 40 square feet of settling pavers near the patio door and refresh the joint sand.",
        "budget": "$480-$700",
        "desired_date": "2026-08-29",
        "approx_lat": 38.9339,
        "approx_lng": -77.1773,
        "created_at": "2026-08-15T08:50:00+00:00",
    },
    {
        "id": "demo-11",
        "title": "Seasonal HVAC tune-up",
        "category": "HVAC",
        "city": "Largo",
        "state": "MD",
        "description": "Inspect and service one residential heat-pump system before fall, including filter and condensate-line checks.",
        "budget": "$160-$240",
        "desired_date": "2026-09-02",
        "approx_lat": 38.8976,
        "approx_lng": -76.8303,
        "created_at": "2026-08-15T08:10:00+00:00",
    },
    {
        "id": "demo-12",
        "title": "Paint two bedrooms and trim",
        "category": "Painting",
        "city": "Columbia",
        "state": "MD",
        "description": "Prep and paint two average-size bedrooms, including baseboards and door trim. Rooms will be empty on arrival.",
        "budget": "$900-$1,300",
        "desired_date": "2026-09-05",
        "approx_lat": 39.2037,
        "approx_lng": -76.8610,
        "created_at": "2026-08-15T07:35:00+00:00",
    },
    {
        "id": "demo-13",
        "title": "Install kitchen tile backsplash",
        "category": "Flooring",
        "city": "Fairfax",
        "state": "VA",
        "description": "Install approximately 28 square feet of owner-provided subway tile and finish with light-gray grout.",
        "budget": "$700-$950",
        "desired_date": "2026-08-31",
        "approx_lat": 38.8462,
        "approx_lng": -77.3064,
        "created_at": "2026-08-15T07:00:00+00:00",
    },
    {
        "id": "demo-14",
        "title": "Trim branches above driveway",
        "category": "Tree service",
        "city": "Takoma Park",
        "state": "MD",
        "description": "Remove several small-to-medium branches hanging over a shared driveway and haul away all debris.",
        "budget": "$550-$800",
        "desired_date": "2026-08-26",
        "approx_lat": 38.9779,
        "approx_lng": -77.0075,
        "created_at": "2026-08-15T06:30:00+00:00",
    },
    {
        "id": "demo-15",
        "title": "Wash storefront windows before opening",
        "category": "Commercial maintenance",
        "city": "Washington",
        "state": "DC",
        "description": "Clean street-level interior and exterior glass for a small retail storefront before 9 a.m.",
        "budget": "$140-$220",
        "desired_date": "2026-08-24",
        "approx_lat": 38.9097,
        "approx_lng": -77.0654,
        "created_at": "2026-08-15T06:00:00+00:00",
    },
]


def compact_spaces(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def demo_projects_for_filters(
    filters: dict[str, str] | None = None,
    viewport: dict[str, float] | None = None,
) -> list[dict]:
    active = filters or {}
    category = compact_spaces(active.get("category"))
    family = compact_spaces(active.get("family"))
    service_slug = compact_spaces(active.get("service"))
    query = compact_spaces(active.get("q")).lower()
    projects = []
    for project in DEMO_PROJECTS:
        service = service_selection("", "", project["category"])
        projects.append(
            dict(
                project,
                is_demo=True,
                photo_count=0,
                service_group_slug=service["service_group_slug"],
                service_slug=service["service_slug"],
            )
        )
    if category:
        projects = [project for project in projects if project["category"] == category]
    if family:
        projects = [
            project for project in projects if project["service_group_slug"] == family
        ]
    if service_slug:
        projects = [
            project for project in projects if project["service_slug"] == service_slug
        ]
    if query:
        projects = [
            project
            for project in projects
            if query
            in " ".join(
                (
                    project["title"],
                    project["category"],
                    project["city"],
                    project["state"],
                    project["description"],
                )
            ).lower()
        ]
    if viewport:
        projects = [
            project
            for project in projects
            if public_viewport_contains(
                viewport, project.get("approx_lat"), project.get("approx_lng")
            )
        ]
    sort = active.get("sort", "newest")
    if sort == "soonest":
        projects.sort(key=lambda project: (project["desired_date"], project["title"]))
    elif sort == "city":
        projects.sort(key=lambda project: (project["city"], project["title"]))
    else:
        projects.sort(key=lambda project: project["created_at"], reverse=True)
    return projects


def guest_project_rows(
    rows: list,
    filters: dict[str, str] | None = None,
    limit: int | None = None,
    viewport: dict[str, float] | None = None,
    include_demo: bool = True,
) -> list:
    live_rows = list(rows)
    demo_rows = demo_projects_for_filters(filters, viewport) if include_demo else []
    if limit is None:
        return live_rows + demo_rows
    capped_limit = max(0, int(limit))
    live_rows = live_rows[:capped_limit]
    return live_rows + demo_rows[: max(0, capped_limit - len(live_rows))]
