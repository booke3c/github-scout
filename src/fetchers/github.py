import os
import re
import base64
import time
from datetime import datetime, timezone

import requests

from ..models import RawToolData

_BASE = "https://api.github.com"


def _headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _get(url: str, params: dict = None) -> dict | list | None:
    try:
        r = requests.get(url, headers=_headers(), params=params, timeout=10)
        if r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", 30))
            time.sleep(retry_after)
            return _get(url, params)
        if r.status_code >= 400:
            return None
        return r.json()
    except Exception:
        return None


def _days_since(iso_str: str) -> int:
    if not iso_str:
        return 9999
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).days


def _file_exists(owner: str, repo: str, path: str) -> bool:
    return _get(f"{_BASE}/repos/{owner}/{repo}/contents/{path}") is not None


def _file_content(owner: str, repo: str, path: str) -> str:
    result = _get(f"{_BASE}/repos/{owner}/{repo}/contents/{path}")
    if result and isinstance(result, dict) and "content" in result:
        return base64.b64decode(result["content"]).decode("utf-8", errors="ignore")
    return ""


def _detect_curl_bash(text: str) -> bool:
    return bool(re.search(r"curl\s+\S+.*\|\s*(ba)?sh", text, re.IGNORECASE))


def _detect_write_all(text: str) -> bool:
    return bool(re.search(r"permissions:\s*write-all", text, re.IGNORECASE))


def _detect_accesses_secrets(text: str) -> bool:
    return bool(re.search(r"\$\{\{\s*secrets\.", text))


def _detect_unpinned_action(text: str) -> bool:
    for line in re.findall(r"uses:\s*(\S+)", text):
        if line.startswith("./") or line.startswith("docker://"):
            continue
        if not re.search(r"@[0-9a-f]{40}", line):
            return True
    return False


def _get_integration_level(repo_data: dict, topics: list[str]) -> int:
    combined = " ".join(topics).lower() + " " + (repo_data.get("description") or "").lower()
    if any(k in combined for k in ["mcp", "claude-code", "model-context-protocol"]):
        return 20
    if any(k in combined for k in ["cli", "command-line", "terminal"]):
        return 16
    if any(k in combined for k in ["github-action", "github-actions"]):
        return 12
    return 8


def _get_issue_stats(owner: str, repo: str) -> tuple[float, float, int]:
    closed = _get(f"{_BASE}/repos/{owner}/{repo}/issues",
                  {"state": "closed", "per_page": 20, "sort": "updated"}) or []
    repo_info = _get(f"{_BASE}/repos/{owner}/{repo}") or {}
    open_count = repo_info.get("open_issues_count", 0)

    close_times = [
        (_days_since(i.get("closed_at", "")) - _days_since(i.get("created_at", ""))) * -1
        for i in closed
        if not i.get("pull_request") and i.get("closed_at") and i.get("created_at")
    ]
    avg_close = sum(close_times) / len(close_times) if close_times else 999.0

    total = max(1, open_count + len([i for i in closed if not i.get("pull_request")]))
    open_ratio = open_count / total

    sec_issues = _get(f"{_BASE}/repos/{owner}/{repo}/issues",
                      {"state": "open", "labels": "security", "per_page": 5}) or []
    sec_unresolved = _days_since(sec_issues[0].get("created_at", "")) if sec_issues else 0

    return avg_close, open_ratio, sec_unresolved


def _get_pr_merge_rate(owner: str, repo: str) -> float:
    prs = _get(f"{_BASE}/repos/{owner}/{repo}/pulls",
               {"state": "closed", "per_page": 20}) or []
    if not prs:
        return 0.5
    merged = sum(1 for pr in prs if pr.get("merged_at"))
    return merged / len(prs)


def fetch_github(query: str, max_results: int = 10) -> list[RawToolData]:
    data = _get(f"{_BASE}/search/repositories",
                {"q": query, "sort": "stars", "per_page": max_results, "order": "desc"})
    if not data or "items" not in data:
        return []

    results = []
    for item in data["items"]:
        owner = item["owner"]["login"]
        repo = item["name"]
        topics = item.get("topics", [])

        has_readme = _file_exists(owner, repo, "README.md")
        readme = _file_content(owner, repo, "README.md") if has_readme else ""

        workflows = _get(f"{_BASE}/repos/{owner}/{repo}/contents/.github/workflows") or []
        action_unpinned = requires_write_all = accesses_secrets = False
        if isinstance(workflows, list):
            for wf in workflows[:3]:
                content = _file_content(owner, repo, wf.get("path", ""))
                if content:
                    action_unpinned = action_unpinned or _detect_unpinned_action(content)
                    requires_write_all = requires_write_all or _detect_write_all(content)
                    accesses_secrets = accesses_secrets or _detect_accesses_secrets(content)

        releases = _get(f"{_BASE}/repos/{owner}/{repo}/releases", {"per_page": 5}) or []
        release_count = len(releases) if isinstance(releases, list) else 0
        has_signed = any(
            any(a.get("name", "").endswith((".sig", ".asc", ".sha256sum"))
                for a in r.get("assets", []))
            for r in (releases if isinstance(releases, list) else [])
        )

        contributors = _get(f"{_BASE}/repos/{owner}/{repo}/contributors",
                            {"per_page": 5}) or []
        contributor_count = len(contributors) if isinstance(contributors, list) else 0

        has_lockfile = any(
            _file_exists(owner, repo, f)
            for f in ["package-lock.json", "yarn.lock", "poetry.lock", "Pipfile.lock"]
        )

        avg_close, open_ratio, sec_unresolved = _get_issue_stats(owner, repo)
        pr_merge_rate = _get_pr_merge_rate(owner, repo)

        org_data = _get(f"{_BASE}/orgs/{owner}") or {}
        verified_org = isinstance(org_data, dict) and org_data.get("is_verified", False)

        results.append(RawToolData(
            name=item["full_name"],
            source="github",
            url=item["html_url"],
            description=(item.get("description") or "")[:120],
            stars=item.get("stargazers_count", 0),
            last_commit_days=_days_since(item.get("pushed_at", "")),
            has_security_md=_file_exists(owner, repo, "SECURITY.md"),
            has_license=item.get("license") is not None,
            license_type=((item.get("license") or {}).get("spdx_id") or ""),
            has_signed_release=has_signed,
            has_lockfile=has_lockfile,
            requires_curl_bash=_detect_curl_bash(readme),
            action_unpinned=action_unpinned,
            requires_write_all=requires_write_all,
            accesses_secrets=accesses_secrets,
            claude_code_integration_level=_get_integration_level(item, topics),
            maintainer_verified_org=verified_org,
            has_readme=has_readme,
            contributor_count=contributor_count,
            release_count=release_count,
            avg_issue_close_days=avg_close,
            open_issue_ratio=open_ratio,
            security_issue_unresolved_days=sec_unresolved,
            pr_merge_rate=pr_merge_rate,
        ))

    return results
