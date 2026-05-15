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
