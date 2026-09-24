from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    node_name: str
    enabled: bool
    evm_rpc: str
    contract_center: str
    chain_id: int
    key_file: Path
    state_dir: Path
    consensus_address: str
    references: tuple[str, str]
    window_blocks: int = 24
    max_missed: int = 8
    max_consecutive_missed: int = 6
    poll_seconds: int = 5
    block_timeout_seconds: int = 30
    max_lag: int = 3
    cooldown_seconds: int = 900

    @property
    def guard_references(self) -> tuple[str, str]:
        return self.references

    @property
    def guard_window(self) -> int:
        return self.window_blocks

    @property
    def guard_max_missed(self) -> int:
        return self.max_missed

    @property
    def guard_max_consecutive_missed(self) -> int:
        return self.max_consecutive_missed

    @property
    def guard_max_lag(self) -> int:
        return self.max_lag

    @property
    def guard_enabled(self) -> bool:
        return self.enabled

    @property
    def guard_poll_seconds(self) -> int:
        return self.poll_seconds

    @property
    def guard_block_timeout_seconds(self) -> int:
        return self.block_timeout_seconds

    @property
    def guard_cooldown_seconds(self) -> int:
        return self.cooldown_seconds


def _url(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{name} must be a URL")
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ConfigError(f"{name} must be an HTTP(S) RPC root without credentials")
    return value.rstrip("/")


def load_config(path: Path) -> Config:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read configuration: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("configuration must be a JSON object")
    try:
        references = tuple(_url(url, "reference") for url in raw["references"])
        cfg = Config(
            node_name=str(raw["node_name"]),
            enabled=raw.get("enabled", False),
            evm_rpc=_url(raw["evm_rpc"], "EVM RPC"),
            contract_center=str(raw["contract_center"]),
            chain_id=int(raw["chain_id"]),
            key_file=Path(raw["key_file"]),
            state_dir=Path(raw.get("state_dir", "/var/lib/decimal-guardian")),
            consensus_address=str(raw["consensus_address"]),
            references=references,
            window_blocks=int(raw.get("window_blocks", 24)),
            max_missed=int(raw.get("max_missed", 8)),
            max_consecutive_missed=int(raw.get("max_consecutive_missed", 6)),
            poll_seconds=int(raw.get("poll_seconds", 5)),
            block_timeout_seconds=int(raw.get("block_timeout_seconds", 30)),
            max_lag=int(raw.get("max_lag", 3)),
            cooldown_seconds=int(raw.get("cooldown_seconds", 900)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"invalid configuration field: {exc}") from exc
    if not cfg.node_name or not isinstance(cfg.enabled, bool):
        raise ConfigError("node_name and enabled are required")
    if (len(cfg.contract_center) != 42 or not cfg.contract_center.startswith("0x")
            or any(c not in "0123456789abcdefABCDEF" for c in cfg.contract_center[2:])
            or cfg.chain_id <= 0):
        raise ConfigError("invalid contract center or chain ID")
    if not cfg.key_file.is_absolute() or not cfg.state_dir.is_absolute():
        raise ConfigError("key_file and state_dir must be absolute")
    if (len(cfg.consensus_address) != 40
            or any(c not in "0123456789abcdefABCDEF" for c in cfg.consensus_address)):
        raise ConfigError("consensus_address must contain 40 hex characters")
    if len(references) != 2 or references[0] == references[1]:
        raise ConfigError("two different reference RPCs are required")
    if not 1 <= cfg.max_missed <= cfg.window_blocks <= 1000 or not 1 <= cfg.max_consecutive_missed <= cfg.window_blocks:
        raise ConfigError("invalid signature thresholds")
    if (not 1 <= cfg.poll_seconds <= 300 or cfg.block_timeout_seconds < 5
            or cfg.max_lag < 0 or cfg.cooldown_seconds < 0):
        raise ConfigError("invalid timing")
    return cfg
