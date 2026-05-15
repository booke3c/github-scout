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
