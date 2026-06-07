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


def format_scan(title: str, inventory: dict, installed: list[ScoredTool],
                recommended: list[ScoredTool], consider: list[ScoredTool],
                avoid: list[ScoredTool]) -> str:
    """個人化掃描輸出：先盤點你已有的，再給「你還沒有」的推薦(附功能摘要 + 裝/不裝建議)。"""
    src = inventory.get("sources", {})
    lines = [f"\n{title}\n"]

    # 1) 先盤點你已經有的
    lines.append("== 你已經有的（本機盤點）==\n")
    lines.append(
        f"VS Code 擴充 {len(src.get('vscode', []))}　Docker {len(src.get('docker', []))}　"
        f"pip {len(src.get('pip', []))}　npm {len(src.get('npm', []))}　"
        f"Claude MCP {len(src.get('claude_mcp', []))}　skills {len(src.get('claude_skills', []))}\n"
    )
    if inventory.get("errors"):
        lines.append("（這些來源沒抓到：" +
                     "、".join(f"{k}（{v}）" for k, v in inventory["errors"].items()) + "）\n")
    if installed:
        names = "、".join(s.data.name for s in installed[:12])
        more = f" 等 {len(installed)} 個" if len(installed) > 12 else ""
        lines.append(f"本次掃到、你已經裝過的（已略過不重複推薦）：{names}{more}\n")

    # 2) 建議裝：你還沒有、符合需求、分數夠
    lines.append("\n== 建議裝（你還沒有，且符合需求）==\n")
    if recommended:
        for i, s in enumerate(recommended[:10], 1):
            t = s.data
            lines.append(
                f"#{i}  {t.name}　[{t.source.upper()}]　評分 {s.total}　【建議裝】\n"
                f"     功能：{(t.description or '（無描述）')[:90]}\n"
                f"     安全 {s.security_score}　整合 {_integration_label(s.integration_score)}　"
                f"Stars {_stars_label(t.stars)}\n"
                f"     {t.url}\n\n"
            )
    else:
        lines.append("（本次沒有你還沒裝、又達標的新工具）\n")

    # 3) 可考慮：有潛力但分數/整合性偏弱
    if consider:
        lines.append("== 可考慮（有潛力，自行斟酌）==\n")
        for s in consider[:8]:
            warn = "，".join(s.warnings[:2]) if s.warnings else "分數偏低"
            lines.append(f"-  {s.data.name}　評分 {s.total}　【可考慮】　功能："
                         f"{(s.data.description or '')[:60]}　── {warn}\n     {s.data.url}\n")
        lines.append("\n")

    # 4) 不建議
    if avoid:
        lines.append("== 不建議（安全/品質疑慮）==\n")
        for s in avoid[:8]:
            warn = "，".join(s.warnings[:2]) if s.warnings else "安全分數不足"
            lines.append(f"-  {s.data.name}　【不建議】　── {warn}\n")

    return "".join(lines)
