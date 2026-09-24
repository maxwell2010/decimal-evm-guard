from dataclasses import replace

import pytest

from decimal_guardian.guard import GuardError, Vote, _vote, evaluate
from decimal_guardian.rpc import NodeStatus


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
