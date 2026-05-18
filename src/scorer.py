from .models import RawToolData, ScoredTool


def _score_security(t: RawToolData) -> tuple[int, list[str]]:
    # 0-35 band (matches spec). Baseline-expected signals weighted modestly;
    # absence of known vulnerabilities weighted heaviest.
    score = 0
    if t.has_license: score += 5
    if t.has_security_md: score += 6
    if t.has_signed_release: score += 4
    if t.has_lockfile: score += 3
    if t.cve_count == 0: score += 9
    if t.dep_vuln_count == 0: score += 8

    warnings = []
    # Penalty graded by real severity. curl|bash / write-all / many open
    # security issues are genuine smells; unpinned actions and `secrets.`
    # references are near-universal in healthy repos -> informational only.
    danger_flags = [
        (t.requires_curl_bash, 12, "README requires curl|bash install"),
        (t.requires_write_all, 8, "workflow requires write-all permissions"),
        (t.unresolved_security_issues > 5, 8,
         f"{t.unresolved_security_issues} unresolved security issues"),
        (t.action_unpinned, 2, "GitHub Action not pinned to SHA (info)"),
        (t.accesses_secrets, 0,
         "workflow references secrets (info, common in CI)"),
    ]
    for flag, penalty, msg in danger_flags:
        if flag:
            score = max(0, score - penalty)
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
    # security 0-35: <10 means almost no positive signals or hit by a
    # severe penalty (curl|bash, write-all, many open security issues).
    if security < 10:
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
    # curl|bash piping a remote script straight into a shell is a
    # categorical supply-chain risk -> hard avoid regardless of other scores.
    if t.requires_curl_bash:
        category = "avoid"
    if t.last_commit_days > 365 and category == "recommended":
        category = "watch"

    return ScoredTool(t, security, integration, stars, credibility, response,
                      total, category, warnings)
