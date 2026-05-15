from datetime import datetime, timezone

import requests

from ..models import RawToolData

_BASE = "https://hub.docker.com/v2/search/repositories"


def fetch_docker(query: str, max_results: int = 10) -> list[RawToolData]:
    try:
        r = requests.get(_BASE, params={"query": query, "page_size": max_results}, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception:
        return []

    results = []
    for item in data.get("results", []):
        last_updated = item.get("last_updated", "")
        days = 9999
        if last_updated:
            dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - dt).days

        is_official = item.get("is_official", False)

        results.append(RawToolData(
            name=item.get("repo_name", ""),
            source="docker",
            url=f"https://hub.docker.com/r/{item.get('repo_name', '')}",
            description=(item.get("short_description") or "")[:120],
            stars=item.get("star_count", 0),
            last_commit_days=days,
            maintainer_verified_org=is_official,
            has_license=True,
            has_readme=True,
            claude_code_integration_level=12,
        ))

    return results
