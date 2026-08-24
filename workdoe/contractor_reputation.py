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
    if next_milestone:
        progress_value = completions
        progress_max = next_milestone["threshold"]
        next_milestone.update(
            {
                "remaining": next_milestone["threshold"] - completions,
                "progress_value": progress_value,
                "progress_max": progress_max,
            }
        )
    else:
        progress_value = completions
        progress_max = max(COMPLETION_MILESTONES[-1]["threshold"], completions)

    current_key = current["key"] if current else ""
    next_key = next_milestone["key"] if next_milestone else ""
    milestones = []
    for milestone in COMPLETION_MILESTONES:
        earned = completions >= milestone["threshold"]
        state = "earned" if earned else "locked"
        if milestone["key"] == current_key:
            state = "current"
        elif milestone["key"] == next_key:
            state = "next"
        milestones.append(
            {
                **milestone,
                "earned": earned,
                "points": milestone["threshold"] * COMPLETION_POINTS,
                "state": state,
            }
        )

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

    if licenses:
        trust_record = {
            "state": "license-source-checked",
            "label": (
                f"{licenses} license source checked"
                if licenses == 1
                else f"{licenses} licenses source checked"
            ),
            "qualifier": "Current public record",
        }
    elif credentials:
        trust_record = {
            "state": "record-source-checked",
            "label": (
                f"{credentials} record source checked"
                if credentials == 1
                else f"{credentials} records source checked"
            ),
            "qualifier": "Current public record",
        }
    else:
        trust_record = {
            "state": "none",
            "label": "No source-checked record",
            "qualifier": "Optional trust record",
        }

    return {
        "completion_points": completions * COMPLETION_POINTS,
        "verified_completions": completions,
        "source_checked_credentials": credentials,
        "source_checked_licenses": licenses,
        "level_label": current["label"] if current else "New to Workdoe",
        "current_milestone": current,
        "achieved_milestones": achieved,
        "milestones": milestones,
        "next_milestone": next_milestone,
        "progress_value": progress_value,
        "progress_max": progress_max,
        "credential_signals": credential_signals,
        "trust_record": trust_record,
        "ranking_effect": "none",
        "method_label": "100 points per mutually confirmed Workdoe project",
    }


def contractor_match_provider(
    contractor_id,
    contractor_name,
    job_id,
    verified_completions=0,
    source_checked_credentials=0,
    source_checked_licenses=0,
) -> dict:
    provider_id = nonnegative_count(contractor_id)
    project_id = nonnegative_count(job_id)
    profile_url = f"/contractors/{provider_id}" if provider_id else ""
    if profile_url and project_id:
        profile_url = f"{profile_url}?job_id={project_id}"
    return {
        "id": provider_id,
        "name": str(contractor_name or "Contractor"),
        "profile_url": profile_url,
        "reputation": contractor_reputation(
            verified_completions,
            source_checked_credentials,
            source_checked_licenses,
        ),
    }
