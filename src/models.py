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
