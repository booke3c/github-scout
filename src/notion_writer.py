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

    result = client.blocks.children.append(
        block_id=page_id,
        children=[_toggle_block(f"{date_label} 掃描結果", [])],
    )
    date_block_id = result["results"][0]["id"]

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
