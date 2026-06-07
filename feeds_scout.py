"""AI 訊號週報 — 本機週掃高訊號來源 → LLM 摘要+相關度 → 寫 Notion 新頁。

用法:
  python feeds_scout.py --scan            # 跑並寫 Notion(首跑自動建子頁)
  python feeds_scout.py --scan --no-notion  # 乾跑,只印終端、不寫 Notion、不更新狀態

設定/狀態:
  feeds_config.json  parent_page_id(母頁)/ digest_page_id(週報頁,首跑自動建)
  feeds_state.json   每來源看過的 URL(只報新增)
沿用 github-scout 的 .env(NOTION_TOKEN)、anthropic key(qfa 檔)、Windows 週排程。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

from src.feeds import collect_new, summarize, overview, _save_state, SOURCES

_ROOT = Path(__file__).resolve().parent
_CONFIG = _ROOT / "feeds_config.json"
_DEFAULT_PARENT = "361967ffe82f808dad92c6669ce93a45"
_REL_ORDER = {"高": 0, "中": 1, "低": 2}


def _load_cfg():
    if _CONFIG.exists():
        return json.loads(_CONFIG.read_text(encoding="utf-8"))
    return {"parent_page_id": _DEFAULT_PARENT, "digest_page_id": None}


def _save_cfg(cfg):
    _CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _render_terminal(items, errors, ov=""):
    lines = [f"AI 訊號週報 {datetime.now():%Y-%m-%d}　新增 {len(items)} 則\n"]
    if ov:
        lines.append("== 本週重點 ==")
        lines.append(ov + "\n")
    high = [it for it in items if it.get("rel") == "高"]
    lines.append(f"== 高度適合你（{len(high)}）==")
    if high:
        for it in high:
            lines.append(f"  ★ {it.get('zh','')}")
            lines.append(f"     {it['title'][:60]}  {it['url']}")
    else:
        lines.append("  （本週沒有標為『高』的）")
    lines.append("")
    by_src = {}
    for it in items:
        by_src.setdefault(it["source"], []).append(it)
    for src in SOURCES:
        lst = by_src.get(src["name"], [])
        if not lst:
            continue
        lst.sort(key=lambda x: _REL_ORDER.get(x.get("rel", "中"), 1))
        lines.append(f"== {src['name']}（{len(lst)}）==")
        for it in lst:
            lines.append(f"  【{it.get('rel','?')}】{it.get('zh','')}")
            lines.append(f"     {it['title'][:60]}  {it['url']}")
        lines.append("")
    if errors:
        lines.append("抓不到的來源：" + "、".join(f"{k}（{v}）" for k, v in errors.items()))
    return "\n".join(lines)


def _para(text, bold=False):
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
        {"type": "text", "text": {"content": text[:1900]},
         "annotations": {"bold": bold}}]}}


def _h3(text):
    return {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [
        {"type": "text", "text": {"content": text}}]}}


def _write_notion(cfg, items, errors, ov=""):
    from src.notion_writer import _client, _append_with_retry, _toggle_block, _bullet
    client = _client()
    # 首跑建子頁
    if not cfg.get("digest_page_id"):
        page = client.pages.create(
            parent={"page_id": cfg["parent_page_id"]},
            properties={"title": [{"text": {"content": "AI 訊號週報"}}]},
        )
        cfg["digest_page_id"] = page["id"]
        _save_cfg(cfg)
        print(f"[*] 已建立 Notion 週報頁：{page['id']}")

    date_label = datetime.now().strftime("%Y-%m-%d")
    # 外層 toggle
    result = _append_with_retry(
        client, cfg["digest_page_id"],
        [_toggle_block(f"AI 訊號週報 {date_label}（新增 {len(items)} 則）", [])])
    box_id = result["results"][0]["id"]

    by_src = {}
    for it in items:
        by_src.setdefault(it["source"], []).append(it)

    # 本週重點(放在 toggle 最上面):整體摘要 + 高度適合你
    children = []
    if ov:
        children.append(_para("本週重點", bold=True))
        children.append(_para(ov))
    high = [it for it in items if it.get("rel") == "高"]
    children.append(_h3(f"高度適合你（{len(high)}）"))
    if high:
        for it in high:
            children.append(_bullet(f"★ {it.get('zh','')}　|　"
                                    f"{it['title'][:60]}　{it['url']}"))
    else:
        children.append(_bullet("本週沒有標為『高』的"))

    for src in SOURCES:
        lst = by_src.get(src["name"], [])
        if not lst:
            continue
        lst.sort(key=lambda x: _REL_ORDER.get(x.get("rel", "中"), 1))
        bullets = [_bullet(f"【{it.get('rel','?')}】{it.get('zh','')}　|　"
                           f"{it['title'][:60]}　{it['url']}") for it in lst]
        children.append(_toggle_block(f"{src['name']}（{len(lst)}）", bullets))
    if errors:
        children.append(_bullet("抓不到的來源：" +
                        "、".join(f"{k}（{v}）" for k, v in errors.items())))
    if children:
        _append_with_retry(client, box_id, children)


def main():
    no_notion = "--no-notion" in sys.argv
    if "--scan" not in sys.argv:
        print("用法: python feeds_scout.py --scan [--no-notion]")
        sys.exit(1)

    items, errors, state = collect_new()
    items = summarize(items)
    items.sort(key=lambda x: _REL_ORDER.get(x.get("rel", "中"), 1))
    ov = overview(items)

    if no_notion:
        print(_render_terminal(items, errors, ov))
        print(f"\n（--no-notion：未寫 Notion、未更新狀態。新增 {len(items)} 則）")
        return

    cfg = _load_cfg()
    if items or errors:
        try:
            _write_notion(cfg, items, errors, ov)
            _save_state(state)   # 寫成功才更新狀態,避免漏報
            print(f"[OK] 已寫入 Notion，新增 {len(items)} 則。頁：{cfg.get('digest_page_id')}")
        except Exception as e:
            print(f"[警告] 寫入 Notion 失敗：{e}")
            print(_render_terminal(items, errors, ov))
            sys.exit(2)
    else:
        _save_state(state)
        print("本週無新增。")


if __name__ == "__main__":
    main()
