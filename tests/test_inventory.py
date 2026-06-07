"""inventory 比對邏輯測試：確保已裝偵測準、不誤判。"""
from src.inventory import is_installed, _identity


def _inv(ids):
    return {"identities": set(ids), "sources": {}, "errors": {}}


def test_exact_id_match():
    inv = _inv({"ms-python.python", "qdrant"})
    assert is_installed("ms-python.python", inv)


def test_owner_repo_last_segment_match():
    inv = _inv({"qdrant"})
    assert is_installed("qdrant/qdrant", inv)


def test_suffix_strip_match():
    # 已裝 claude MCP 'playwright'，掃到 'microsoft/playwright-mcp' 應算已裝
    inv = _inv({"playwright"})
    assert is_installed("microsoft/playwright-mcp", inv)


def test_no_false_positive_on_owner_prefix():
    # 回歸：'acme' 是 pip 套件，不可讓 'acme/super-opcua-mcp' 被誤判已裝
    inv = _inv({"acme", "super"})
    assert not is_installed("acme/super-opcua-mcp", inv)


def test_generic_tokens_do_not_match():
    inv = _inv({"playwright"})
    assert not is_installed("someone/random-mcp", inv)   # 只共用 generic 'mcp'


def test_identity_drops_generic_and_short():
    ids = _identity("foo/bar-cli")
    assert "cli" not in ids          # generic 去掉
    assert "bar" in ids              # 去尾綴後保留
