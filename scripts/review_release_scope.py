"""Read committed Workdoe release differences without executing application code."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath

from cloudflare_production_deploy import FULL_COMMIT_ID, RELEASE_INPUT_PATHS, git_read
from jinja2 import Environment, TemplateError, nodes
from workdoe_production_smoke import committed_release_reader

ROOT = Path(__file__).resolve().parents[1]
SCOPE_PATHS = (*RELEASE_INPUT_PATHS, "workdoe", "scripts", ".github/workflows",
               "cloudflare/workdoe-cloudflare-manifest.json", "cloudflare/.dev.vars.example",
               "LICENSE", "THIRD_PARTY_NOTICES.md")
MAX_SOURCE_BYTES = 2 * 1024 * 1024
POLICIES = ("privacy", "terms", "safety")
ROOT_PYTHON_REQUIREMENTS = frozenset({"requirements.txt", "requirements-audit.txt"})


def python_dependency_inputs(before: dict, after: dict) -> dict:
    files = []
    for path in sorted(before.keys() | after.keys() | ROOT_PYTHON_REQUIREMENTS):
        parsed = PurePosixPath(path)
        if path not in ROOT_PYTHON_REQUIREMENTS and not (
            parsed.parent == PurePosixPath(".github/python") and parsed.suffix == ".txt"
        ):
            continue
        status = (
            "missing" if path not in before and path not in after else
            "added" if path not in before else "removed" if path not in after else
            "unchanged" if before[path] == after[path] else "modified"
        )
        files.append({"path": path, "status": status})
    return {
        "scope": ["requirements.txt", "requirements-audit.txt", "tracked direct .github/python/*.txt files"],
        "unchanged": all(item["status"] == "unchanged" for item in files),
        "files": files,
        "package_version_changes": "not_evaluated",
    }


class ScopeReviewError(ValueError):
    pass


class PolicyStatements(HTMLParser):
    """Compare narrative headings, paragraphs and their links, not navigation."""

    def __init__(self, html: str):
        super().__init__(convert_charrefs=True)
        self.statements: list[dict] = []
        self.navigation_depth = 0
        self.capture: str | None = None
        self.parts: list[str] = []
        self.links: list[str] = []
        self.feed(html)
        self.close()
        if self.capture or self.navigation_depth:
            raise ScopeReviewError("Policy markup is incomplete.")
        if sum(item["tag"] == "h1" for item in self.statements) != 1 or sum(
            item["tag"] == "p" for item in self.statements
        ) < 6:
            raise ScopeReviewError("Policy narrative is incomplete.")

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if len(attributes) != len(attrs):
            raise ScopeReviewError("Policy markup contains duplicate attributes.")
        if tag == "nav":
            self.navigation_depth += 1
        if self.navigation_depth:
            return
        if tag in {"h1", "h2", "h3", "p"}:
            if self.capture:
                raise ScopeReviewError("Policy narrative has nested text blocks.")
            if "eyebrow" not in str(attributes.get("class") or "").split() and attributes.get("aria-hidden") != "true":
                self.capture, self.parts, self.links = tag, [], []
        elif tag == "a" and self.capture:
            self.links.append(attributes.get("href") or "")

    def handle_endtag(self, tag):
        if tag == "nav":
            self.navigation_depth -= 1
            if self.navigation_depth < 0:
                raise ScopeReviewError("Policy navigation is incomplete.")
        elif not self.navigation_depth and tag == self.capture:
            text = " ".join("".join(self.parts).split())
            if not text:
                raise ScopeReviewError("Policy narrative contains an empty text block.")
            self.statements.append({"tag": tag, "text": text, "links": self.links})
            self.capture = None

    def handle_data(self, data):
        if self.capture and not self.navigation_depth:
            self.parts.append(data)


def worker_policy_body(source: str, name: str) -> str:
    functions = [item for item in ast.parse(source).body if isinstance(item, ast.FunctionDef) and item.name == f"{name}_page_html"]
    if len(functions) != 1 or len(functions[0].body) != 2:
        raise ScopeReviewError("Worker policy does not use the reviewed static-body structure.")
    assignment, returned = functions[0].body
    if not (
        isinstance(assignment, ast.Assign) and len(assignment.targets) == 1
        and isinstance(assignment.targets[0], ast.Name) and assignment.targets[0].id == "body"
        and isinstance(assignment.value, ast.Constant) and isinstance(assignment.value.value, str)
        and isinstance(returned, ast.Return) and isinstance(returned.value, ast.Call)
        and isinstance(returned.value.func, ast.Name) and returned.value.func.id == "layout"
        and len(returned.value.args) == 4 and isinstance(returned.value.args[3], ast.Name)
        and returned.value.args[3].id == "body"
    ):
        raise ScopeReviewError("Worker policy body could not be verified without execution.")
    return assignment.value.value


def template_policy_body(source: str) -> str:
    blocks = [block for block in Environment(autoescape=True).parse(source).find_all(nodes.Block) if block.name == "content"]
    if len(blocks) != 1 or any(not isinstance(item, nodes.Output) for item in blocks[0].body):
        raise ScopeReviewError("Template policy content is not static.")
    fragments = [fragment for item in blocks[0].body for fragment in item.nodes]
    if any(not isinstance(fragment, nodes.TemplateData) for fragment in fragments):
        raise ScopeReviewError("Template policy content requires evaluation.")
    return "".join(fragment.data for fragment in fragments)


def policy_fingerprint(statements: list[dict]) -> str:
    return hashlib.sha256(json.dumps(statements, ensure_ascii=True, sort_keys=True).encode()).hexdigest()


def committed_tree(repo_root: Path, commit: str) -> dict[str, tuple[str, str]]:
    if not FULL_COMMIT_ID.fullmatch(commit):
        raise ScopeReviewError("Use a full Git commit ID for both revisions.")
    # The shared reader verifies that the supplied object is exactly a commit.
    committed_release_reader(repo_root, commit)
    tree = {}
    for record in filter(None, git_read(repo_root, ["ls-tree", "-rz", "--full-tree", commit, "--", *SCOPE_PATHS]).split("\0")):
        metadata, name = record.split("\t", 1)
        mode, kind, object_id = metadata.split()
        if (
            mode not in {"100644", "100755"} or kind != "blob" or not FULL_COMMIT_ID.fullmatch(object_id)
            or "\ufffd" in name or "\n" in name or "\r" in name
        ):
            raise ScopeReviewError("Unsupported release tree entry; manual review is required.")
        tree[name] = (mode, object_id)
    if not tree or len(tree) > 4096:
        raise ScopeReviewError("Release tree is empty or outside the review limit.")
    return tree


def category(path: str) -> str:
    if path.startswith("cloudflare/worker/"):
        return "worker"
    if path.startswith("workdoe/static/"):
        return "browser_assets"
    if path.startswith("workdoe/"):
        return "flask_adapter_and_templates"
    if path.startswith("cloudflare/d1/migrations/"):
        return "database_migrations"
    if path.startswith(("scripts/", ".github/workflows/")):
        return "release_tooling"
    return "configuration_and_provenance"


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ScopeReviewError("Duplicate key in a committed JSON document.")
        result[key] = value
    return result


def read_json(read, path: str) -> dict:
    def invalid_constant(_):
        raise ScopeReviewError("Non-finite constant in a committed JSON document.")

    document = json.loads(read(path, MAX_SOURCE_BYTES).decode("utf-8"), object_pairs_hook=unique_object, parse_constant=invalid_constant)
    if not isinstance(document, dict):
        raise ScopeReviewError("Expected a committed JSON object.")
    return document


def review(repo_root: Path, base: str, candidate: str) -> dict:
    before, after = committed_tree(repo_root, base), committed_tree(repo_root, candidate)
    required = {"package.json", "package-lock.json", *ROOT_PYTHON_REQUIREMENTS, "cloudflare/wrangler.jsonc",
                "cloudflare/worker/app_shell.py", *(f"workdoe/templates/{name}.html" for name in POLICIES)}
    if any(not required.issubset(tree) for tree in (before, after)):
        raise ScopeReviewError("A required committed release input is missing.")
    changed = [
        {"path": path, "status": "added" if path not in before else "removed" if path not in after else "modified",
         "category": category(path)}
        for path in sorted(before.keys() | after.keys()) if before.get(path) != after.get(path)
    ]
    reads = [committed_release_reader(repo_root, commit) for commit in (base, candidate)]
    configs = [read_json(read, "cloudflare/wrangler.jsonc") for read in reads]
    if any(not isinstance(config.get("vars"), dict) for config in configs):
        raise ScopeReviewError("Committed Worker variables are not structured objects.")
    changed_variables = sorted(key for key in configs[0]["vars"].keys() | configs[1]["vars"].keys()
                               if key not in configs[0]["vars"] or key not in configs[1]["vars"]
                               or configs[0]["vars"][key] != configs[1]["vars"][key])
    other_config = sorted(key for key in configs[0].keys() | configs[1].keys()
                          if key != "vars" and (key not in configs[0] or key not in configs[1]
                                                or configs[0][key] != configs[1][key]))
    packages = [read_json(read, "package.json") for read in reads]
    package_pin_keys = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies",
                        "peerDependenciesMeta", "bundledDependencies", "bundleDependencies", "overrides", "engines")
    worker_sources = [read("cloudflare/worker/app_shell.py", MAX_SOURCE_BYTES).decode("utf-8") for read in reads]
    policies = {}
    for name in POLICIES:
        statements = [PolicyStatements(worker_policy_body(source, name)).statements for source in worker_sources]
        templates = [PolicyStatements(template_policy_body(read(f"workdoe/templates/{name}.html", MAX_SOURCE_BYTES).decode("utf-8"))).statements
                     for read in reads]
        policies[name] = {
            "worker_statements_unchanged": statements[0] == statements[1],
            "template_statements_unchanged": templates[0] == templates[1],
            "base_adapter_parity": statements[0] == templates[0],
            "candidate_adapter_parity": statements[1] == templates[1],
            "base_fingerprint": policy_fingerprint(statements[0]),
            "candidate_fingerprint": policy_fingerprint(statements[1]),
            "candidate_statement_count": len(statements[1]),
        }
    migration_paths = {path for path in before.keys() | after.keys() if path.startswith("cloudflare/d1/migrations/")}
    if not migration_paths:
        raise ScopeReviewError("Migration inventory is empty.")
    return {
        "schema": "workdoe.release-scope.v1", "base_commit": base, "candidate_commit": candidate,
        "scope_paths": list(SCOPE_PATHS),
        "read_only": True, "provider_commands_executed": False, "live_baseline_verified": False,
        "deployment_authorized": False, "public_launch_authorized": False,
        "changed_path_count": len(changed), "changed_categories": dict(sorted(Counter(item["category"] for item in changed).items())),
        "changed_paths": changed,
        "configuration": {"changed_variable_names": changed_variables, "other_changed_keys": other_config,
                          "variable_values_omitted": True},
        "database_migrations_unchanged": all(before.get(path) == after.get(path) for path in migration_paths),
        "migration_file_count": sum(path in after and path.endswith(".sql") for path in migration_paths),
        "node_lock_unchanged": before.get("package-lock.json") == after.get("package-lock.json"),
        "python_requirements_unchanged": before.get("requirements.txt") == after.get("requirements.txt"),
        "python_requirements_legacy_scope": "requirements.txt only",
        "python_dependency_inputs": python_dependency_inputs(before, after),
        "node_dependency_pins_unchanged": all(packages[0].get(key) == packages[1].get(key) for key in package_pin_keys),
        "provenance_changed_paths": [
            item["path"] for item in changed if item["path"] in {
                "LICENSE", "THIRD_PARTY_NOTICES.md", "DEPENDENCY_PROVENANCE.json",
            } or item["path"].startswith("licenses/")
        ],
        "license_clearance": "not_evaluated",
        "policy_statement_comparison": policies,
        "limitations": ["Committed static narrative and paragraph links only; not a rendered-response or legal review.",
                        "Policy layout, navigation, browser notices, provider settings and deployed data practices need separate review.",
                        "Source inventory is not code approval, dependency clearance, live-state proof or permission to deploy."],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--candidate-commit", required=True)
    args = parser.parse_args()
    try:
        payload = review(ROOT, args.base_commit, args.candidate_commit)
    except (OSError, ValueError, SyntaxError, RecursionError, TemplateError, subprocess.SubprocessError):
        print(json.dumps({"ok": False, "error": "Committed scope could not be verified; no provider commands were run."}))
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
