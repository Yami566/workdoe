from __future__ import annotations

import re


PROJECT_TEMPLATE_LIMIT = 12
PROJECT_TEMPLATE_NAME_MAX_LENGTH = 60
PROJECT_TEMPLATE_PATH_RE = re.compile(r"^/api/client/templates/([1-9][0-9]*)/delete$")


class ProjectTemplateError(ValueError):
    def __init__(self, errors: list[str], field_errors: dict[str, list[str]] | None = None):
        self.errors = errors
        self.field_errors = field_errors or {}
        super().__init__(" ".join(errors))


def row_value(row, key: str, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return getattr(row, key, default)


def compact_spaces(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def project_template_request_payload(payload) -> dict[str, str | int]:
    name = compact_spaces(payload.get("name"))
    raw_source_id = str(payload.get("source_job_id") or "").strip()
    errors: list[str] = []
    field_errors: dict[str, list[str]] = {}
    if not name:
        errors.append("Add a template name.")
        field_errors["name"] = ["Add a template name."]
    elif len(name) > PROJECT_TEMPLATE_NAME_MAX_LENGTH:
        message = f"Keep the template name to {PROJECT_TEMPLATE_NAME_MAX_LENGTH} characters."
        errors.append(message)
        field_errors["name"] = [message]
    if not raw_source_id.isdigit() or int(raw_source_id) <= 0:
        errors.append("Choose one of your projects.")
        field_errors["source_job_id"] = ["Choose one of your projects."]
    if errors:
        raise ProjectTemplateError(errors, field_errors)
    return {"name": name, "source_job_id": int(raw_source_id)}


def project_template_values(name: str, job_form: dict) -> dict:
    return {
        "name": name,
        "source_job_id": job_form.get("id"),
        "service_group_slug": str(job_form.get("service_group_slug") or ""),
        "service_slug": str(job_form.get("service_slug") or ""),
        "category": str(job_form.get("category") or "Other"),
        "title": str(job_form.get("title") or ""),
        "description": str(job_form.get("description") or ""),
        "project_setting": str(job_form.get("project_setting") or ""),
        "budget_min": job_form.get("budget_min") or None,
        "budget_max": job_form.get("budget_max") or None,
    }


def project_template_response(row) -> dict:
    return {
        "id": int(row_value(row, "id", 0) or 0),
        "name": str(row_value(row, "name", "") or ""),
        "source_job_id": row_value(row, "source_job_id"),
        "service_group_slug": str(row_value(row, "service_group_slug", "") or ""),
        "service_slug": str(row_value(row, "service_slug", "") or ""),
        "category": str(row_value(row, "category", "Other") or "Other"),
        "title": str(row_value(row, "title", "") or ""),
        "description": str(row_value(row, "description", "") or ""),
        "project_setting": str(row_value(row, "project_setting", "") or ""),
        "budget_min": row_value(row, "budget_min"),
        "budget_max": row_value(row, "budget_max"),
        "created_at": str(row_value(row, "created_at", "") or ""),
        "updated_at": str(row_value(row, "updated_at", "") or ""),
        "use_url": f"/jobs/new?template={int(row_value(row, 'id', 0) or 0)}",
    }


def project_template_job_form(row) -> dict[str, str]:
    return {
        "service_group_slug": str(row_value(row, "service_group_slug", "") or ""),
        "service_slug": str(row_value(row, "service_slug", "") or ""),
        "category": str(row_value(row, "category", "Other") or "Other"),
        "title": str(row_value(row, "title", "") or ""),
        "project_setting": str(row_value(row, "project_setting", "") or ""),
        "city": "",
        "state": "DC",
        "zip_code": "",
        "desired_date": "",
        "description": str(row_value(row, "description", "") or ""),
        "budget_min": str(row_value(row, "budget_min", "") or ""),
        "budget_max": str(row_value(row, "budget_max", "") or ""),
    }


def parse_project_template_delete_path(path: str) -> int:
    match = PROJECT_TEMPLATE_PATH_RE.fullmatch(path or "")
    if not match:
        raise ProjectTemplateError(["Unsupported project template route."])
    return int(match.group(1))
