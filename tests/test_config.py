import json
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
