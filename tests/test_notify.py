import io
from urllib.error import HTTPError
from urllib.parse import parse_qs

import pytest

from decimal_guardian.notify import NotificationError, send_validator_offline


def test_send_validator_offline_uses_post(monkeypatch):
    requests = []
    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return io.BytesIO(b'{"ok":true,"result":{}}')
    monkeypatch.setattr("decimal_guardian.notify.urlopen", fake_urlopen)
    report = {"missed": 8, "window": 24, "consecutive_missed": 6}
    send_validator_offline("123:secret", 456, "node1", report, "0xabc")
    request, timeout = requests[0]
    assert request.get_method() == "POST"
    assert request.full_url.endswith("/sendMessage")
    assert timeout == 10
    assert parse_qs(request.data.decode()) == {
        "chat_id": ["456"],
        "text": ["Валидатор node1 отключен после пропуска подписей.\nПропущено: 8 из 24, подряд: 6.\nТранзакция: 0xabc"],
    }


def test_http_failure_does_not_expose_bot_token(monkeypatch):
    def fail(request, timeout):
        raise HTTPError(request.full_url, 403, "Forbidden", {}, None)
    monkeypatch.setattr("decimal_guardian.notify.urlopen", fail)
    with pytest.raises(NotificationError) as error:
        send_validator_offline("123:secret", 456, "node1", {"missed": 8, "window": 24, "consecutive_missed": 6}, None)
    assert "HTTP 403" in str(error.value)
    assert "secret" not in str(error.value)
