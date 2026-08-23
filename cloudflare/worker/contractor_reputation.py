from __future__ import annotations

COMPLETION_POINTS = 100
COMPLETION_MILESTONES = (
    {"key": "first-finish", "label": "First finish", "threshold": 1},
    {"key": "steady-provider", "label": "Steady provider", "threshold": 3},
    {"key": "local-regular", "label": "Local regular", "threshold": 10},
    {"key": "proven-partner", "label": "Proven partner", "threshold": 25},
)


def nonnegative_count(value) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def contractor_reputation(
    verified_completions=0,
    source_checked_credentials=0,
    source_checked_licenses=0,
) -> dict:
    completions = nonnegative_count(verified_completions)
    credentials = nonnegative_count(source_checked_credentials)
    licenses = min(credentials, nonnegative_count(source_checked_licenses))
    achieved = [
        dict(milestone)
        for milestone in COMPLETION_MILESTONES
        if completions >= milestone["threshold"]
    ]
    current = achieved[-1] if achieved else None
    next_milestone = next(
        (
            dict(milestone)
            for milestone in COMPLETION_MILESTONES
            if completions < milestone["threshold"]
        ),
        None,
    )
    current_threshold = current["threshold"] if current else 0
    if next_milestone:
        progress_value = completions - current_threshold
        progress_max = next_milestone["threshold"] - current_threshold
        next_milestone.update(
            {
                "remaining": next_milestone["threshold"] - completions,
                "progress_value": progress_value,
                "progress_max": progress_max,
            }
        )
    else:
        progress_value = 1
        progress_max = 1

    credential_signals = []
    if licenses:
        credential_signals.append(
            {
                "key": "license-source-checked",
                "label": "License source checked",
                "qualifier": "Current public record",
            }
        )
    elif credentials:
        credential_signals.append(
            {
                "key": "record-source-checked",
                "label": "Record source checked",
                "qualifier": "Current public record",
            }
        )

    return {
        "completion_points": completions * COMPLETION_POINTS,
        "verified_completions": completions,
        "source_checked_credentials": credentials,
        "source_checked_licenses": licenses,
        "level_label": current["label"] if current else "New to Workdoe",
        "current_milestone": current,
        "achieved_milestones": achieved,
        "next_milestone": next_milestone,
        "progress_value": progress_value,
        "progress_max": progress_max,
        "credential_signals": credential_signals,
        "ranking_effect": "none",
        "method_label": "100 points per mutually confirmed Workdoe project",
    }
