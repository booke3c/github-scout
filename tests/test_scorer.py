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
