import io
from dataclasses import replace
from urllib.error import HTTPError
from urllib.parse import parse_qs

import pytest

from decimal_guardian.notify import NotificationError, send_validator_offline


def test_send_validator_offline_uses_post(monkeypatch, cfg):
    requests = []
    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return io.BytesIO(b'{"ok":true,"result":{}}')
    monkeypatch.setattr("decimal_guardian.notify.urlopen", fake_urlopen)
    cfg = replace(cfg, node_name="node1", telegram_bot_token="123:secret", telegram_user_id=456)
    report = {"missed": 8, "window": 24, "consecutive_missed": 6}
    send_validator_offline(cfg, report, "0xabc")
    request, timeout = requests[0]
    assert request.get_method() == "POST"
    assert request.full_url.endswith("/sendMessage")
    assert timeout == 10
    assert parse_qs(request.data.decode()) == {
        "chat_id": ["456"],
        "text": ["Узел: node1\nВалидатор отключен после пропуска подписей.\nПричина: max_missed: 8 >= 8 в окне из 24 блоков; max_consecutive_missed: 6 >= 6 подряд\nТранзакция: 0xabc"],
    }


@pytest.mark.parametrize("missed,consecutive,expected,absent", [
    (8, 2, "max_missed: 8 >= 8 в окне из 24 блоков", "max_consecutive_missed"),
    (2, 6, "max_consecutive_missed: 6 >= 6 подряд", "max_missed"),
])
def test_alert_names_only_the_triggered_threshold(monkeypatch, cfg, missed, consecutive, expected, absent):
    messages = []
    def fake_urlopen(request, timeout):
        messages.append(parse_qs(request.data.decode())["text"][0])
        return io.BytesIO(b'{"ok":true}')
    monkeypatch.setattr("decimal_guardian.notify.urlopen", fake_urlopen)
    cfg = replace(cfg, telegram_bot_token="123:secret", telegram_user_id=456)
    send_validator_offline(cfg, {"missed": missed, "window": 24, "consecutive_missed": consecutive}, "0xabc")
    assert f"Узел: {cfg.node_name}" in messages[0]
    assert expected in messages[0]
    assert absent not in messages[0]


def test_http_failure_does_not_expose_bot_token(monkeypatch, cfg):
    def fail(request, timeout):
        raise HTTPError(request.full_url, 403, "Forbidden", {}, None)
    monkeypatch.setattr("decimal_guardian.notify.urlopen", fail)
    cfg = replace(cfg, telegram_bot_token="123:secret", telegram_user_id=456)
    with pytest.raises(NotificationError) as error:
        send_validator_offline(cfg, {"missed": 8, "window": 24, "consecutive_missed": 6}, None)
    assert "HTTP 403" in str(error.value)
    assert "secret" not in str(error.value)
