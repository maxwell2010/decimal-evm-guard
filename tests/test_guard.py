from dataclasses import replace

import pytest

from decimal_guardian.guard import GuardError, Vote, _vote, evaluate, run_forever
from decimal_guardian.rpc import NodeStatus
from decimal_guardian.validator import ActionResult


def test_vote_reads_previous_height_and_validator_order(monkeypatch):
    address = "A" * 40
    urls = []

    def fetch(url):
        urls.append(url)
        if "/block?" in url:
            return {"result": {"block": {"last_commit": {"height": "12", "block_id": {"hash": "B" * 64},
                    "signatures": [{"block_id_flag": 1}, {"block_id_flag": 2, "validator_address": address, "signature": "signed"}]}}}}
        return {"result": {"total": "2", "validators": [{"address": "C" * 40}, {"address": address}]}}

    monkeypatch.setattr("decimal_guardian.guard.rpc.fetch_json", fetch)
    _vote.cache_clear()
    assert _vote("https://a.example", 12, address).signed is True
    assert any("/block?height=13" in url for url in urls)
    assert any("/validators?height=12" in url for url in urls)


def test_evaluate_rejects_disagreeing_references(monkeypatch, cfg):
    config = replace(cfg, references=("https://a.example", "https://b.example"),
                     consensus_address="A" * 40, window_blocks=3, max_missed=2)
    monkeypatch.setattr("decimal_guardian.guard.rpc.status", lambda root: NodeStatus(20, False, "decimal", root))
    monkeypatch.setattr("decimal_guardian.guard._vote", lambda root, height, address: Vote(height, ("A" if root.endswith("a.example") else "B") * 64, False))
    with pytest.raises(GuardError, match="disagree"):
        evaluate(config)


def test_evaluate_threshold_and_signed_window(monkeypatch, cfg):
    config = replace(cfg, references=("https://a.example", "https://b.example"),
                     consensus_address="A" * 40, window_blocks=4, max_missed=2)
    monkeypatch.setattr("decimal_guardian.guard.rpc.status", lambda root: NodeStatus(20, False, "decimal", root))
    monkeypatch.setattr("decimal_guardian.guard._vote", lambda root, height, address: Vote(height, "A" * 64, height < 17))
    result = evaluate(config)
    assert result == {"latest": 19, "window": 4, "missed": 3, "consecutive_missed": 3, "should_pause": True}


def test_telegram_alert_only_after_confirmed_pause(monkeypatch, cfg):
    settings = replace(cfg, enabled=True, telegram_bot_token="123:secret", telegram_user_id=456)
    report = {"latest": 20, "window": 24, "missed": 8, "consecutive_missed": 6, "should_pause": True}
    monkeypatch.setattr("decimal_guardian.guard.evaluate", lambda _: report)
    messages = []
    monkeypatch.setattr("decimal_guardian.guard.send_validator_offline", lambda *args: messages.append(args))
    class StopLoop(Exception):
        pass
    monkeypatch.setattr("decimal_guardian.guard.time.sleep", lambda _: (_ for _ in ()).throw(StopLoop()))
    class Provider:
        def paused(self):
            return False
        def set_paused(self, paused):
            assert paused is True
            return ActionResult("confirmed", "0xabc")
    with pytest.raises(StopLoop):
        run_forever(settings, Provider())
    assert messages == [("123:secret", 456, "test-validator", report, "0xabc")]


def test_no_telegram_alert_when_pause_was_already_done(monkeypatch, cfg):
    settings = replace(cfg, enabled=True, telegram_bot_token="123:secret", telegram_user_id=456)
    monkeypatch.setattr("decimal_guardian.guard.evaluate", lambda _: {
        "latest": 20, "window": 24, "missed": 8, "consecutive_missed": 6, "should_pause": True
    })
    monkeypatch.setattr("decimal_guardian.guard.send_validator_offline", lambda *args: pytest.fail("unexpected alert"))
    class StopLoop(Exception):
        pass
    monkeypatch.setattr("decimal_guardian.guard.time.sleep", lambda _: (_ for _ in ()).throw(StopLoop()))
    class Provider:
        def paused(self):
            return False
        def set_paused(self, paused):
            return ActionResult("already_offline", None)
    with pytest.raises(StopLoop):
        run_forever(settings, Provider())
