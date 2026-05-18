from .models import ScoredTool


def _integration_label(level: int) -> str:
    return {20: "MCP/Claude Code", 16: "CLI", 12: "GitHub Actions",
            8: "Shell wrap", 4: "手動", 0: "不適合"}.get(level, "Shell wrap")


def _stars_label(stars: int) -> str:
    if stars >= 1000:
        return f"{stars / 1000:.1f}k"
    return str(stars)


def format_results(query: str, recommended: list[ScoredTool],
                   watch: list[ScoredTool], avoid: list[ScoredTool] = None) -> str:
    avoid = avoid or []
    total_found = len(recommended) + len(watch) + len(avoid)
    lines = [f"\nGitHub Scout 結果：{query}（共 {total_found} 筆，評分 >=70 顯示前 5）\n"]

    if recommended:
        lines.append("== Top 推薦 ==\n")
        for i, s in enumerate(recommended[:5], 1):
            t = s.data
            lines.append(
                f"#{i}  {t.name:<40} [{t.source.upper()}]  評分 {s.total}\n"
                f"    {t.description[:70]}\n"
                f"    Stars {_stars_label(t.stars)}  最近 commit {t.last_commit_days} 天前\n"
                f"    安全 {s.security_score}  整合 {s.integration_score}（{_integration_label(s.integration_score)}）"
                f"  可信 {s.credibility_score}  回覆 {s.response_score}  Stars {s.stars_score}\n"
                f"    CVE {t.cve_count}  依賴漏洞 {t.dep_vuln_count}"
                f"  SECURITY.md {'✓' if t.has_security_md else '✗'}"
                f"  LICENSE {t.license_type or '?'}\n"
                f"    {t.url}\n"
            )
    else:
        lines.append("無結果達到推薦門檻（評分 >=70）。\n")

    if watch:
        lines.append("\n== 觀察名單（整合性不足或分數偏低但有潛力）==\n")
        for s in watch[:5]:
            warn_str = "，".join(s.warnings[:2]) if s.warnings else "無"
            lines.append(f"- {s.data.name}  評分 {s.total}  ── {warn_str}  {s.data.url}\n")

    if avoid:
        lines.append("\n== 不建議安裝 ==\n")
        for s in avoid[:5]:
            warn_str = "，".join(s.warnings[:2]) if s.warnings else "安全分數不足"
            lines.append(f"- {s.data.name}  ── {warn_str}\n")

    return "".join(lines)
