from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median

from project_readiness import project_brief_readiness

DEFAULT_MINIMUM_ELIGIBLE_CONTRACTORS = 3
NO_MATCH_OR_CANCELLED_REASONS = frozenset(
    {"plans-changed", "no-qualified-bid", "scope-changed", "duplicate"}
)


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def count_value(row, key: str) -> int:
    try:
        return max(0, int(row_value(row, key, 0) or 0))
    except (TypeError, ValueError):
        return 0


def percentage_rate(numerator: int, denominator: int) -> int:
    return round((numerator / denominator) * 100) if denominator else 0


def project_week_start(value) -> str:
    text = str(value or "").strip()
    if not text:
        return "Unknown week"
    try:
        created = datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            created = datetime.strptime(text[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc).date()
        except ValueError:
            return text[:10] or "Unknown week"
    return (created - timedelta(days=created.weekday())).isoformat()


def parsed_timestamp(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def first_bid_minutes(created_at, first_bid_at):
    created = parsed_timestamp(created_at)
    first_bid = parsed_timestamp(first_bid_at)
    if not created or not first_bid:
        return None
    elapsed_seconds = (first_bid - created).total_seconds()
    if elapsed_seconds < 0:
        return None
    return round(elapsed_seconds / 60)


def median_minutes(values: list[int]):
    if not values:
        return None
    return round(median(values))


def response_time_label(minutes) -> str:
    if minutes is None:
        return "No bids"
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f} hr" if hours % 1 else f"{int(hours)} hr"
    days = hours / 24
    return f"{days:.1f} days" if days % 1 else f"{int(days)} days"


def pilot_cell_metrics(project_rows: list, supply_rows: list, as_of=None) -> dict:
    current_week_start = project_week_start(
        as_of or datetime.now(timezone.utc).date().isoformat()
    )
    supply_by_cell = {}
    for row in supply_rows:
        key = (
            str(row_value(row, "service_slug", "") or ""),
            str(row_value(row, "zone_slug", "") or ""),
        )
        supply_by_cell[key] = {
            "current_eligible_contractors": count_value(
                row, "current_eligible_contractors"
            ),
            "minimum_eligible_contractors": count_value(
                row, "minimum_eligible_contractors"
            )
            or DEFAULT_MINIMUM_ELIGIBLE_CONTRACTORS,
            "activation_status": str(
                row_value(row, "activation_status", "candidate") or "candidate"
            ),
            "service_name": str(
                row_value(row, "service_name", "") or "Unclassified service"
            ),
            "zone_name": str(
                row_value(row, "zone_name", "") or "Unclassified zone"
            ),
        }

    grouped = {}
    for row in project_rows:
        service_slug = str(row_value(row, "service_slug", "") or "")
        zone_slug = str(row_value(row, "service_zone_slug", "") or "")
        week_start = project_week_start(row_value(row, "created_at", ""))
        key = (week_start, service_slug, zone_slug)
        if key not in grouped:
            supply = supply_by_cell.get(
                (service_slug, zone_slug),
                {
                    "current_eligible_contractors": 0,
                    "minimum_eligible_contractors": DEFAULT_MINIMUM_ELIGIBLE_CONTRACTORS,
                    "activation_status": "candidate",
                },
            )
            grouped[key] = {
                **supply,
                "week_start": week_start,
                "service_slug": service_slug,
                "service_name": str(
                    row_value(row, "service_name", "")
                    or supply.get("service_name")
                    or "Unclassified service"
                ),
                "zone_slug": zone_slug,
                "zone_name": str(
                    row_value(row, "zone_name", "")
                    or supply.get("zone_name")
                    or "Unclassified zone"
                ),
                "published_projects": 0,
                "brief_ready_projects": 0,
                "projects_with_bids": 0,
                "total_bids": 0,
                "matched_projects": 0,
                "verified_completions": 0,
                "desired_date_projects": 0,
                "closed_projects": 0,
                "workdoe_match_closures": 0,
                "no_match_or_cancelled_projects": 0,
                "open_report_projects": 0,
                "_first_bid_minutes": [],
            }
        cell = grouped[key]
        bid_count = count_value(row, "bid_count")
        close_reason = str(row_value(row, "close_reason", "") or "")
        response_minutes = first_bid_minutes(
            row_value(row, "created_at", ""), row_value(row, "first_bid_at", "")
        )
        cell["published_projects"] += 1
        cell["brief_ready_projects"] += int(
            project_brief_readiness(row)["state"] == "ready"
        )
        cell["projects_with_bids"] += int(bid_count > 0)
        cell["total_bids"] += bid_count
        cell["matched_projects"] += int(count_value(row, "matched_count") > 0)
        cell["verified_completions"] += int(
            count_value(row, "verified_completion_count") > 0
        )
        cell["desired_date_projects"] += int(
            bool(str(row_value(row, "desired_date", "") or "").strip())
        )
        cell["closed_projects"] += int(row_value(row, "status", "") == "closed")
        cell["workdoe_match_closures"] += int(close_reason == "workdoe-match")
        cell["no_match_or_cancelled_projects"] += int(
            close_reason in NO_MATCH_OR_CANCELLED_REASONS
        )
        cell["open_report_projects"] += int(
            count_value(row, "open_report_count") > 0
        )
        if response_minutes is not None:
            cell["_first_bid_minutes"].append(response_minutes)

    for (service_slug, zone_slug), supply in supply_by_cell.items():
        if supply["activation_status"] != "active":
            continue
        key = (current_week_start, service_slug, zone_slug)
        if key in grouped:
            continue
        grouped[key] = {
            **supply,
            "week_start": current_week_start,
            "service_slug": service_slug,
            "zone_slug": zone_slug,
            "published_projects": 0,
            "brief_ready_projects": 0,
            "projects_with_bids": 0,
            "total_bids": 0,
            "matched_projects": 0,
            "verified_completions": 0,
            "desired_date_projects": 0,
            "closed_projects": 0,
            "workdoe_match_closures": 0,
            "no_match_or_cancelled_projects": 0,
            "open_report_projects": 0,
            "_first_bid_minutes": [],
        }

    cells = []
    for cell in grouped.values():
        response_samples = cell.pop("_first_bid_minutes")
        cell["first_bid_samples"] = len(response_samples)
        cell["median_first_bid_minutes"] = median_minutes(response_samples)
        cell["median_first_bid_label"] = response_time_label(
            cell["median_first_bid_minutes"]
        )
        cell["zero_bid_projects"] = (
            cell["published_projects"] - cell["projects_with_bids"]
        )
        cell["brief_ready_rate"] = percentage_rate(
            cell["brief_ready_projects"], cell["published_projects"]
        )
        cell["bid_coverage_rate"] = percentage_rate(
            cell["projects_with_bids"], cell["published_projects"]
        )
        cell["qualified_match_rate"] = percentage_rate(
            cell["matched_projects"], cell["published_projects"]
        )
        cell["verified_completion_rate"] = percentage_rate(
            cell["verified_completions"], cell["matched_projects"]
        )
        cell["workdoe_close_rate"] = percentage_rate(
            cell["workdoe_match_closures"], cell["closed_projects"]
        )
        cell["open_report_rate"] = percentage_rate(
            cell["open_report_projects"], cell["published_projects"]
        )
        cell["supply_gap"] = (
            cell["current_eligible_contractors"]
            < cell["minimum_eligible_contractors"]
        )
        if cell["supply_gap"]:
            cell["state"] = "supply-gap"
            cell["state_label"] = "Supply gap"
        elif not cell["published_projects"]:
            cell["state"] = "no-demand"
            cell["state_label"] = "No projects"
        elif cell["zero_bid_projects"]:
            cell["state"] = "needs-response"
            cell["state_label"] = "Needs response"
        elif cell["verified_completions"]:
            cell["state"] = "verified"
            cell["state_label"] = "Verified work"
        elif cell["matched_projects"]:
            cell["state"] = "matched"
            cell["state_label"] = "Matched"
        else:
            cell["state"] = "receiving-bids"
            cell["state_label"] = "Receiving bids"
        cells.append(cell)

    cells.sort(key=lambda cell: (cell["service_name"], cell["zone_name"]))
    cells.sort(key=lambda cell: cell["week_start"], reverse=True)
    summary = {
        "tracked_cells": len(cells),
        "observed_cells": sum(1 for cell in cells if cell["published_projects"]),
        "active_zero_project_cells": sum(
            1
            for cell in cells
            if cell["activation_status"] == "active"
            and not cell["published_projects"]
        ),
        "published_projects": sum(cell["published_projects"] for cell in cells),
        "brief_ready_projects": sum(
            cell["brief_ready_projects"] for cell in cells
        ),
        "projects_with_bids": sum(cell["projects_with_bids"] for cell in cells),
        "matched_projects": sum(cell["matched_projects"] for cell in cells),
        "verified_completions": sum(
            cell["verified_completions"] for cell in cells
        ),
        "desired_date_projects": sum(
            cell["desired_date_projects"] for cell in cells
        ),
        "closed_projects": sum(cell["closed_projects"] for cell in cells),
        "workdoe_match_closures": sum(
            cell["workdoe_match_closures"] for cell in cells
        ),
        "no_match_or_cancelled_projects": sum(
            cell["no_match_or_cancelled_projects"] for cell in cells
        ),
        "open_report_projects": sum(
            cell["open_report_projects"] for cell in cells
        ),
        "zero_bid_projects": sum(cell["zero_bid_projects"] for cell in cells),
        "supply_gap_cells": sum(1 for cell in cells if cell["supply_gap"]),
    }
    response_samples = [
        first_bid_minutes(
            row_value(row, "created_at", ""), row_value(row, "first_bid_at", "")
        )
        for row in project_rows
    ]
    response_samples = [value for value in response_samples if value is not None]
    summary["first_bid_samples"] = len(response_samples)
    summary["median_first_bid_minutes"] = median_minutes(response_samples)
    summary["median_first_bid_label"] = response_time_label(
        summary["median_first_bid_minutes"]
    )
    summary["qualified_match_rate"] = percentage_rate(
        summary["matched_projects"], summary["published_projects"]
    )
    summary["verified_completion_rate"] = percentage_rate(
        summary["verified_completions"], summary["matched_projects"]
    )
    summary["workdoe_close_rate"] = percentage_rate(
        summary["workdoe_match_closures"], summary["closed_projects"]
    )
    summary["open_report_rate"] = percentage_rate(
        summary["open_report_projects"], summary["published_projects"]
    )
    return {"cells": cells, "summary": summary}
