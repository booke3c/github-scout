from src.models import RawToolData, ScoredTool


def test_raw_tool_data_defaults():
    t = RawToolData(
        name="a/b",
        source="github",
        url="https://github.com/a/b",
        description="test"
    )
    assert t.stars == 0
    assert t.last_commit_days == 9999
    assert t.claude_code_integration_level == 4
    assert t.data_complete is True


def test_scored_tool_fields():
    t = RawToolData(
        name="a/b",
        source="github",
        url="https://github.com/a/b",
        description="test"
    )
    s = ScoredTool(
        data=t,
        security_score=25,
        integration_score=16,
        stars_score=8,
        credibility_score=12,
        response_score=10,
        total=71,
        category="recommended",
        warnings=[]
    )
    assert s.total == 71
    assert s.category == "recommended"
