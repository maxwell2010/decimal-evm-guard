import json
from pathlib import Path
from dataclasses import asdict

import pytest

from decimal_guardian.config import ConfigError, load_config


def test_config_requires_distinct_rpc_sources(cfg, tmp_path):
    data = asdict(cfg)
    data["key_file"] = str(cfg.key_file)
    data["state_dir"] = str(cfg.state_dir)
    data["references"] = ["https://same.example", "https://same.example"]
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ConfigError, match="two different"):
        load_config(path)


def test_config_round_trip(cfg, tmp_path):
    data = asdict(cfg)
    data["key_file"] = str(cfg.key_file)
    data["state_dir"] = str(cfg.state_dir)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert load_config(path) == cfg


def test_example_shows_signature_settings_and_uses_mainnet_defaults(tmp_path):
    data = json.loads(Path("config.example.json").read_text(encoding="utf-8"))
    assert {name: data[name] for name in (
        "window_blocks", "max_missed", "max_consecutive_missed", "poll_seconds",
        "block_timeout_seconds", "max_lag", "cooldown_seconds"
    )} == {
        "window_blocks": 24, "max_missed": 8, "max_consecutive_missed": 6,
        "poll_seconds": 5, "block_timeout_seconds": 30, "max_lag": 3, "cooldown_seconds": 900,
    }
    data["key_file"] = str(tmp_path / "validator.key")
    data["state_dir"] = str(tmp_path / "state")
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    cfg = load_config(path)
    assert cfg.chain_id == 75
    assert cfg.contract_center == "0xc108715a06f76caa96fa2c943ebf05159c29a87d"
    assert cfg.evm_rpc == "http://127.0.0.1:8545"
    assert cfg.window_blocks == 24
    assert cfg.telegram_bot_token is None


def test_other_network_requires_explicit_contract_center(tmp_path):
    data = json.loads(Path("config.example.json").read_text(encoding="utf-8"))
    data.update({"chain_id": 76, "key_file": str(tmp_path / "validator.key"), "state_dir": str(tmp_path / "state")})
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ConfigError, match="contract center"):
        load_config(path)
    data["contract_center"] = "0x" + "1" * 40
    path.write_text(json.dumps(data), encoding="utf-8")
    assert load_config(path).chain_id == 76


@pytest.mark.parametrize("telegram", [
    {"bot_token": "123:secret", "user_id": None},
    {"bot_token": None, "user_id": 456},
    {"bot_token": "bad-secret", "user_id": 456},
    {"bot_token": "123:secret", "user_id": True},
])
def test_invalid_telegram_config_does_not_echo_secret(cfg, tmp_path, telegram):
    data = asdict(cfg)
    data["key_file"] = str(cfg.key_file)
    data["state_dir"] = str(cfg.state_dir)
    data["telegram"] = telegram
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ConfigError) as error:
        load_config(path)
    assert "secret" not in str(error.value)


def test_telegram_config_hides_token(cfg, tmp_path):
    data = asdict(cfg)
    data["key_file"] = str(cfg.key_file)
    data["state_dir"] = str(cfg.state_dir)
    data["telegram"] = {"bot_token": "123:secret", "user_id": 456}
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    loaded = load_config(path)
    assert loaded.telegram_user_id == 456
    assert "123:secret" not in repr(loaded)
