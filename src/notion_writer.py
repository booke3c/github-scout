import logging
import os
import time

from notion_client import Client
from notion_client.errors import HTTPResponseError, RequestTimeoutError

from .models import ScoredTool

# Transient HTTP statuses worth retrying (Notion gateway / rate limit).
_TRANSIENT_STATUS = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 5
_BACKOFF_BASE = 2.0   # seconds
_BACKOFF_CAP = 30.0   # seconds


class NotionWriteError(Exception):
    """Raised when a Notion write fails after exhausting retries.

    The caller should fall back to printing results locally so a
    multi-minute scan is never silently lost.
    """


def _client() -> Client:
    return Client(auth=os.environ["NOTION_TOKEN"])


def _retry_after_seconds(err: HTTPResponseError, attempt: int) -> float:
    """Honor Notion's Retry-After header for 429; otherwise exponential."""
    headers = getattr(err, "headers", None) or {}
    ra = headers.get("Retry-After") or headers.get("retry-after")
    if ra:
        try:
            return min(float(ra), _BACKOFF_CAP)
        except (TypeError, ValueError):
            pass
    return min(_BACKOFF_BASE * (2 ** attempt), _BACKOFF_CAP)


def _append_with_retry(client: Client, block_id: str, children: list[dict]) -> dict:
    """blocks.children.append with retry on transient Notion failures."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return client.blocks.children.append(block_id=block_id, children=children)
        except HTTPResponseError as e:
            last_exc = e
            status = getattr(e, "status", None)
            if status not in _TRANSIENT_STATUS or attempt == _MAX_ATTEMPTS - 1:
                # Non-transient (e.g. 400 bad payload, 401 auth) -> don't retry.
                if status not in _TRANSIENT_STATUS:
                    raise NotionWriteError(
                        f"Notion 回傳非暫時性錯誤 {status}，不重試：{e}"
                    ) from e
                break
            wait = _retry_after_seconds(e, attempt)
            logging.warning(
                "Notion append 第 %d/%d 次失敗 (status %s)，%.1fs 後重試",
                attempt + 1, _MAX_ATTEMPTS, status, wait,
            )
            time.sleep(wait)
        except RequestTimeoutError as e:
            last_exc = e
            if attempt == _MAX_ATTEMPTS - 1:
                break
            wait = min(_BACKOFF_BASE * (2 ** attempt), _BACKOFF_CAP)
            logging.warning(
                "Notion append 第 %d/%d 次逾時，%.1fs 後重試",
                attempt + 1, _MAX_ATTEMPTS, wait,
            )
            time.sleep(wait)
    raise NotionWriteError(
        f"Notion 寫入重試 {_MAX_ATTEMPTS} 次後仍失敗：{last_exc}"
    ) from last_exc


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


def _tool_bullet(s: ScoredTool, verdict: str = "建議裝") -> dict:
    t = s.data
    # 功能說明放前面、加長到 110 字，讓「這是什麼、要不要裝」一眼看懂
    text = (
        f"【{verdict}】{t.name}　功能：{(t.description or '（無描述）')[:110]}"
        f"　｜評分 {s.total}／安全 {s.security_score}／Stars {t.stars}　{t.url}"
    )
    return _bullet(text)


def write_scan_results(
    page_id: str,
    date_label: str,
    recommended: list[ScoredTool],
    watch: list[ScoredTool],
    avoid: list[ScoredTool],
    integration_notes: str,
    installed: list[ScoredTool] | None = None,
) -> None:
    """Append a dated scan report to the Notion page.

    installed：本次掃到、但你已安裝而略過的工具（顯示出來，證明有做盤點比對）。
    Raises NotionWriteError if the write cannot be persisted after
    retries so the caller can fall back to local output.
    """
    client = _client()

    result = _append_with_retry(
        client, page_id, [_toggle_block(f"{date_label} 掃描結果", [])]
    )
    date_block_id = result["results"][0]["id"]

    rec_bullets = [_tool_bullet(s, "建議裝") for s in recommended[:20]]
    watch_bullets = [_tool_bullet(s, "可考慮") for s in watch[:20]]
    avoid_bullets = [
        _bullet(f"【不建議】{s.data.name}　── {'，'.join(s.warnings[:2])}")
        for s in avoid[:20]
    ]

    blocks = []
    if installed:
        names = "、".join(s.data.name for s in installed[:25])
        blocks.append(_toggle_block(
            f"你已經有的·已略過不重複推薦（{len(installed)} 個）", [_bullet(names)]))
    blocks += [
        _toggle_block(f"建議裝·你還沒有且符合需求（{len(recommended)} 筆）", rec_bullets),
        _toggle_block(f"可考慮·有潛力自行斟酌（{len(watch)} 筆）", watch_bullets),
        _toggle_block(f"不建議·安全或品質疑慮（{len(avoid)} 筆）", avoid_bullets),
        _toggle_block("Claude Code 整合建議", [_bullet(integration_notes)]),
    ]

    _append_with_retry(client, date_block_id, blocks)
