import pytest
from unittest.mock import patch, MagicMock
from src.fetchers.github import (
    _detect_curl_bash, _detect_write_all,
    _detect_accesses_secrets, _detect_unpinned_action,
    _days_since, _get_integration_level,
)

def test_detect_curl_bash_positive():
    assert _detect_curl_bash("curl -fsSL https://example.com | bash") is True
    assert _detect_curl_bash("curl https://x.com/install.sh | sh") is True

def test_detect_curl_bash_negative():
    assert _detect_curl_bash("pip install requests") is False

def test_detect_write_all():
    assert _detect_write_all("permissions: write-all") is True
    assert _detect_write_all("permissions: read-all") is False

def test_detect_accesses_secrets():
    assert _detect_accesses_secrets("${{ secrets.GITHUB_TOKEN }}") is True
    assert _detect_accesses_secrets("no secrets here") is False

def test_detect_unpinned_action():
    pinned = "uses: actions/checkout@a81bbbf8298c0fa03ea29cdc473d45769f953675"
    unpinned = "uses: actions/checkout@v3"
    assert _detect_unpinned_action(unpinned) is True
    assert _detect_unpinned_action(pinned) is False

def test_days_since_recent():
    from datetime import datetime, timezone, timedelta
    recent = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    assert _days_since(recent) == 5

def test_days_since_empty():
    assert _days_since("") == 9999

def test_integration_level_mcp():
    assert _get_integration_level({"description": "an MCP server"}, ["mcp"]) == 20

def test_integration_level_cli():
    assert _get_integration_level({"description": "a CLI tool"}, ["cli"]) == 16

def test_integration_level_default():
    assert _get_integration_level({"description": "a library"}, []) == 8
