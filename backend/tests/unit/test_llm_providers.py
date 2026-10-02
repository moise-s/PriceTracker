"""Provider error mapping: typed, actionable, and never echoing the key or the provider body."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from pricetracker.llm.providers import (
    LlmAuthError,
    LlmBadResponse,
    LlmError,
    LlmModelNotFound,
    LlmRateLimited,
    LlmTimeout,
    OpenAICompatibleClient,
    ProviderConfig,
)
from pricetracker.models.enums import LlmKind
from pricetracker.services.llm_admin import _friendly

KEY = "gsk_test_key_not_real_123456"
MESSAGES = [{"role": "user", "content": "ping"}]
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> OpenAICompatibleClient:
    config = ProviderConfig(
        name="Groq",
        kind=LlmKind.GROQ,
        base_url="https://api.groq.test/openai/v1",
        model="qwen/qwen3.8-27b",
        api_key=KEY,
        structured_output="json_schema",
        key_source="env:GROQ_API_KEY",
    )
    return OpenAICompatibleClient(config, transport=httpx.MockTransport(handler))


def _fails_with(response: httpx.Response) -> LlmError:
    with pytest.raises(LlmError) as info:
        _client(lambda request: response).complete_json(MESSAGES, SCHEMA, "health_check")
    assert KEY not in str(info.value)
    return info.value


def test_daily_quota_is_reported_with_when_to_retry_but_without_the_body() -> None:
    body = {
        "error": {
            "message": "Rate limit reached for model `qwen/qwen3.8-27b` in organization "
            "`org_secretish` on tokens per day (TPD): Limit 500000, Used 499990",
            "code": "rate_limit_exceeded",
        }
    }
    error = _fails_with(httpx.Response(429, json=body, headers={"retry-after": "754"}))
    assert isinstance(error, LlmRateLimited)
    assert error.daily and error.retry_after == 754
    assert "org_secretish" not in str(error)
    message = _friendly(error)
    assert message.startswith("Cota diária do provedor esgotada")
    assert "cerca de 13 min" in message and "org_" not in message


def test_short_rate_limit_without_hint_still_explains_the_degradation() -> None:
    error = _fails_with(httpx.Response(429, json={"error": {"message": "slow down"}}))
    assert isinstance(error, LlmRateLimited) and not error.daily and error.retry_after is None
    assert _friendly(error) == (
        "Limite de uso do provedor atingido. Tente mais tarde; a coleta segue sem IA até lá."
    )


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(401, json={"error": "invalid api key"}), LlmAuthError),
        (httpx.Response(404, json={"error": "not found"}), LlmModelNotFound),
        (
            httpx.Response(400, json={"error": {"code": "model_decommissioned"}}),
            LlmModelNotFound,
        ),
        (httpx.Response(503, text="upstream overloaded"), LlmBadResponse),
    ],
)
def test_http_failures_map_to_typed_errors(
    response: httpx.Response, expected: type[LlmError]
) -> None:
    assert isinstance(_fails_with(response), expected)


def test_timeouts_are_typed() -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LlmTimeout):
        _client(slow).complete_json(MESSAGES, SCHEMA, "health_check")


def test_the_key_only_travels_in_the_authorization_header() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"ok": true}'}}], "usage": {}}
        )

    result = _client(handler).complete_json(MESSAGES, SCHEMA, "health_check")
    assert result.content == {"ok": True}
    request = seen[0]
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert KEY not in str(request.url) and KEY.encode() not in request.content
