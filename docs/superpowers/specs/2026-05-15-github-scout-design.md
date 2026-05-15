# GitHub Scout Agent — 設計文件 v0.2

**日期**：2026-05-15  
**專案路徑**：`C:\Users\USER1502\github-scout\`

---

## 1. 目標

取代「等別人推薦」的被動模式，主動搜尋並評估 GitHub 生態系工具的品質、安全性與 Claude Code 整合性。支援：
- 手動查詢（隨時從 Claude Code 觸發）
- 每週自動掃描（結果寫入 Notion）

---

## 2. 架構

```
手動查詢
  └─ /github-scout <關鍵字> [--save]  (Claude Code skill)
       └─ 呼叫 github_scout.py --query <關鍵字> [--save]
            └─ 查詢多個 API → 計算綜合評分 → 印出結果到對話

週期掃描
  └─ Windows Task Scheduler（每週一 08:00）
       └─ 呼叫 github_scout.py --scan
            └─ 用預設關鍵字清單掃描 → 計算評分 → 寫入 Notion
```

**主要元件：**
- `github_scout.py` — 核心邏輯，單一入口（`--query` 或 `--scan` 模式）
- `config.json` — 關鍵字清單、評分門檻、Notion page ID（**不存 token**）
- `.env` — API tokens（`GITHUB_TOKEN`、`NOTION_TOKEN`，不進版控）
- `.claude/skills/github-scout.md` — Claude Code skill 定義
- `task_scheduler.xml` — Windows Task Scheduler 匯入設定
- `logs/error.log` — 執行錯誤記錄

---

## 3. 資料來源

### 主要 Discovery 來源

| 來源 | 查詢對象 | API |
|------|---------|-----|
| GitHub Search API | Actions、CLI tools、任意 repo | `api.github.com/search/repositories` |
| GitHub Topics | 主題分類搜尋（mcp, claude-code, opc-ua 等） | `api.github.com/search/topics` |
| VS Code Marketplace | 擴充套件 | `marketplace.visualstudio.com/_apis/public/gallery/extensionquery` |
| Docker Hub | 官方 images | `hub.docker.com/v2/search/repositories` |

### 候選工具補查（有候選名稱時才呼叫）

| 來源 | 用途 | API |
|------|------|-----|
| GitHub Repo Contents API | 讀取 README、SECURITY.md、action.yml、pyproject.toml | `api.github.com/repos/{owner}/{repo}/contents/{path}` |
| GitHub Issues API | 查 open/closed issue 回覆速度 | `api.github.com/repos/{owner}/{repo}/issues` |
| GitHub Pulls API | 查 PR merge / close 頻率 | `api.github.com/repos/{owner}/{repo}/pulls` |
| GitHub Advisory Database | 查套件已知 CVE | `api.github.com/advisories` |
| PyPI JSON API | 查 Python 套件 metadata | `pypi.org/pypi/{name}/json` |

**注意：**
- GitHub API 需要 `GITHUB_TOKEN`（Personal Access Token，read-only scope 即可）
- VS Code Marketplace API 無官方文件，錯誤處理要做完整，不允許此來源失敗導致整體掃描中斷
- PyPI 適合「補查」特定套件，不適合廣泛 discovery

---

## 4. 評分演算法 v0.2（滿分 100）

| 面向 | 滿分 | 計算細節 |
|------|------|---------|
| 安全性 | 35 | 見下方細項 |
| Claude Code 整合性 | 20 | 見下方細項 |
| Stars / 成長性 | 15 | log scale：≥10k=15, ≥5k=12, ≥1k=8, ≥100=4, <100=1 |
| 維護者可信度 | 15 | 見下方細項 |
| Issue / PR 回覆速度 | 15 | 見下方細項 |

### 安全性（35 分）

```
基礎存在（有 SECURITY.md）       +5
有 LICENSE                       +3
有 signed release / checksum     +3
有 lockfile（package-lock.json 等）+2
無已知 CVE（Advisory DB 無命中）  +7
無依賴漏洞                       +5

減分項（每項 -5，最低 0）：
- README 要求 curl | bash 安裝
- GitHub Action 未 pin 到 SHA
- workflow 要求 write-all permissions
- 存取 secrets / token / SSH key
- 大量 unresolved security issue（>5 個）
- 安裝後要求過度系統權限
```

任何減分導致安全性 < 25 → 一律不推薦，不管總分。

### Claude Code 整合性（20 分）

```
20：原生 Claude Code 支援 / MCP server
16：CLI 適合 Claude Code 直接呼叫
12：GitHub Action 可間接整合
8：可透過 shell script 包裝使用
4：只能人工操作
0：不適合或高風險
```

整合性 < 8 → 只能進觀察名單，不列入正式推薦。

### 維護者可信度（15 分）

```
維護者有 GitHub Verified Organization   +4
有清晰的 README                        +3
有明確 CONTRIBUTORS 或多貢獻者          +3
有穩定 release 歷史（>3 個版本）        +3
有完整 license（MIT / Apache / BSD）    +2
```

### Issue / PR 回覆速度（15 分）

```
最近 20 個 closed issues 平均關閉天數：
  ≤7 天 = 15, ≤30 天 = 10, ≤90 天 = 5, >90 天 = 0

額外扣分：
- open issues / total issues 比例 > 50%   -3
- 有 security label issue 未處理 > 30 天  -5
- 最近 20 PR 的 merge rate < 30%          -3
```

### 硬性門檻

```
總分 < 70            → 不推薦（不顯示在 Top 推薦）
安全性 < 25 / 35     → 一律不推薦，無論總分
Claude Code 整合 < 8  → 只能進觀察名單
最近 12 個月無 commit → 不推薦（除非是極成熟穩定工具，需標記說明）
資料不足時            → 標記「資料不足，請人工確認」，不假設安全
```

---

## 5. 輸出格式

### 手動查詢（對話視窗）

呼叫方式：
- `/github-scout <關鍵字>` — 只顯示在對話
- `/github-scout <關鍵字> --save` — 顯示在對話，同時寫入 Notion

```
GitHub Scout 結果：opc-ua python（共 15 筆符合，評分 ≥70 顯示前 5）

== Top 推薦 ==

#1  FreeOpcUa/python-opcua        [GitHub Repo]   評分 84
    OPC UA 客戶端/伺服器 Python 實作，Stars 2.1k，最近 commit 12 天前
    安全性 28  整合性 16（CLI）  可信度 12  回覆速度 12  Stars 10
    CVE 0  依賴漏洞 0  SECURITY.md ✓  LICENSE MIT
    https://github.com/FreeOpcUa/python-opcua

#2  ...

== 觀察名單（整合性不足但有潛力）==

- example/tool  評分 65，Claude Code 整合性 6，缺 SECURITY.md

== 不建議安裝 ==

- dangerous/action  安全性 18（Action 未 pin SHA，要求 write-all）
```

### 週期掃描（Notion）

**頁面**：CC GITHUB search agent（ID: `361967ffe82f808dad92c6669ce93a45`）

**每週追加一個 toggle，不覆蓋舊記錄：**

```
Toggle：2026-05-18 掃描結果
  ├─ Toggle：Top 推薦（N 筆）
  │    └─ [名稱]  評分 XX  ── 一行摘要 + 分數拆解 + 連結
  ├─ Toggle：觀察名單（N 筆）
  │    └─ [名稱]  評分 XX  ── 說明為何未達正式推薦
  ├─ Toggle：不建議安裝（N 筆）
  │    └─ [名稱]  ── 具體原因（例：Action 未 pin SHA）
  └─ Toggle：Claude Code 整合建議
       └─ 本週最適合接入 Claude Code 的工具與做法
```

Notion 寫入方式：每個 toggle 為一個 `toggle` block，子項目為 `bulleted_list_item`。
單次 append 最多 100 個 child block，nesting 最多兩層（不再往下疊）。

---

## 6. Config 設定

### `config.json`（不存 token）

```json
{
  "scan_keywords": [
    "opc-ua", "cnc automation", "python automation",
    "mcp server", "claude-code", "ci/cd",
    "docker dev tools", "code quality",
    "security scan", "vs code productivity",
    "python testing", "api monitoring",
    "github actions", "cli tool"
  ],
  "min_score": 70,
  "max_results_per_query": 10,
  "notion_page_id": "361967ffe82f808dad92c6669ce93a45"
}
```

### `.env`（不進版控，加入 `.gitignore`）

```env
GITHUB_TOKEN=ghp_xxxx
NOTION_TOKEN=ntn_xxxx
```

---

## 7. 排程設定

- **工具**：Windows Task Scheduler
- **頻率**：每週一 08:00
- **執行指令**：`python C:\Users\USER1502\github-scout\github_scout.py --scan`
- **失敗處理**：寫入 `logs/error.log`，不重試，不發通知（後續可加）

---

## 8. 依賴套件

```
requests         # HTTP 呼叫
notion-client    # Notion Blocks API
python-dateutil  # 日期計算
python-dotenv    # 讀取 .env
```

---

## 9. 建議上線順序

1. 先做手動查詢 `/github-scout <關鍵字>`
2. 驗證評分邏輯與輸出品質（手動跑 2 週）
3. 確認結果品質後，再開啟 Windows Task Scheduler 自動掃描
4. 自動掃描穩定後，再開 `--save` 寫入 Notion

---

## 10. 不在範圍內

- 不做 GUI 介面
- 不做即時通知（LINE / email push）
- 不快取歷史評分（每次重新查詢，確保資料新鮮）
- npm 套件（後續可加）
