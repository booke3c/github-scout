"""Anthropic 呼叫韌性包裝(選用、可攜)。

把 client.messages.create 包一層:遇到暫時性錯誤(429 限流、529 overloaded、
5xx、連線/逾時)自動指數退避重試;重試用盡且有給 fallback_model 時,改用備援
模型再試一次。**不改變任何成功路徑的輸出**——成功時就是原樣回傳 messages.create
的結果,所以套到現有 agent 不影響其行為,只是讓暫時性故障不再靜默失敗。

用法(把原本的 client.messages.create(**kw) 換成):
    from src.resilient import resilient_create
    resp = resilient_create(client, fallback_model="claude-sonnet-5", **kw)

刻意用 duck-typing 判斷可重試(看 status_code / 例外類名 / 'overload' 字樣),
不綁 anthropic 的例外類別,方便單元測試與跨專案重用。
"""
from __future__ import annotations

import time

_RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}
_RETRY_NAMES = {
    "RateLimitError", "APIConnectionError", "APITimeoutError",
    "InternalServerError", "OverloadedError", "ServiceUnavailableError",
}


def is_retryable(exc: Exception) -> bool:
    """暫時性錯誤才重試;像 400/401/404/422 這種請求本身錯的,直接拋、不重試。"""
    sc = getattr(exc, "status_code", None)
    if sc in _RETRY_STATUS:
        return True
    if type(exc).__name__ in _RETRY_NAMES:
        return True
    return "overload" in str(exc).lower()


def resilient_create(client, *, fallback_model: str | None = None,
                     max_retries: int = 4, base: float = 1.0, cap: float = 20.0,
                     sleep=time.sleep, **kwargs):
    """重試 + 指數退避 + 選用模型 fallback 的 messages.create 包裝。

    參數:
        client          anthropic.Anthropic 實例(或任何有 .messages.create 的物件)
        fallback_model  重試用盡仍失敗時,改用此模型再試一次(None=不 fallback)
        max_retries     可重試錯誤的最大重試次數(不含首次)
        base/cap        指數退避起始秒數與上限
        sleep           注入用(測試傳假 sleep)
        **kwargs        原封不動轉給 client.messages.create
    成功:回傳 messages.create 的結果(與原行為相同)。
    失敗:重試用盡(必要時 fallback)後,拋出最後一個例外。
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return client.messages.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            if not is_retryable(exc):
                raise
            last_exc = exc
            if attempt < max_retries:
                sleep(min(base * (2 ** attempt), cap))

    # 主模型重試用盡:有備援模型且與目前不同 → 換模型再試一次
    if fallback_model and kwargs.get("model") != fallback_model:
        kwargs["model"] = fallback_model
        try:
            return client.messages.create(**kwargs)
        except Exception:  # noqa: BLE001
            raise last_exc if last_exc else RuntimeError("resilient_create failed")
    if last_exc:
        raise last_exc
    raise RuntimeError("resilient_create: unreachable")
