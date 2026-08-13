from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "workdoe-launch-handoff.local.md"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from github_deploy_dispatch import build_dispatch_plan  # noqa: E402
from workdoe_launch_doctor import DEFAULT_LOCAL_URL, build_doctor  # noqa: E402


SECRET_VALUE_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk_(?:live|test)_[A-Za-z0-9_]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
]
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PRIVATE_KEY|API_KEY|JWT_KEY)[A-Z0-9_]*)=([^\s`]+)"
)


def redact_text(value: str) -> str:
    redacted = SECRET_ASSIGNMENT_PATTERN.sub(r"\1=<redacted>", value)
    for pattern in SECRET_VALUE_PATTERNS:
        redacted = pattern.sub("<redacted>", redacted)
    return redacted


def redact_payload(value):
    if isinstance(value, dict):
        return {key: redact_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def md_escape(value: str) -> str:
    return redact_text(value).replace("|", "\\|").replace("\n", " ")


def checkbox(done: bool) -> str:
    return "[x]" if done else "[ ]"


ACTION_GROUPS = [
    (
        "GitHub Deployment Secrets",
        lambda action: action.startswith("gh secret set")
        or action == "npm run github:release:status",
    ),
    (
        "Cloudflare Account And Resources",
        lambda action: action.endswith("wrangler.cmd login")
        or action in {"npm run cf:resources:plan", "npm run cf:resources:apply"},
    ),
    (
        "Worker Secrets And Clerk",
        lambda action: "wrangler.cmd secret put" in action
        or action in {"npm run cf:secrets:evidence", "npm run cf:clerk:proof"},
    ),
    (
        "DNS And Domain Activation",
        lambda action: action == "npm run launch:dns"
        or action.startswith("Deploy the Worker custom domain route")
        or action == "confirm workdoe.com DNS in Cloudflare",
    ),
    (
        "Final Deployment And Smoke",
        lambda action: action
        in {
            "npm run cf:deploy:plan",
            "npm run github:deploy:plan",
            "npm run github:deploy",
            "npm run launch:smoke",
            "npm run launch:smoke:strict",
            "npm run launch:doctor:live",
        },
    ),
]


def action_group_name(action: str) -> str:
    for name, predicate in ACTION_GROUPS:
        if predicate(action):
            return name
    return "Other"


def group_actions(actions: list[str]) -> list[dict]:
    groups: dict[str, list[str]] = {name: [] for name, _ in ACTION_GROUPS}
    groups["Other"] = []
    for action in actions:
        groups[action_group_name(action)].append(action)
    return [
        {"name": name, "actions": values}
        for name, values in groups.items()
        if values
    ]


def build_handoff_payload(
    repo_root: Path = REPO_ROOT,
    *,
    local_url: str = DEFAULT_LOCAL_URL,
) -> dict:
    doctor = build_doctor(repo_root, live=True, local_url=local_url)
    dispatch = build_dispatch_plan(repo_root, local_url=local_url)
    blockers = sorted(set(list(doctor["blockers"]) + list(dispatch["blockers"])))
    next_actions = []
    for action in list(doctor["next_actions"]) + [
        "npm run launch:dns",
        "npm run github:deploy:plan",
        "npm run github:deploy",
        "npm run launch:smoke",
        "npm run launch:smoke:strict",
    ]:
        if action and action not in next_actions:
            next_actions.append(action)

    return redact_payload({
        "service": "workdoe",
        "domain": "workdoe.com",
        "ready": bool(doctor["ready"] and dispatch["ready_to_dispatch"]),
        "safe_to_share": True,
        "contains_secret_values": False,
        "doctor": doctor,
        "dispatch": {
            "ready_to_dispatch": dispatch["ready_to_dispatch"],
            "repository": dispatch["repository"],
            "workflow": dispatch["workflow"],
            "ref": dispatch["ref"],
            "command_text": dispatch["command_text"],
            "git": dispatch["git"],
        },
        "blockers": blockers,
        "next_actions": next_actions,
        "action_groups": group_actions(next_actions),
        "private_local_files": [
            ".env",
            "cloudflare/.dev.vars",
            "cloudflare-secret-list.local.json",
            "clerk-proxy-proof.local.json",
        ],
    })


def render_markdown(payload: dict) -> str:
    status = "Ready for guarded GitHub dispatch" if payload["ready"] else "Blocked before production dispatch"
    lines = [
        "# Workdoe Launch Handoff",
        "",
        f"Status: {status}",
        "",
        "This handoff is generated from local and live release gates. It includes secret names and command names, but not secret values.",
        "",
        "## Gate Snapshot",
        "",
        "| Gate | Status | Summary | Next |",
        "| --- | --- | --- | --- |",
    ]
    for phase in payload["doctor"]["phases"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(phase["name"]),
                    md_escape(phase["status"]),
                    md_escape(phase["summary"]),
                    md_escape(phase.get("next_command", "")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Repository Gate",
            "",
            f"- Branch: `{md_escape(payload['dispatch']['git'].get('branch', ''))}`",
            f"- Clean worktree: `{payload['dispatch']['git'].get('clean')}`",
            f"- Synced with upstream: `{payload['dispatch']['git'].get('synced_with_upstream')}`",
            f"- Dispatch workflow: `{md_escape(payload['dispatch']['workflow'])}` on `{md_escape(payload['dispatch']['ref'])}`",
            "",
            "## Remaining Blockers",
            "",
        ]
    )
    if payload["blockers"]:
        lines.extend(f"- {md_escape(blocker)}" for blocker in payload["blockers"])
    else:
        lines.append("- None.")

    lines.extend(["", "## Operator Checklist", ""])
    for group in payload["action_groups"]:
        lines.extend(["", f"### {md_escape(group['name'])}", ""])
        for action in group["actions"]:
            done = action in payload["doctor"]["next_actions"] and payload["ready"]
            lines.append(f"- {checkbox(done)} `{md_escape(action)}`")

    lines.extend(
        [
            "",
            "## Final Dispatch",
            "",
            "Run the plan command first. The execute command refuses to dispatch unless the live doctor and repository gates are ready.",
            "",
            "```powershell",
            "npm run github:deploy:plan",
            "npm run github:deploy",
            "```",
            "",
            "Underlying workflow command:",
            "",
            "```powershell",
            md_escape(payload["dispatch"]["command_text"]),
            "```",
            "",
            "## Private Local Files",
            "",
        ]
    )
    lines.extend(f"- `{md_escape(path)}`" for path in payload["private_local_files"])
    lines.extend(
        [
            "",
            "Keep private local files out of git. The checked-in `.gitignore` already excludes `*.local.json`, `*.local.txt`, `*.local.md`, `.env`, and `cloudflare/.dev.vars`.",
            "",
        ]
    )
    return redact_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a redacted Workdoe launch handoff checklist from live release gates."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument(
        "--local-url",
        default=DEFAULT_LOCAL_URL,
        help="Local prototype URL checked by the launch doctor.",
    )
    parser.add_argument("--write", action="store_true", help="Write the Markdown handoff file.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Markdown output path.")
    parser.add_argument(
        "--fail-when-not-ready",
        action="store_true",
        help="Exit nonzero when production dispatch is not ready.",
    )
    args = parser.parse_args()

    payload = build_handoff_payload(REPO_ROOT, local_url=args.local_url)
    markdown = render_markdown(payload)
    if args.write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(markdown)
    if args.fail_when_not_ready and not payload["ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
