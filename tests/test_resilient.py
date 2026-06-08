"""resilient_create 測試:重試/退避/fallback/不重試 都覆蓋。用假 client,不打真 API。"""
import pytest
from src.resilient import resilient_create, is_retryable


class _Err(Exception):
    def __init__(self, status_code=None, msg=""):
        super().__init__(msg or f"status {status_code}")
        self.status_code = status_code


class _FakeMessages:
    def __init__(self, script):
        # script: list,元素是 Exception(則拋出)或值(則回傳)
        self.script = list(script)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _FakeClient:
    def __init__(self, script):
        self.messages = _FakeMessages(script)


def _noslip(_):  # 假 sleep,不真的等
    pass


def test_success_first_try():
    c = _FakeClient(["OK"])
    assert resilient_create(c, model="m", sleep=_noslip) == "OK"
    assert len(c.messages.calls) == 1


def test_retry_then_success():
    c = _FakeClient([_Err(529), _Err(429), "OK"])
    slept = []
    assert resilient_create(c, model="m", sleep=slept.append) == "OK"
    assert len(c.messages.calls) == 3
    assert len(slept) == 2  # 兩次重試各退避一次


def test_non_retryable_raises_immediately():
    c = _FakeClient([_Err(400)])
    with pytest.raises(_Err):
        resilient_create(c, model="m", sleep=_noslip)
    assert len(c.messages.calls) == 1  # 不重試


def test_fallback_model_after_exhaustion():
    # 主模型一直 overloaded(529),用盡後換 fallback 成功
    c = _FakeClient([_Err(529), _Err(529), _Err(529), "FB-OK"])
    out = resilient_create(c, model="opus", fallback_model="sonnet",
                           max_retries=2, sleep=_noslip)
    assert out == "FB-OK"
    assert c.messages.calls[-1]["model"] == "sonnet"  # 最後一次用備援模型


def test_overload_by_message_text():
    c = _FakeClient([_Err(None, "Overloaded: please retry"), "OK"])
    assert resilient_create(c, model="m", sleep=_noslip) == "OK"


def test_is_retryable_predicate():
    assert is_retryable(_Err(429))
    assert is_retryable(_Err(529))
    assert not is_retryable(_Err(400))
    assert not is_retryable(_Err(404))
