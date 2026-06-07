import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).parent
_CONFIG = json.loads((_ROOT / "config.json").read_text(encoding="utf-8"))

_LOG_PATH = _ROOT / "logs" / "error.log"
_LOG_PATH.parent.mkdir(exist_ok=True)
logging.basicConfig(
    filename=str(_LOG_PATH),
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
)


def _load_fetchers():
    from src.fetchers.github import fetch_github
    from src.fetchers.vscode import fetch_vscode
    from src.fetchers.docker import fetch_docker
    return fetch_github, fetch_vscode, fetch_docker


def _fetch_all(query: str) -> list:
    fetch_github, fetch_vscode, fetch_docker = _load_fetchers()
    max_r = _CONFIG.get("max_results_per_query", 10)
    results = []
    results.extend(fetch_github(query, max_r))
    results.extend(fetch_vscode(query, max_r // 2))
    results.extend(fetch_docker(query, max_r // 2))
    return results


def _score_and_split(raw_tools):
    from src.scorer import score_tool
    scored = [score_tool(t) for t in raw_tools]
    recommended = [s for s in scored if s.category == "recommended"]
    watch = [s for s in scored if s.category == "watch"]
    avoid = [s for s in scored if s.category == "avoid"]
    recommended.sort(key=lambda s: s.total, reverse=True)
    return recommended, watch, avoid


def _integration_notes(recommended: list) -> str:
    if not recommended:
        return "本週無達到推薦門檻的工具。"
    top = recommended[0]
    level = top.data.claude_code_integration_level
    label = {20: "MCP server", 16: "CLI 呼叫", 12: "GitHub Actions 整合"}.get(level, "Shell 包裝")
    return f"本週最推薦：{top.data.name}（{label}，評分 {top.total}）。{top.data.url}"


def cmd_query(query: str, save: bool) -> None:
    from src.formatter import format_results
    raw = _fetch_all(query)
    recommended, watch, avoid = _score_and_split(raw)
    print(format_results(query, recommended, watch, avoid))

    if save:
        from src.notion_writer import write_scan_results, NotionWriteError
        date_label = datetime.now().strftime("%Y-%m-%d")
        try:
            write_scan_results(
                page_id=_CONFIG["notion_page_id"],
                date_label=f"{date_label} 手動查詢：{query}",
                recommended=recommended,
                watch=watch,
                avoid=avoid,
                integration_notes=_integration_notes(recommended),
            )
            print("\n已寫入 Notion。")
        except NotionWriteError as e:
            logging.error("Notion write failed (query): %s", e)
            print(f"\n[警告] 查詢結果未能寫入 Notion：{e}")
            print("上方終端機結果即為完整查詢輸出，未遺失。")


def cmd_scan(write_notion: bool = True) -> None:
    """本機個人化掃描：先盤點你已裝的 → 比對略過 → 推薦只留你還沒有的。"""
    from src.formatter import format_scan
    from src.scorer import score_tool
    from src.inventory import get_installed_inventory, is_installed

    inv = get_installed_inventory()

    keywords = _CONFIG.get("scan_keywords", [])
    seen = set()
    all_scored = []
    for kw in keywords:
        for t in _fetch_all(kw):
            if t.url in seen:
                continue
            seen.add(t.url)
            all_scored.append(score_tool(t))

    # 先依「是否已裝」分流：已裝的略過不推薦
    installed, fresh = [], []
    for s in all_scored:
        (installed if is_installed(s.data.name, inv) else fresh).append(s)

    recommended = sorted([s for s in fresh if s.category == "recommended"],
                         key=lambda s: s.total, reverse=True)
    consider = [s for s in fresh if s.category == "watch"]
    avoid = [s for s in fresh if s.category == "avoid"]

    date_label = datetime.now().strftime("%Y-%m-%d")
    title = f"GitHub Scout 個人化掃描　{date_label}"
    report = format_scan(title, inv, installed, recommended, consider, avoid)
    summary = (f"已裝略過 {len(installed)}　建議裝 {len(recommended)}　"
               f"可考慮 {len(consider)}　不建議 {len(avoid)}。")

    if not write_notion:
        print(report)
        print(f"\n{summary}（--no-notion：未寫入 Notion）")
        return

    from src.notion_writer import write_scan_results, NotionWriteError
    try:
        write_scan_results(
            page_id=_CONFIG["notion_page_id"],
            date_label=date_label,
            recommended=recommended,
            watch=consider,
            avoid=avoid,
            integration_notes=_integration_notes(recommended),
            installed=installed,
        )
        print(report)
        print(f"\n{summary}已寫入 Notion。")
    except NotionWriteError as e:
        # Notion 寫入失敗時，把整批結果印在終端機，避免數分鐘掃描白跑。
        logging.error("Notion write failed (scan): %s", e)
        print(report)
        print(f"\n{summary}\n[警告] 寫入 Notion 失敗：{e}")
        print("以上為本地完整結果，未寫入 Notion。請稍後重跑或檢查 Notion 狀態。")
        sys.exit(2)


def main():
    try:
        no_notion = "--no-notion" in sys.argv
        if "--query" in sys.argv:
            idx = sys.argv.index("--query")
            query_args = []
            save = False
            for a in sys.argv[idx + 1:]:
                if a == "--save":
                    save = True
                elif not a.startswith("--"):
                    query_args.append(a)
            if no_notion:
                save = False
            query = " ".join(query_args)
            if not query:
                print("Usage: python github_scout.py --query <keywords> [--save]")
                sys.exit(1)
            cmd_query(query, save)
        elif "--scan" in sys.argv:
            cmd_scan(write_notion=not no_notion)
        else:
            print("Usage:\n"
                  "  python github_scout.py --query <keywords> [--save]\n"
                  "  python github_scout.py --scan [--no-notion]")
            sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        logging.exception("Fatal error")
        print(f"Error: {e}\nDetails written to {_LOG_PATH}")
        sys.exit(1)


if __name__ == "__main__":
    main()
