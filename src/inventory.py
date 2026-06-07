"""盤點本機已安裝的開發工具，給 scout 排除「你已經有的」。

四個來源(各自獨立容錯，缺工具就跳過並回報，不讓整體掛掉):
  - VS Code 擴充     : code --list-extensions
  - Docker images    : docker images
  - pip / npm 全域   : pip list / npm ls -g
  - Claude MCP+skills: ~/.claude.json 的 mcpServers + ~/.claude/skills、plugins

回傳:
  inventory = {
    "sources": {"vscode": [...], "docker": [...], "pip": [...], "npm": [...],
                "claude_mcp": [...], "claude_skills": [...]},
    "errors":  {"<source>": "原因"},        # 抓不到的來源
    "tokens":  set(...)                       # 全部正規化後的比對用 token
  }
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(cmd: list[str], timeout: int = 25):
    """執行指令，回 (stdout, error)。找不到指令或失敗回 (None, 原因)。"""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=timeout, encoding="utf-8", errors="replace")
        if out.returncode != 0:
            return None, (out.stderr or out.stdout or "").strip()[:200]
        return out.stdout, None
    except FileNotFoundError:
        return None, "指令不存在(未安裝或不在 PATH)"
    except subprocess.TimeoutExpired:
        return None, "逾時"
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:200]


def _run_variants(names: list[str], args: list[str]):
    """Windows 上 code/npm 可能是 .cmd；逐一嘗試。"""
    last_err = "找不到指令"
    for n in names:
        out, err = _run([n] + args)
        if out is not None:
            return out, None
        last_err = err
    return None, last_err


def get_vscode_extensions():
    out, err = _run_variants(["code", "code.cmd"], ["--list-extensions"])
    if out is None:
        return [], err
    return sorted({l.strip() for l in out.splitlines() if l.strip()}), None


def get_docker_images():
    out, err = _run(["docker", "images", "--format", "{{.Repository}}"])
    if out is None:
        return [], err
    imgs = {l.strip() for l in out.splitlines() if l.strip() and l.strip() != "<none>"}
    return sorted(imgs), None


def get_pip_packages():
    out, err = _run_variants(["pip", "pip3"], ["list", "--format=json"])
    if out is None:
        return [], err
    try:
        data = json.loads(out)
        return sorted({d["name"].lower() for d in data}), None
    except Exception:  # noqa: BLE001
        return [], "解析 pip 輸出失敗"


def get_npm_globals():
    out, err = _run_variants(["npm", "npm.cmd"], ["ls", "-g", "--depth=0", "--json"])
    if out is None:
        return [], err
    try:
        data = json.loads(out)
        deps = data.get("dependencies", {}) or {}
        return sorted(deps.keys()), None
    except Exception:  # noqa: BLE001
        return [], "解析 npm 輸出失敗"


def get_claude_assets():
    """回 (mcp_servers, skills, error)。讀 ~/.claude.json 與 ~/.claude/。"""
    home = Path.home()
    mcp, skills = [], []
    errs = []

    # MCP servers：~/.claude.json 的 mcpServers（含專案層）
    cj = home / ".claude.json"
    if cj.exists():
        try:
            data = json.loads(cj.read_text(encoding="utf-8"))
            mcp_set = set((data.get("mcpServers") or {}).keys())
            for proj in (data.get("projects") or {}).values():
                mcp_set.update((proj.get("mcpServers") or {}).keys())
            mcp = sorted(mcp_set)
        except Exception:  # noqa: BLE001
            errs.append("解析 ~/.claude.json 失敗")
    else:
        errs.append("找不到 ~/.claude.json")

    # skills：~/.claude/skills/* 與 plugins 內的 skills
    sk = set()
    sdir = home / ".claude" / "skills"
    if sdir.exists():
        sk.update(p.name for p in sdir.iterdir() if p.is_dir())
    pdir = home / ".claude" / "plugins"
    if pdir.exists():
        for sub in pdir.rglob("skills"):
            if sub.is_dir():
                sk.update(p.name for p in sub.iterdir() if p.is_dir())
    skills = sorted(sk)

    return mcp, skills, ("；".join(errs) if errs else None)


_GENERIC = {"cli", "tool", "tools", "app", "server", "mcp", "code", "python",
            "node", "js", "api", "dev", "git", "action", "actions", "core",
            "lib", "sdk", "plugin", "extension", "vscode", "docker"}
_SUFFIXES = ("-mcp", "-server", "-cli", "-tool", "-tools", "-action",
             "-actions", "-plugin", "-extension", "-app", "-sdk", "-py",
             "-js", "-ts", ".nvim", ".vim")


def _identity(name: str) -> set[str]:
    """工具的『身分 token』：完整 id + 最後一段(去常見尾綴)。嚴格，避免碎片誤中。

    例:
      ms-python.python      → {ms-python.python, python}
      qdrant/qdrant         → {qdrant/qdrant, qdrant}
      microsoft/playwright-mcp → {microsoft/playwright-mcp, playwright-mcp, playwright}
      acme/super-opcua-mcp  → {acme/super-opcua-mcp, super-opcua-mcp, super-opcua}
    """
    s = name.lower().strip()
    if not s:
        return set()
    ids = {s}
    last = s
    for sep in ("/", ":"):              # owner/repo、image:tag → 取最後一段
        if sep in last:
            last = last.rsplit(sep, 1)[-1]
    ids.add(last)
    if "." in s:                        # publisher.ext → 也加 ext 段
        ids.add(s.rsplit(".", 1)[-1])
    # 去掉常見尾綴(playwright-mcp ↔ playwright)
    for x in list(ids):
        for suf in _SUFFIXES:
            if x.endswith(suf) and len(x) > len(suf) + 2:
                ids.add(x[:-len(suf)])
    return {i for i in ids if len(i) >= 3 and i not in _GENERIC}


def get_installed_inventory():
    vscode, e_vs = get_vscode_extensions()
    docker, e_dk = get_docker_images()
    pip, e_pip = get_pip_packages()
    npm, e_npm = get_npm_globals()
    mcp, skills, e_cl = get_claude_assets()

    sources = {
        "vscode": vscode, "docker": docker, "pip": pip, "npm": npm,
        "claude_mcp": mcp, "claude_skills": skills,
    }
    errors = {}
    for k, e in [("vscode", e_vs), ("docker", e_dk), ("pip", e_pip),
                 ("npm", e_npm), ("claude", e_cl)]:
        if e:
            errors[k] = e

    identities = set()
    for items in sources.values():
        for it in items:
            identities |= _identity(it)

    return {"sources": sources, "errors": errors, "identities": identities}


def is_installed(name: str, inventory: dict) -> bool:
    """工具名是否已在本機。嚴格比對身分 token(完整 id 或去尾綴後的最後一段)。"""
    return bool(_identity(name) & inventory.get("identities", set()))


if __name__ == "__main__":
    import sys
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
    inv = get_installed_inventory()
    for src, items in inv["sources"].items():
        print(f"[{src}] {len(items)} 筆", ("　例:" + "、".join(items[:5])) if items else "")
    if inv["errors"]:
        print("\n抓不到的來源:")
        for k, v in inv["errors"].items():
            print(f"  - {k}: {v}")
    print(f"\n比對身分 token 總數: {len(inv['identities'])}")
