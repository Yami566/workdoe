from __future__ import annotations


PROJECT_BRIEF_SIGNAL_TOTAL = 6
MIN_SUBSTANTIVE_DESCRIPTION_LENGTH = 20
MIN_SCOPE_ANSWER_COUNT = 2


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return getattr(row, key, default)


def count_value(value) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def has_budget_signal(row) -> bool:
    for key in ("budget_min", "budget_max"):
        value = row_value(row, key)
        if value in (None, ""):
            continue
        try:
            if float(value) >= 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def project_brief_readiness(
    row,
    scope_answer_count: int | None = None,
    photo_count: int | None = None,
) -> dict:
    description = " ".join(str(row_value(row, "description", "") or "").split())
    resolved_scope_count = count_value(
        row_value(row, "scope_answer_count", 0)
        if scope_answer_count is None
        else scope_answer_count
    )
    resolved_photo_count = count_value(
        row_value(row, "photo_count", 0) if photo_count is None else photo_count
    )
    signals = [
        {
            "key": "service",
            "label": "Service chosen",
            "complete": bool(str(row_value(row, "service_slug", "") or "").strip()),
        },
        {
            "key": "description",
            "label": "Brief written",
            "complete": len(description) >= MIN_SUBSTANTIVE_DESCRIPTION_LENGTH,
        },
        {
            "key": "scope",
            "label": "Quote details",
            "complete": resolved_scope_count >= MIN_SCOPE_ANSWER_COUNT,
        },
        {
            "key": "setting",
            "label": "Project setting",
            "complete": bool(str(row_value(row, "project_setting", "") or "").strip()),
        },
        {
            "key": "timing",
            "label": "Desired timing",
            "complete": bool(str(row_value(row, "desired_date", "") or "").strip()),
        },
        {
            "key": "budget_or_photo",
            "label": "Budget or photo",
            "complete": has_budget_signal(row) or resolved_photo_count > 0,
        },
    ]
    score = sum(1 for signal in signals if signal["complete"])
    state = "ready" if score >= 5 else "building" if score >= 3 else "thin"
    return {
        "score": score,
        "total": PROJECT_BRIEF_SIGNAL_TOTAL,
        "label": f"Brief {score} of {PROJECT_BRIEF_SIGNAL_TOTAL}",
        "state": state,
        "signals": signals,
    }
