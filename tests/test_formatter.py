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
