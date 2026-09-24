from dataclasses import replace
from types import SimpleNamespace

import pytest

from decimal_guardian.evm import EvmProvider
from decimal_guardian.validator import ValidatorError


def test_sender_uses_pending_nonce_and_checks_poststate(cfg):
    settings = replace(cfg, chain_id=75)
    provider = EvmProvider.__new__(EvmProvider)
    provider.cfg = settings
    on_chain = {"paused": False}
    observed = {}

    class Function:
        def call(self):
            return (1, on_chain["paused"], [])

        def estimate_gas(self, tx):
            return 90000

        def build_transaction(self, tx):
            observed.update(tx)
            return tx

    fn = Function()
    functions = SimpleNamespace(getValidator=lambda address: fn, pauseSelf=lambda: fn)
    provider._contract = lambda: SimpleNamespace(functions=functions)
    account = SimpleNamespace(address="0x" + "a" * 40, sign_transaction=lambda tx: SimpleNamespace(
        hash=SimpleNamespace(hex=lambda: "0x" + "1" * 64), raw_transaction=b"signed"))
    provider._account = lambda: account

    class Eth:
        chain_id = 75
        gas_price = 7

        def get_transaction_count(self, address, block):
            assert block == "pending"
            return 4

        def send_raw_transaction(self, raw):
            assert raw == b"signed"
            on_chain["paused"] = True

        def wait_for_transaction_receipt(self, tx_hash, timeout):
            return SimpleNamespace(status=1)

    provider.w3 = SimpleNamespace(eth=Eth())
    result = provider.set_paused(True)
    assert result.tx_hash == "0x" + "1" * 64
    assert observed["nonce"] == 4
    assert observed["chainId"] == 75
    assert observed["gas"] >= 100000
    assert provider.set_paused(True).status == "already_offline"


def test_chain_id_mismatch_blocks_sender(cfg):
    provider = EvmProvider.__new__(EvmProvider)
    provider.cfg = replace(cfg, chain_id=75)
    provider.w3 = SimpleNamespace(eth=SimpleNamespace(chain_id=76))
    provider._account = lambda: SimpleNamespace(address="0x" + "a" * 40)
    provider._contract = lambda: pytest.fail("contract touched")
    with pytest.raises(ValidatorError, match="chain ID"):
        provider.set_paused(True)


def test_guard_rejects_unpause(cfg):
    provider = EvmProvider.__new__(EvmProvider)
    provider.cfg = cfg
    with pytest.raises(ValidatorError, match="only pause"):
        provider.set_paused(False)


def test_mnemonic_uses_fixed_default_path(cfg):
    import json
    import os

    if os.name == "nt":
        pytest.skip("Unix file permissions are required for the secret-file test")

    cfg.key_file.write_text(json.dumps({"mnemonic": "placeholder only"}), encoding="utf-8")
    cfg.key_file.chmod(0o600)
    observed = {}
    account = SimpleNamespace(
        enable_unaudited_hdwallet_features=lambda: None,
        from_mnemonic=lambda phrase, account_path: observed.update(phrase=phrase, path=account_path) or "account",
    )
    provider = EvmProvider.__new__(EvmProvider)
    provider.cfg = cfg
    provider.w3 = SimpleNamespace(eth=SimpleNamespace(account=account))
    assert provider._account() == "account"
    assert observed["path"] == "m/44'/60'/0'/0/0"


def test_unresolved_transaction_prevents_new_send(cfg):
    import json
    from web3.exceptions import TransactionNotFound

    provider = EvmProvider.__new__(EvmProvider)
    provider.cfg = replace(cfg, chain_id=75)
    provider._account = lambda: SimpleNamespace(address="0x" + "a" * 40)
    state = SimpleNamespace(call=lambda: (1, False, []))
    provider._contract = lambda: SimpleNamespace(functions=SimpleNamespace(getValidator=lambda address: state))
    provider.w3 = SimpleNamespace(eth=SimpleNamespace(
        chain_id=75,
        get_transaction_receipt=lambda tx: (_ for _ in ()).throw(TransactionNotFound(tx)),
        send_raw_transaction=lambda raw: pytest.fail("second transaction sent"),
    ))
    cfg.state_dir.mkdir()
    (cfg.state_dir / "evm-tx.json").write_text(json.dumps({"status": "pending", "hash": "0x" + "1" * 64}))
    with pytest.raises(ValidatorError, match="unresolved"):
        provider.set_paused(True)
