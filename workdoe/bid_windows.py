from __future__ import annotations

from datetime import datetime, timedelta, timezone

DEFAULT_BID_LIMIT = 4
BID_WINDOW_DAYS = 7
BID_EXTENSION_DAYS = 7


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


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def default_bidding_closes_at(now=None) -> str:
    return _iso(_utc_datetime(now) + timedelta(days=BID_WINDOW_DAYS))


def extended_bidding_closes_at(value, now=None) -> str:
    current = _utc_datetime(value)
    current_time = _utc_datetime(now)
    return _iso(max(current, current_time) + timedelta(days=BID_EXTENSION_DAYS))


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
    has_approved_match = bool(_row_value(job, "has_approved_match", False))
    remaining = max(0, limit - used)
    is_full = remaining == 0
    is_expired = deadline <= current_time
    accepting = (
        status == "open" and not has_approved_match and not is_full and not is_expired
    )
    if status != "open":
        state = "closed"
        availability_label = "Project closed"
    elif has_approved_match:
        state = "matched"
        availability_label = "Contractor chosen"
    elif is_full:
        state = "full"
        availability_label = "Bid pool full"
    elif is_expired:
        state = "expired"
        availability_label = "Bidding closed"
    else:
        state = "open"
        availability_label = f"{remaining} bid {'slot' if remaining == 1 else 'slots'} left"
    deadline_label = deadline.strftime("%b %d at %I:%M %p UTC").replace(" 0", " ")
    return {
        "limit": limit,
        "used": used,
        "remaining": remaining,
        "is_full": is_full,
        "is_expired": is_expired,
        "accepting": accepting,
        "can_extend": (
            status == "open" and not has_approved_match and is_expired and not is_full
        ),
        "state": state,
        "usage_label": f"{used} of {limit} bids",
        "availability_label": availability_label,
        "deadline": _iso(deadline),
        "deadline_label": deadline_label,
    }
