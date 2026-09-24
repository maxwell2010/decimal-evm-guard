from pathlib import Path

import pytest

from decimal_guardian.config import Config


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    return Config(
        node_name="test-validator",
        enabled=False,
        evm_rpc="http://127.0.0.1:8545",
        contract_center="0x" + "1" * 40,
        chain_id=75,
        key_file=tmp_path / "validator.key",
        state_dir=tmp_path / "state",
        consensus_address="A" * 40,
        references=("https://a.example", "https://b.example"),
    )
