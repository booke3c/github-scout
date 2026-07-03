"""AI 訊號週報：週掃高訊號來源(RSS + 少量爬取)，只報新增，LLM 一句摘要 + 相關度。

設計沿用 github-scout 的本機+排程+Notion 模式，但職責獨立(看 blog/news，不是 GitHub 工具)。
- RSS 來源用 feedparser(穩)。
- 無 RSS 的(Anthropic news)best-effort 爬，失敗就略過該來源、不拖垮整體。
- 狀態檔 feeds_state.json 記每個來源看過的 URL，每週只報新增；首跑只取最新數筆當起點避免洪水。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from src.resilient import resilient_create

_ROOT = Path(__file__).resolve().parent.parent
_STATE_PATH = _ROOT / "feeds_state.json"
_KEY_FILE = Path(os.environ.get("ANTHROPIC_KEY_FILE",
                                "C:/Users/USER1502/.config/qfa/anthropic_api_key.txt"))

SOURCES = [
    {"key": "simonw", "name": "Simon Willison", "type": "rss",
     "url": "https://simonwillison.net/atom/everything/"},
    {"key": "claudecode", "name": "Claude Code 更新", "type": "rss",
     "url": "https://github.com/anthropics/claude-code/releases.atom"},
    {"key": "importai", "name": "Import AI", "type": "rss",
     "url": "https://importai.substack.com/feed"},
    {"key": "latentspace", "name": "Latent Space", "type": "rss",
     "url": "https://www.latent.space/feed"},
    {"key": "hn_ai", "name": "Hacker News(AI 熱門)", "type": "rss",
     "url": "https://hnrss.org/newest?q=AI+OR+Claude+OR+LLM+OR+agent&points=80"},
    {"key": "anthropic", "name": "Anthropic News", "type": "scrape_anthropic",
     "url": "https://www.anthropic.com/news"},
]

# 首跑每個來源最多取幾筆當起點(避免第一次報幾百則)
_FIRST_RUN_CAP = 4
# 每來源每次最多納入幾則新項(控制 LLM 成本)
_PER_SOURCE_CAP = 8


def _resolve_anthropic_key() -> str | None:
    k = os.environ.get("ANTHROPIC_API_KEY")
    if k:
        return k.strip()
    if _KEY_FILE.exists():
        return _KEY_FILE.read_text(encoding="utf-8").strip()
    return None


def _load_state() -> dict:
    if _STATE_PATH.exists():
        try:
            return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(state: dict) -> None:
    _STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                           encoding="utf-8")


def _clean(text: str, n: int = 240) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:n]


def fetch_rss(src: dict, limit: int = 15):
    import feedparser
    d = feedparser.parse(src["url"])
    items = []
    for e in d.entries[:limit]:
        url = getattr(e, "link", "") or ""
        if not url:
            continue
        items.append({
            "source": src["name"], "key": src["key"],
            "title": _clean(getattr(e, "title", ""), 200),
            "url": url,
            "snippet": _clean(getattr(e, "summary", "") or
                              getattr(e, "description", ""), 240),
        })
    return items, None


def fetch_anthropic(src: dict, limit: int = 12):
    """無 RSS，best-effort 從 news 頁抓 /news/<slug> 連結與標題。"""
    try:
        import requests
    except ImportError:
        return [], "未安裝 requests"
    try:
        r = requests.get(src["url"], timeout=25,
                         headers={"User-Agent": "Mozilla/5.0 feed-scout"})
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        html = r.text
    except Exception as e:
        return [], str(e)[:160]
    seen, items = set(), []
    # 抓 href="/news/xxx" 連同錨文字當標題
    for m in re.finditer(r'href="(/news/[a-z0-9\-]+)"[^>]*>(.*?)</a>', html, re.S):
        path, label = m.group(1), _clean(m.group(2), 160)
        if path in seen or not label or len(label) < 6:
            continue
        seen.add(path)
        items.append({"source": src["name"], "key": src["key"],
                      "title": label, "url": "https://www.anthropic.com" + path,
                      "snippet": ""})
        if len(items) >= limit:
            break
    if not items:
        return [], "頁面結構改變、抓不到 /news 連結"
    return items, None


def fetch_source(src: dict):
    try:
        if src["type"] == "rss":
            return fetch_rss(src)
        if src["type"] == "scrape_anthropic":
            return fetch_anthropic(src)
        return [], f"未知來源型別 {src['type']}"
    except Exception as e:  # noqa: BLE001
        return [], str(e)[:160]


def collect_new():
    """回傳 (new_items, errors, state)。只含上次未看過的；首跑取最新數筆當起點。"""
    state = _load_state()
    new_items, errors = [], {}
    for src in SOURCES:
        items, err = fetch_source(src)
        if err:
            errors[src["key"]] = err
        if not items:
            continue
        seen = set(state.get(src["key"], []))
        first_run = src["key"] not in state
        fresh = [it for it in items if it["url"] not in seen]
        if first_run:
            fresh = fresh[:_FIRST_RUN_CAP]
        else:
            fresh = fresh[:_PER_SOURCE_CAP]
        new_items.extend(fresh)
        # 更新狀態：把這次抓到的 URL 全記入(保留最近 300)
        merged = list(dict.fromkeys([it["url"] for it in items] +
                                    state.get(src["key"], [])))[:300]
        state[src["key"]] = merged
    return new_items, errors, state


# ---- LLM：批次摘要 + 相關度 ----

_PROFILE = """Steve：CNC 製造廠副總，重度 Claude Code 使用者、Python 自動化、跑一批真實
agent(台股bot、Notion自動化、CNC SCADA、PLC、Family OS);工業自動化 OPC-UA/CNC/SCADA;
cloud-first;對 agent 成本敏感。高相關=Claude Code/agent/MCP/Python自動化/LLM實務/工業自動化+AI;
低相關=純前端、遊戲、影片生成、與他無關的研究。"""


def summarize(items: list, model: str = "claude-sonnet-5") -> list:
    """對每則加 zh(一句繁中摘要) 與 rel(高/中/低)。LLM 失敗則降級為標題。"""
    if not items:
        return items
    key = _resolve_anthropic_key()
    if not key:
        for it in items:
            it["zh"], it["rel"] = it["title"], "中"
        return items
    try:
        import anthropic
    except ImportError:
        for it in items:
            it["zh"], it["rel"] = it["title"], "中"
        return items
    client = anthropic.Anthropic(api_key=key, timeout=60.0, max_retries=2)
    # 批次：一次最多 25 則，控制 token
    out = []
    for i in range(0, len(items), 25):
        batch = items[i:i + 25]
        listing = "\n".join(
            f"{j}. [{it['source']}] {it['title']} — {it['snippet'][:160]}"
            for j, it in enumerate(batch))
        prompt = (
            f"使用者畫像：{_PROFILE}\n\n以下是本週各來源新文章。對每則用繁體中文寫一句"
            f"(<=30字)摘要『這在講什麼』,並依畫像標相關度(高/中/低)。\n"
            f"只回 JSON 陣列,每元素 {{\"i\":序號,\"zh\":\"摘要\",\"rel\":\"高/中/低\"}}。\n\n{listing}")
        try:
            msg = resilient_create(
                client, model=model, max_tokens=2000,
                thinking={"type": "disabled"},
                system=[{"type": "text", "text": "你幫 Steve 過濾 AI 情報,精簡、不浮誇、繁中、無 emoji。",
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": prompt}])
            raw = msg.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```", 2)[1].lstrip("json").strip()
            parsed = {d["i"]: d for d in json.loads(raw)}
        except Exception:
            parsed = {}
        for j, it in enumerate(batch):
            d = parsed.get(j, {})
            it["zh"] = d.get("zh", it["title"])
            it["rel"] = d.get("rel", "中")
            out.append(it)
    return out


def overview(items: list, model: str = "claude-sonnet-5") -> str:
    """本週重點:2-3 句繁中整體摘要(新聞有什麼 + 對 Steve 值得注意的趨勢)。"""
    if not items:
        return ""
    key = _resolve_anthropic_key()
    if not key:
        return ""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key, timeout=60.0, max_retries=2)
        listing = "\n".join(
            f"[{it['source']}][{it.get('rel','中')}] {it.get('zh', it['title'])}"
            for it in items)
        prompt = (
            f"使用者畫像:{_PROFILE}\n\n以下是本週各來源新項(已標相關度)。用繁體中文寫 "
            f"2-3 句『本週重點』:整體在發生什麼、有沒有值得他特別注意的趨勢或單一大事。"
            f"精簡、不浮誇、無 emoji、不要逐條複述。\n\n{listing}")
        msg = resilient_create(
            client, model=model, max_tokens=560,
            thinking={"type": "disabled"},
            system=[{"type": "text", "text": "你幫 Steve 寫一週 AI 情報的開場重點,精簡犀利、繁中、無 emoji。",
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}])
        return msg.content[0].text.strip()
    except Exception:
        return ""
