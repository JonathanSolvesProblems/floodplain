import pytest

from floodplain.backends import _is_retryable, with_retry


class ApiStatusCodeError(Exception):
    def __init__(self, status):
        super().__init__(f"status={status}")
        self.status = status


class ContreeTransportError(Exception):
    pass


def test_5xx_and_429_are_retryable():
    for status in (500, 502, 503, 504, 429):
        assert _is_retryable(ApiStatusCodeError(status))


def test_4xx_is_not_retryable():
    for status in (400, 401, 403, 404, 422):
        assert not _is_retryable(ApiStatusCodeError(status))


def test_transport_errors_are_retryable_by_name():
    assert _is_retryable(ContreeTransportError("boom"))
    assert not _is_retryable(ValueError("nope"))


async def test_with_retry_succeeds_after_transient_500s():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ApiStatusCodeError(500)
        return "ok"

    assert await with_retry("t", flaky, attempts=4) == "ok"
    assert calls["n"] == 3


async def test_with_retry_gives_up_and_reraises():
    async def always_500():
        raise ApiStatusCodeError(503)

    with pytest.raises(ApiStatusCodeError):
        await with_retry("t", always_500, attempts=2)


async def test_with_retry_does_not_retry_a_real_error():
    calls = {"n": 0}

    async def bad_request():
        calls["n"] += 1
        raise ApiStatusCodeError(422)

    with pytest.raises(ApiStatusCodeError):
        await with_retry("t", bad_request, attempts=5)
    assert calls["n"] == 1
