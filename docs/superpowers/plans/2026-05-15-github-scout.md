# GitHub Scout Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI agent that searches GitHub, VS Code Marketplace, and Docker Hub for high-quality tools, scores them with a security-first algorithm, prints results to the terminal, and optionally writes weekly scans to a Notion page.

**Architecture:** Single entry-point `github_scout.py` delegates to modular fetchers (`src/fetchers/`), a scorer (`src/scorer.py`), a formatter (`src/formatter.py`), and a Notion writer (`src/notion_writer.py`). `--query` mode: fetch → score → print. `--scan` mode: iterate config keywords → fetch → score → write Notion.

**Tech Stack:** Python 3.10+, `requests`, `notion-client`, `python-dateutil`, `python-dotenv`, `pytest`

---

## File Map

```
github-scout/
├── github_scout.py                  # CLI entry point (--query / --scan)
├── config.json                      # Keywords, thresholds, Notion page ID
├── .env.example                     # Token template (safe to commit)
├── .env                             # Actual tokens (gitignored)
├── .gitignore
├── requirements.txt
├── task_scheduler.xml               # Windows Task Scheduler import file
├── src/
│   ├── __init__.py
│   ├── models.py                    # RawToolData, ScoredTool dataclasses
│   ├── scorer.py                    # Scoring algorithm v0.2
│   ├── formatter.py                 # Terminal output formatting
│   ├── notion_writer.py             # Notion Blocks API writer
│   └── fetchers/
│       ├── __init__.py
│       ├── github.py                # GitHub Search + repo detail APIs
│       ├── vscode.py                # VS Code Marketplace API
│       └── docker.py                # Docker Hub API
├── tests/
│   ├── __init__.py
│   ├── test_scorer.py
│   ├── test_formatter.py
│   ├── test_notion_writer.py
│   ├── test_github_fetcher.py
│   └── test_fetchers.py             # vscode + docker
└── .claude/
    └── commands/
        └── github-scout.md          # Claude Code slash command
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `github-scout/requirements.txt`
- Create: `github-scout/.gitignore`
- Create: `github-scout/.env.example`
- Create: `github-scout/config.json`
- Create: `github-scout/src/__init__.py`
- Create: `github-scout/src/fetchers/__init__.py`
- Create: `github-scout/tests/__init__.py`

- [ ] **Step 1: Init git repo and create directory structure**

```bash
cd C:\Users\USER1502\github-scout
git init
mkdir src src\fetchers tests .claude .claude\commands logs
```

- [ ] **Step 2: Write requirements.txt**

```
requests==2.32.3
notion-client==2.2.1
python-dateutil==2.9.0
python-dotenv==1.0.1
pytest==8.2.0
```

- [ ] **Step 3: Write .gitignore**

```
.env
logs/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 4: Write .env.example**

```env
GITHUB_TOKEN=ghp_your_token_here
NOTION_TOKEN=ntn_your_token_here
```

The actual `.env` must have:
- `GITHUB_TOKEN`: GitHub Personal Access Token, scopes: `public_repo` (read-only)
- `NOTION_TOKEN`: Internal Integration Token from `C:\Users\USER1502\Desktop\claude_code_Notion_api\api.txt`

- [ ] **Step 5: Write config.json**

```json
{
  "scan_keywords": [
    "opc-ua", "cnc automation", "python automation",
    "mcp server", "claude-code", "ci/cd",
    "docker dev tools", "code quality",
    "security scan", "vs code productivity",
    "python testing", "api monitoring",
    "github actions", "cli tool"
  ],
  "min_score": 70,
  "max_results_per_query": 10,
  "notion_page_id": "361967ffe82f808dad92c6669ce93a45"
}
```

- [ ] **Step 6: Create empty __init__.py files**

```bash
# Create empty files
type nul > src\__init__.py
type nul > src\fetchers\__init__.py
type nul > tests\__init__.py
```

- [ ] **Step 7: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 8: Commit**

```bash
git add requirements.txt .gitignore .env.example config.json src\__init__.py src\fetchers\__init__.py tests\__init__.py
git commit -m "chore: project scaffold"
```

---

## Task 2: Data Model

**Files:**
- Create: `src/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing test**

`tests/test_models.py`:
```python
from src.models import RawToolData, ScoredTool

def test_raw_tool_data_defaults():
    t = RawToolData(name="a/b", source="github", url="https://github.com/a/b", description="test")
    assert t.stars == 0
    assert t.last_commit_days == 9999
    assert t.claude_code_integration_level == 4
    assert t.data_complete is True

def test_scored_tool_fields():
    t = RawToolData(name="a/b", source="github", url="https://github.com/a/b", description="test")
    s = ScoredTool(data=t, security_score=25, integration_score=16, stars_score=8,
                   credibility_score=12, response_score=10, total=71,
                   category="recommended", warnings=[])
    assert s.total == 71
    assert s.category == "recommended"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_models.py -v
```

Expected: `ImportError: cannot import name 'RawToolData'`

- [ ] **Step 3: Write src/models.py**

```python
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class RawToolData:
    name: str
    source: Literal["github", "vscode", "docker", "pypi"]
    url: str
    description: str
    stars: int = 0
    last_commit_days: int = 9999
    has_security_md: bool = False
    has_license: bool = False
    license_type: str = ""
    has_signed_release: bool = False
    has_lockfile: bool = False
    cve_count: int = 0
    dep_vuln_count: int = 0
    requires_curl_bash: bool = False
    action_unpinned: bool = False
    requires_write_all: bool = False
    accesses_secrets: bool = False
    unresolved_security_issues: int = 0
    claude_code_integration_level: int = 4
    maintainer_verified_org: bool = False
    has_readme: bool = False
    contributor_count: int = 0
    release_count: int = 0
    avg_issue_close_days: float = 999.0
    open_issue_ratio: float = 1.0
    security_issue_unresolved_days: int = 0
    pr_merge_rate: float = 0.5
    data_complete: bool = True
    missing_fields: list = field(default_factory=list)


@dataclass
class ScoredTool:
    data: RawToolData
    security_score: int
    integration_score: int
    stars_score: int
    credibility_score: int
    response_score: int
    total: int
    category: Literal["recommended", "watch", "avoid"]
    warnings: list[str]
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
pytest tests/test_models.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: add RawToolData and ScoredTool data models"
```

---

## Task 3: Scorer

**Files:**
- Create: `src/scorer.py`
- Create: `tests/test_scorer.py`

- [ ] **Step 1: Write failing tests**

`tests/test_scorer.py`:
```python
import pytest
from src.models import RawToolData
from src.scorer import score_tool

def _safe_tool(**kwargs) -> RawToolData:
    defaults = dict(
        name="safe/tool", source="github", url="https://github.com/safe/tool",
        description="test", stars=5000, last_commit_days=14,
        has_security_md=True, has_license=True, license_type="MIT",
        has_signed_release=True, has_lockfile=True,
        cve_count=0, dep_vuln_count=0,
        claude_code_integration_level=16,
        maintainer_verified_org=True, has_readme=True,
        contributor_count=5, release_count=4,
        avg_issue_close_days=14.0, open_issue_ratio=0.2, pr_merge_rate=0.8,
    )
    defaults.update(kwargs)
    return RawToolData(**defaults)

def test_safe_popular_tool_is_recommended():
    result = score_tool(_safe_tool())
    assert result.total >= 70
    assert result.category == "recommended"

def test_curl_bash_tool_is_avoided():
    result = score_tool(_safe_tool(requires_curl_bash=True))
    assert result.security_score < 25
    assert result.category == "avoid"
    assert any("curl" in w for w in result.warnings)

def test_write_all_permission_penalizes_security():
    result = score_tool(_safe_tool(requires_write_all=True))
    assert result.security_score < 25
    assert result.category == "avoid"

def test_low_integration_goes_to_watch():
    result = score_tool(_safe_tool(claude_code_integration_level=4))
    assert result.category == "watch"

def test_no_commit_12_months_demotes_to_watch():
    result = score_tool(_safe_tool(last_commit_days=400))
    assert result.category == "watch"
    assert any("12 months" in w for w in result.warnings)

def test_stars_score_thresholds():
    from src.scorer import _score_stars
    assert _score_stars(15000) == 15
    assert _score_stars(5000) == 12
    assert _score_stars(1000) == 8
    assert _score_stars(100) == 4
    assert _score_stars(50) == 1

def test_security_score_max_is_25_for_all_green():
    result = score_tool(_safe_tool())
    assert result.security_score == 25  # 5+3+3+2+7+5

def test_data_incomplete_adds_warning():
    t = _safe_tool(data_complete=False, missing_fields=["avg_issue_close_days"])
    result = score_tool(t)
    assert any("資料不足" in w for w in result.warnings)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_scorer.py -v
```

Expected: `ImportError: cannot import name 'score_tool'`

- [ ] **Step 3: Write src/scorer.py**

```python
from .models import RawToolData, ScoredTool


def _score_security(t: RawToolData) -> tuple[int, list[str]]:
    score = 0
    if t.has_security_md: score += 5
    if t.has_license: score += 3
    if t.has_signed_release: score += 3
    if t.has_lockfile: score += 2
    if t.cve_count == 0: score += 7
    if t.dep_vuln_count == 0: score += 5

    warnings = []
    danger_flags = [
        (t.requires_curl_bash, "README requires curl|bash install"),
        (t.action_unpinned, "GitHub Action not pinned to SHA"),
        (t.requires_write_all, "workflow requires write-all permissions"),
        (t.accesses_secrets, "accesses secrets/tokens/SSH keys"),
        (t.unresolved_security_issues > 5,
         f"{t.unresolved_security_issues} unresolved security issues"),
    ]
    for flag, msg in danger_flags:
        if flag:
            score = max(0, score - 5)
            warnings.append(msg)

    return score, warnings


def _score_stars(stars: int) -> int:
    for threshold, pts in [(10000, 15), (5000, 12), (1000, 8), (100, 4)]:
        if stars >= threshold:
            return pts
    return 1


def _score_credibility(t: RawToolData) -> int:
    score = 0
    if t.maintainer_verified_org: score += 4
    if t.has_readme: score += 3
    if t.contributor_count >= 3: score += 3
    if t.release_count >= 3: score += 3
    if t.license_type.upper() in (
        "MIT", "APACHE", "APACHE-2.0", "BSD", "BSD-2-CLAUSE", "BSD-3-CLAUSE"
    ):
        score += 2
    return score


def _score_response(t: RawToolData) -> tuple[int, list[str]]:
    warnings = []
    avg = t.avg_issue_close_days
    score = 15 if avg <= 7 else 10 if avg <= 30 else 5 if avg <= 90 else 0

    if t.open_issue_ratio > 0.5:
        score = max(0, score - 3)
        warnings.append(f"high open issue ratio ({t.open_issue_ratio:.0%})")
    if t.security_issue_unresolved_days > 30:
        score = max(0, score - 5)
        warnings.append("security issue open >30 days")
    if t.pr_merge_rate < 0.3:
        score = max(0, score - 3)
        warnings.append(f"low PR merge rate ({t.pr_merge_rate:.0%})")

    return score, warnings


def _categorize(total: int, security: int, integration: int) -> str:
    if security < 25:
        return "avoid"
    if integration < 8:
        return "watch"
    if total < 70:
        return "watch"
    return "recommended"


def score_tool(t: RawToolData) -> ScoredTool:
    security, sec_warns = _score_security(t)
    integration = t.claude_code_integration_level
    stars = _score_stars(t.stars)
    credibility = _score_credibility(t)
    response, resp_warns = _score_response(t)
    total = security + integration + stars + credibility + response
    warnings = sec_warns + resp_warns

    if t.last_commit_days > 365:
        warnings.append("no commit in 12 months")

    if not t.data_complete:
        warnings.append(f"資料不足，請人工確認: {', '.join(t.missing_fields)}")

    category = _categorize(total, security, integration)
    if t.last_commit_days > 365 and category == "recommended":
        category = "watch"

    return ScoredTool(t, security, integration, stars, credibility, response,
                      total, category, warnings)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_scorer.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/scorer.py tests/test_scorer.py
git commit -m "feat: add scoring algorithm v0.2"
```

---

## Task 4: GitHub Fetcher

**Files:**
- Create: `src/fetchers/github.py`
- Create: `tests/test_github_fetcher.py`

- [ ] **Step 1: Write failing tests (with mocked HTTP)**

`tests/test_github_fetcher.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from src.fetchers.github import (
    _detect_curl_bash, _detect_write_all,
    _detect_accesses_secrets, _detect_unpinned_action,
    _days_since, _get_integration_level,
)

def test_detect_curl_bash_positive():
    assert _detect_curl_bash("curl -fsSL https://example.com | bash") is True
    assert _detect_curl_bash("curl https://x.com/install.sh | sh") is True

def test_detect_curl_bash_negative():
    assert _detect_curl_bash("pip install requests") is False

def test_detect_write_all():
    assert _detect_write_all("permissions: write-all") is True
    assert _detect_write_all("permissions: read-all") is False

def test_detect_accesses_secrets():
    assert _detect_accesses_secrets("${{ secrets.GITHUB_TOKEN }}") is True
    assert _detect_accesses_secrets("no secrets here") is False

def test_detect_unpinned_action():
    pinned = "uses: actions/checkout@a81bbbf8298c0fa03ea29cdc473d45769f953675"
    unpinned = "uses: actions/checkout@v3"
    assert _detect_unpinned_action(unpinned) is True
    assert _detect_unpinned_action(pinned) is False

def test_days_since_recent():
    from datetime import datetime, timezone, timedelta
    recent = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    assert _days_since(recent) == 5

def test_days_since_empty():
    assert _days_since("") == 9999

def test_integration_level_mcp():
    assert _get_integration_level({"description": "an MCP server"}, ["mcp"]) == 20

def test_integration_level_cli():
    assert _get_integration_level({"description": "a CLI tool"}, ["cli"]) == 16

def test_integration_level_default():
    assert _get_integration_level({"description": "a library"}, []) == 8
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_github_fetcher.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Write src/fetchers/github.py**

```python
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_github_fetcher.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/fetchers/github.py tests/test_github_fetcher.py
git commit -m "feat: add GitHub fetcher with security pattern detection"
```

---

## Task 5: VS Code Marketplace + Docker Hub Fetchers

**Files:**
- Create: `src/fetchers/vscode.py`
- Create: `src/fetchers/docker.py`
- Create: `tests/test_fetchers.py`

- [ ] **Step 1: Write failing tests**

`tests/test_fetchers.py`:
```python
from unittest.mock import patch, MagicMock
from src.fetchers.vscode import fetch_vscode
from src.fetchers.docker import fetch_docker

def test_vscode_returns_empty_on_api_error():
    with patch("src.fetchers.vscode.requests.post") as mock:
        mock.return_value.status_code = 500
        result = fetch_vscode("python")
    assert result == []

def test_vscode_parses_response():
    mock_response = {
        "results": [{
            "extensions": [{
                "extensionName": "python",
                "publisher": {"publisherName": "ms-python"},
                "displayName": "Python",
                "shortDescription": "Python support",
                "statistics": [
                    {"statisticName": "install", "value": 100000000},
                    {"statisticName": "averagerating", "value": 4.5},
                ],
                "lastUpdated": "2026-01-01T00:00:00Z",
                "flags": "validated",
            }]
        }]
    }
    with patch("src.fetchers.vscode.requests.post") as mock:
        mock.return_value.status_code = 200
        mock.return_value.json.return_value = mock_response
        result = fetch_vscode("python")
    assert len(result) == 1
    assert result[0].name == "ms-python.python"
    assert result[0].source == "vscode"

def test_docker_returns_empty_on_api_error():
    with patch("src.fetchers.docker.requests.get") as mock:
        mock.return_value.status_code = 500
        result = fetch_docker("python")
    assert result == []

def test_docker_parses_official_image():
    mock_response = {
        "results": [{
            "repo_name": "python",
            "short_description": "Python official image",
            "star_count": 10000,
            "pull_count": 1000000000,
            "is_official": True,
            "last_updated": "2026-01-01T00:00:00Z",
        }]
    }
    with patch("src.fetchers.docker.requests.get") as mock:
        mock.return_value.status_code = 200
        mock.return_value.json.return_value = mock_response
        result = fetch_docker("python")
    assert len(result) == 1
    assert result[0].name == "python"
    assert result[0].maintainer_verified_org is True
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_fetchers.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Write src/fetchers/vscode.py**

```python
import os
from datetime import datetime, timezone

import requests

from ..models import RawToolData

_ENDPOINT = "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery"
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json;api-version=6.0-preview.1",
}


def fetch_vscode(query: str, max_results: int = 10) -> list[RawToolData]:
    body = {
        "filters": [{
            "criteria": [
                {"filterType": 8, "value": "Microsoft.VisualStudio.Code"},
                {"filterType": 10, "value": query},
            ],
            "pageSize": max_results,
            "sortBy": 4,
            "sortOrder": 0,
        }],
        "assetTypes": [],
        "flags": 914,
    }
    try:
        r = requests.post(_ENDPOINT, json=body, headers=_HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception:
        return []

    results = []
    for ext in (data.get("results") or [{}])[0].get("extensions", []):
        publisher = ext.get("publisher", {}).get("publisherName", "unknown")
        name = ext.get("extensionName", "")
        stats = {s["statisticName"]: s["value"] for s in ext.get("statistics", [])}
        install_count = int(stats.get("install", 0))
        is_featured = "validated" in (ext.get("flags") or "")

        last_updated = ext.get("lastUpdated", "")
        days = 9999
        if last_updated:
            dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - dt).days

        results.append(RawToolData(
            name=f"{publisher}.{name}",
            source="vscode",
            url=f"https://marketplace.visualstudio.com/items?itemName={publisher}.{name}",
            description=(ext.get("shortDescription") or "")[:120],
            stars=install_count // 10000,
            last_commit_days=days,
            has_license=True,
            maintainer_verified_org=is_featured,
            has_readme=True,
            claude_code_integration_level=12,
        ))

    return results
```

- [ ] **Step 4: Write src/fetchers/docker.py**

```python
from datetime import datetime, timezone

import requests

from ..models import RawToolData

_BASE = "https://hub.docker.com/v2/search/repositories"


def fetch_docker(query: str, max_results: int = 10) -> list[RawToolData]:
    try:
        r = requests.get(_BASE, params={"query": query, "page_size": max_results}, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception:
        return []

    results = []
    for item in data.get("results", []):
        last_updated = item.get("last_updated", "")
        days = 9999
        if last_updated:
            dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - dt).days

        is_official = item.get("is_official", False)
        pull_count = item.get("pull_count", 0)

        results.append(RawToolData(
            name=item.get("repo_name", ""),
            source="docker",
            url=f"https://hub.docker.com/r/{item.get('repo_name', '')}",
            description=(item.get("short_description") or "")[:120],
            stars=item.get("star_count", 0),
            last_commit_days=days,
            maintainer_verified_org=is_official,
            has_license=True,
            has_readme=True,
            claude_code_integration_level=12,
        ))

    return results
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
pytest tests/test_fetchers.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add src/fetchers/vscode.py src/fetchers/docker.py tests/test_fetchers.py
git commit -m "feat: add VS Code Marketplace and Docker Hub fetchers"
```

---

## Task 6: Terminal Formatter

**Files:**
- Create: `src/formatter.py`
- Create: `tests/test_formatter.py`

- [ ] **Step 1: Write failing tests**

`tests/test_formatter.py`:
```python
from src.models import RawToolData, ScoredTool
from src.formatter import format_results, _integration_label

def _make_scored(category="recommended", total=80, integration=16) -> ScoredTool:
    t = RawToolData(
        name="test/repo", source="github",
        url="https://github.com/test/repo",
        description="A test tool", stars=2000,
        last_commit_days=10, has_security_md=True,
        has_license=True, license_type="MIT",
        claude_code_integration_level=integration,
    )
    return ScoredTool(t, 25, integration, 8, 12, 10, total, category, [])

def test_format_results_contains_top_section():
    output = format_results("test query", [_make_scored()], [])
    assert "Top 推薦" in output
    assert "test/repo" in output

def test_format_results_contains_watch_section_when_present():
    output = format_results("test query", [], [_make_scored(category="watch", total=65)])
    assert "觀察名單" in output

def test_format_results_shows_score():
    output = format_results("test query", [_make_scored(total=80)], [])
    assert "80" in output

def test_integration_label_mcp():
    assert _integration_label(20) == "MCP/Claude Code"

def test_integration_label_cli():
    assert _integration_label(16) == "CLI"

def test_format_results_no_results():
    output = format_results("nothing", [], [])
    assert "0 筆" in output or "無結果" in output
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_formatter.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Write src/formatter.py**

```python
from .models import ScoredTool


def _integration_label(level: int) -> str:
    return {20: "MCP/Claude Code", 16: "CLI", 12: "GitHub Actions",
            8: "Shell wrap", 4: "手動", 0: "不適合"}.get(level, "Shell wrap")


def _stars_label(stars: int) -> str:
    if stars >= 1000:
        return f"{stars / 1000:.1f}k"
    return str(stars)


def format_results(query: str, recommended: list[ScoredTool],
                   watch: list[ScoredTool], avoid: list[ScoredTool] = None) -> str:
    avoid = avoid or []
    total_found = len(recommended) + len(watch) + len(avoid)
    lines = [f"\nGitHub Scout 結果：{query}（共 {total_found} 筆，評分 ≥70 顯示前 5）\n"]

    if recommended:
        lines.append("== Top 推薦 ==\n")
        for i, s in enumerate(recommended[:5], 1):
            t = s.data
            lines.append(
                f"#{i}  {t.name:<40} [{t.source.upper()}]  評分 {s.total}\n"
                f"    {t.description[:70]}\n"
                f"    Stars {_stars_label(t.stars)}  最近 commit {t.last_commit_days} 天前\n"
                f"    安全 {s.security_score}  整合 {s.integration_score}（{_integration_label(s.integration_score)}）"
                f"  可信 {s.credibility_score}  回覆 {s.response_score}  Stars {s.stars_score}\n"
                f"    CVE {t.cve_count}  依賴漏洞 {t.dep_vuln_count}"
                f"  SECURITY.md {'✓' if t.has_security_md else '✗'}"
                f"  LICENSE {t.license_type or '?'}\n"
                f"    {t.url}\n"
            )
    else:
        lines.append("無結果達到推薦門檻（評分 ≥70）。\n")

    if watch:
        lines.append("\n== 觀察名單（整合性不足或分數偏低但有潛力）==\n")
        for s in watch[:5]:
            warn_str = "，".join(s.warnings[:2]) if s.warnings else "無"
            lines.append(f"- {s.data.name}  評分 {s.total}  ── {warn_str}  {s.data.url}\n")

    if avoid:
        lines.append("\n== 不建議安裝 ==\n")
        for s in avoid[:5]:
            warn_str = "，".join(s.warnings[:2]) if s.warnings else "安全分數不足"
            lines.append(f"- {s.data.name}  ── {warn_str}\n")

    return "".join(lines)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_formatter.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/formatter.py tests/test_formatter.py
git commit -m "feat: add terminal formatter"
```

---

## Task 7: Notion Writer

**Files:**
- Create: `src/notion_writer.py`
- Create: `tests/test_notion_writer.py`

- [ ] **Step 1: Write failing tests**

`tests/test_notion_writer.py`:
```python
from unittest.mock import MagicMock, patch
from src.notion_writer import _toggle_block, _bullet, write_scan_results
from src.models import RawToolData, ScoredTool

def _make_scored(name="test/repo", total=80) -> ScoredTool:
    t = RawToolData(name=name, source="github",
                    url=f"https://github.com/{name}",
                    description="desc", stars=1000)
    return ScoredTool(t, 25, 16, 8, 12, 10, total, "recommended", [])

def test_toggle_block_structure():
    block = _toggle_block("Title", [])
    assert block["type"] == "toggle"
    assert block["toggle"]["rich_text"][0]["text"]["content"] == "Title"
    assert block["toggle"]["children"] == []

def test_bullet_structure():
    b = _bullet("hello")
    assert b["type"] == "bulleted_list_item"
    assert b["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "hello"

def test_write_scan_results_calls_notion_api():
    mock_client = MagicMock()
    mock_client.blocks.children.append.return_value = {
        "results": [{"id": "fake-block-id"}]
    }
    with patch("src.notion_writer._client", return_value=mock_client):
        write_scan_results(
            page_id="page-id",
            date_label="2026-05-18",
            recommended=[_make_scored()],
            watch=[],
            avoid=[],
            integration_notes="Use test/repo as MCP server",
        )
    assert mock_client.blocks.children.append.call_count == 2
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_notion_writer.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Write src/notion_writer.py**

```python
import os
from notion_client import Client

from .models import ScoredTool


def _client() -> Client:
    return Client(auth=os.environ["NOTION_TOKEN"])


def _toggle_block(title: str, children: list[dict]) -> dict:
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": title}}],
            "children": children,
        },
    }


def _bullet(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": text[:2000]}}]
        },
    }


def _tool_bullet(s: ScoredTool) -> dict:
    t = s.data
    text = (
        f"{t.name}  評分 {s.total}  ── {t.description[:60]}"
        f"  安全 {s.security_score} 整合 {s.integration_score}"
        f"  {t.url}"
    )
    return _bullet(text)


def write_scan_results(
    page_id: str,
    date_label: str,
    recommended: list[ScoredTool],
    watch: list[ScoredTool],
    avoid: list[ScoredTool],
    integration_notes: str,
) -> None:
    client = _client()

    # Step 1: Create the date toggle (empty, no children yet)
    result = client.blocks.children.append(
        block_id=page_id,
        children=[_toggle_block(f"{date_label} 掃描結果", [])],
    )
    date_block_id = result["results"][0]["id"]

    # Step 2: Append 4 sub-toggles with bullets inside
    # Each category toggle includes its bullet children (max 100 per append)
    rec_bullets = [_tool_bullet(s) for s in recommended[:20]]
    watch_bullets = [_tool_bullet(s) for s in watch[:20]]
    avoid_bullets = [
        _bullet(f"{s.data.name}  ── {'，'.join(s.warnings[:2])}")
        for s in avoid[:20]
    ]

    client.blocks.children.append(
        block_id=date_block_id,
        children=[
            _toggle_block(f"Top 推薦（{len(recommended)} 筆）", rec_bullets),
            _toggle_block(f"觀察名單（{len(watch)} 筆）", watch_bullets),
            _toggle_block(f"不建議安裝（{len(avoid)} 筆）", avoid_bullets),
            _toggle_block("Claude Code 整合建議", [_bullet(integration_notes)]),
        ],
    )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_notion_writer.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/notion_writer.py tests/test_notion_writer.py
git commit -m "feat: add Notion writer with toggle block structure"
```

---

## Task 8: Main CLI Entry Point

**Files:**
- Create: `github_scout.py`

- [ ] **Step 1: Write github_scout.py**

```python
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).parent
_CONFIG = json.loads((_ROOT / "config.json").read_text(encoding="utf-8"))


def _load_fetchers():
    from src.fetchers.github import fetch_github
    from src.fetchers.vscode import fetch_vscode
    from src.fetchers.docker import fetch_docker
    return fetch_github, fetch_vscode, fetch_docker


def _fetch_all(query: str) -> list:
    fetch_github, fetch_vscode, fetch_docker = _load_fetchers()
    max_r = _CONFIG.get("max_results_per_query", 10)
    results = []
    results.extend(fetch_github(query, max_r))
    results.extend(fetch_vscode(query, max_r // 2))
    results.extend(fetch_docker(query, max_r // 2))
    return results


def _score_and_split(raw_tools):
    from src.scorer import score_tool
    scored = [score_tool(t) for t in raw_tools]
    recommended = [s for s in scored if s.category == "recommended"]
    watch = [s for s in scored if s.category == "watch"]
    avoid = [s for s in scored if s.category == "avoid"]
    recommended.sort(key=lambda s: s.total, reverse=True)
    return recommended, watch, avoid


def _integration_notes(recommended: list) -> str:
    if not recommended:
        return "本週無達到推薦門檻的工具。"
    top = recommended[0]
    level = top.data.claude_code_integration_level
    label = {20: "MCP server", 16: "CLI 呼叫", 12: "GitHub Actions 整合"}.get(level, "Shell 包裝")
    return f"本週最推薦：{top.data.name}（{label}，評分 {top.total}）。{top.data.url}"


def cmd_query(query: str, save: bool) -> None:
    from src.formatter import format_results
    raw = _fetch_all(query)
    recommended, watch, avoid = _score_and_split(raw)
    print(format_results(query, recommended, watch, avoid))

    if save:
        from src.notion_writer import write_scan_results
        date_label = datetime.now().strftime("%Y-%m-%d")
        write_scan_results(
            page_id=_CONFIG["notion_page_id"],
            date_label=f"{date_label} 手動查詢：{query}",
            recommended=recommended,
            watch=watch,
            avoid=avoid,
            integration_notes=_integration_notes(recommended),
        )
        print(f"\n已寫入 Notion。")


def cmd_scan() -> None:
    from src.notion_writer import write_scan_results
    from src.formatter import format_results

    keywords = _CONFIG.get("scan_keywords", [])
    all_recommended, all_watch, all_avoid = [], [], []

    for kw in keywords:
        raw = _fetch_all(kw)
        rec, watch, avoid = _score_and_split(raw)
        all_recommended.extend(rec)
        all_watch.extend(watch)
        all_avoid.extend(avoid)

    # Deduplicate by URL
    seen = set()
    def dedup(lst):
        result = []
        for s in lst:
            if s.data.url not in seen:
                seen.add(s.data.url)
                result.append(s)
        return result

    all_recommended = sorted(dedup(all_recommended), key=lambda s: s.total, reverse=True)
    all_watch = dedup(all_watch)
    all_avoid = dedup(all_avoid)

    date_label = datetime.now().strftime("%Y-%m-%d")
    write_scan_results(
        page_id=_CONFIG["notion_page_id"],
        date_label=date_label,
        recommended=all_recommended,
        watch=all_watch,
        avoid=all_avoid,
        integration_notes=_integration_notes(all_recommended),
    )
    print(f"掃描完成。推薦 {len(all_recommended)} 筆，觀察名單 {len(all_watch)} 筆，"
          f"不建議 {len(all_avoid)} 筆。已寫入 Notion。")


def main():
    parser = argparse.ArgumentParser(description="GitHub Scout Agent")
    sub = parser.add_subparsers(dest="mode")

    q = sub.add_parser("--query", help="Manual search query")
    q.add_argument("query", nargs="+")
    q.add_argument("--save", action="store_true")

    sub.add_parser("--scan", help="Weekly scan using config keywords")

    # Support: python github_scout.py --query foo bar --save
    args, remaining = parser.parse_known_args()

    if "--query" in sys.argv:
        idx = sys.argv.index("--query")
        query_args = []
        save = False
        for a in sys.argv[idx + 1:]:
            if a == "--save":
                save = True
            elif not a.startswith("--"):
                query_args.append(a)
        query = " ".join(query_args)
        cmd_query(query, save)
    elif "--scan" in sys.argv:
        cmd_scan()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test manual query**

```bash
cd C:\Users\USER1502\github-scout
python github_scout.py --query opc-ua python
```

Expected: output shows GitHub Scout results. If `GITHUB_TOKEN` is not set, results may be limited by rate limit but should not crash.

- [ ] **Step 3: Commit**

```bash
git add github_scout.py
git commit -m "feat: add CLI entry point with --query and --scan modes"
```

---

## Task 9: Claude Code Slash Command

**Files:**
- Create: `.claude/commands/github-scout.md`

- [ ] **Step 1: Write .claude/commands/github-scout.md**

```markdown
Search GitHub, VS Code Marketplace, and Docker Hub for developer tools matching the query.

Run the following command and display the exact output to the user:

```bash
python C:\Users\USER1502\github-scout\github_scout.py --query $ARGUMENTS
```

If the arguments include `--save`, also pass `--save` to write the results to Notion.

Show the full output exactly as printed. Do not summarize or modify the output.
```

- [ ] **Step 2: Test the slash command**

In Claude Code terminal, type:
```
/github-scout opc-ua python
```

Expected: Claude Code runs the Python script and displays the search results.

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/github-scout.md
git commit -m "feat: add /github-scout Claude Code slash command"
```

---

## Task 10: Windows Task Scheduler XML

**Files:**
- Create: `task_scheduler.xml`

- [ ] **Step 1: Write task_scheduler.xml**

```xml
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-05-18T08:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek>
        <WeeksInterval>1</WeeksInterval>
        <DaysOfWeek>
          <Monday />
        </DaysOfWeek>
      </ScheduleByWeek>
    </CalendarTrigger>
  </Triggers>
  <Actions Context="Author">
    <Exec>
      <Command>python</Command>
      <Arguments>C:\Users\USER1502\github-scout\github_scout.py --scan</Arguments>
      <WorkingDirectory>C:\Users\USER1502\github-scout</WorkingDirectory>
    </Exec>
  </Actions>
  <Settings>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
  </Settings>
</Task>
```

- [ ] **Step 2: Import into Task Scheduler**

Open PowerShell as Administrator:
```powershell
schtasks /create /xml "C:\Users\USER1502\github-scout\task_scheduler.xml" /tn "GitHubScout-WeeklyScan" /f
```

Expected: `SUCCESS: The scheduled task "GitHubScout-WeeklyScan" has successfully been created.`

- [ ] **Step 3: Verify the task exists**

```powershell
schtasks /query /tn "GitHubScout-WeeklyScan" /fo LIST
```

Expected: task listed with trigger "每週一 08:00".

- [ ] **Step 4: Commit**

```bash
git add task_scheduler.xml
git commit -m "chore: add Windows Task Scheduler XML for weekly scan"
```

---

## Task 11: Error Logging

**Files:**
- Modify: `github_scout.py`

- [ ] **Step 1: Add error logging to main()**

Edit `github_scout.py`, replace the `main()` function with:

```python
import logging
from pathlib import Path

_LOG_PATH = Path(__file__).parent / "logs" / "error.log"
_LOG_PATH.parent.mkdir(exist_ok=True)
logging.basicConfig(
    filename=str(_LOG_PATH),
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
)


def main():
    try:
        parser = argparse.ArgumentParser(description="GitHub Scout Agent")
        if "--query" in sys.argv:
            idx = sys.argv.index("--query")
            query_args = []
            save = False
            for a in sys.argv[idx + 1:]:
                if a == "--save":
                    save = True
                elif not a.startswith("--"):
                    query_args.append(a)
            query = " ".join(query_args)
            if not query:
                print("Usage: python github_scout.py --query <keywords> [--save]")
                sys.exit(1)
            cmd_query(query, save)
        elif "--scan" in sys.argv:
            cmd_scan()
        else:
            print("Usage:\n  --query <keywords> [--save]\n  --scan")
            sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        logging.exception("Fatal error")
        print(f"Error: {e}\nDetails written to {_LOG_PATH}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run all tests to confirm nothing broke**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add github_scout.py
git commit -m "feat: add error logging to logs/error.log"
```

---

## Final Checklist (Self-Review)

- [x] Spec §1 目標: `--query` (Task 8) + `--scan` (Task 8) + Notion (Task 7)
- [x] Spec §2 架構: `github_scout.py` + `src/` modules + `.env` + `config.json`
- [x] Spec §3 資料來源: GitHub (Task 4), VS Code (Task 5), Docker (Task 5)
- [x] Spec §4 評分: scorer v0.2 全部實作 (Task 3)
- [x] Spec §4 硬性門檻: 安全 <25 → avoid, 整合 <8 → watch (Task 3)
- [x] Spec §5 輸出格式: formatter (Task 6) + notion_writer (Task 7)
- [x] Spec §6 config.json: 不存 token (Task 1)
- [x] Spec §7 排程: task_scheduler.xml (Task 10)
- [x] Token 安全: .env + python-dotenv (Task 1 + Task 8)
- [x] 錯誤處理: VS Code fetcher failure isolated (Task 5), error.log (Task 11)
