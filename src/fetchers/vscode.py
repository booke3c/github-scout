import os
from datetime import datetime, timezone

import requests

from ..models import RawToolData

_ENDPOINT = "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery"
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json;api-version=6.0-preview.1",
}


def fetch_vscode(query: str, max_results: int = 10) -> list[RawToolData]:
    body = {
        "filters": [{
            "criteria": [
                {"filterType": 8, "value": "Microsoft.VisualStudio.Code"},
                {"filterType": 10, "value": query},
            ],
            "pageSize": max_results,
            "sortBy": 4,
            "sortOrder": 0,
        }],
        "assetTypes": [],
        "flags": 914,
    }
    try:
        r = requests.post(_ENDPOINT, json=body, headers=_HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception:
        return []

    results = []
    for ext in (data.get("results") or [{}])[0].get("extensions", []):
        publisher = ext.get("publisher", {}).get("publisherName", "unknown")
        name = ext.get("extensionName", "")
        stats = {s["statisticName"]: s["value"] for s in ext.get("statistics", [])}
        install_count = int(stats.get("install", 0))
        is_featured = "validated" in (ext.get("flags") or "")

        last_updated = ext.get("lastUpdated", "")
        days = 9999
        if last_updated:
            dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - dt).days

        results.append(RawToolData(
            name=f"{publisher}.{name}",
            source="vscode",
            url=f"https://marketplace.visualstudio.com/items?itemName={publisher}.{name}",
            description=(ext.get("shortDescription") or "")[:120],
            stars=install_count // 10000,
            last_commit_days=days,
            has_license=True,
            maintainer_verified_org=is_featured,
            has_readme=True,
            claude_code_integration_level=12,
        ))

    return results
