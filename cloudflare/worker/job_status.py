from __future__ import annotations


JOB_STATUS_ACTIONS = {"close": "closed", "reopen": "open"}
JOB_STATUS_EVENTS = {"closed": "job-closed", "open": "job-reopened"}


class JobStatusError(ValueError):
    pass


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def parse_job_status_path(path: str) -> tuple[int, str, str]:
    prefix = "/api/jobs/"
    if not path.startswith(prefix):
        raise JobStatusError("Unsupported job status route.")
    parts = [part for part in path[len(prefix) :].split("/") if part]
    if len(parts) != 2:
        raise JobStatusError("Unsupported job status route.")
    raw_id, action = parts
    if not raw_id.isdigit() or int(raw_id) < 1:
        raise JobStatusError("Unsupported job status route.")
    if action not in JOB_STATUS_ACTIONS:
        raise JobStatusError("Unsupported job status route.")
    return int(raw_id), action, JOB_STATUS_ACTIONS[action]


def can_update_job_status(user, job) -> bool:
    if not user or not job:
        return False
    if row_value(user, "status") != "active":
        return False
    return row_value(user, "role") == "client" and row_value(user, "id") == row_value(job, "client_id")


def job_status_event_type(status: str) -> str:
    return JOB_STATUS_EVENTS.get(status, "job-status-updated")


def job_status_response(job_id: int, status: str) -> dict:
    return {
        "ok": True,
        "job_id": job_id,
        "status": status,
        "url": f"/client/jobs/{job_id}",
    }
