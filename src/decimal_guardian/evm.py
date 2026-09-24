from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

from web3 import Web3
from filelock import FileLock
from web3.exceptions import TransactionNotFound

from .config import Config
from .validator import ActionResult, ValidatorError


CENTER_ABI = [{"inputs": [{"name": "", "type": "string"}], "name": "getContractAddress", "outputs": [{"name": "", "type": "address"}], "stateMutability": "view", "type": "function"}]
VALIDATOR_ABI = [
    {"inputs": [{"name": "validator", "type": "address"}], "name": "getValidator", "outputs": [{"components": [{"name": "status", "type": "uint8"}, {"name": "paused", "type": "bool"}, {"name": "penaltyPercantages", "type": "uint16[]"}], "name": "", "type": "tuple"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "pauseSelf", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
]


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".tx-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class EvmProvider:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.w3 = Web3(Web3.HTTPProvider(cfg.evm_rpc, request_kwargs={"timeout": 15}))

    def _account(self):
        path = self.cfg.key_file
        mode = path.stat().st_mode
        if not stat.S_ISREG(mode) or mode & 0o077:
            raise ValidatorError("validator key file must be a regular file with mode 0600")
        secret = json.loads(path.read_text(encoding="utf-8"))
        if set(secret) == {"private_key"}:
            return self.w3.eth.account.from_key(secret["private_key"])
        if set(secret) == {"mnemonic"}:
            self.w3.eth.account.enable_unaudited_hdwallet_features()
            return self.w3.eth.account.from_mnemonic(secret["mnemonic"], account_path="m/44'/60'/0'/0/0")
        raise ValidatorError("key file must contain private_key or mnemonic")

    def _contract(self):
        center = self.w3.eth.contract(address=Web3.to_checksum_address(self.cfg.contract_center), abi=CENTER_ABI)
        address = center.functions.getContractAddress("master-validator").call()
        if not address or int(address, 16) == 0:
            raise ValidatorError("master-validator contract is not configured on chain")
        return self.w3.eth.contract(address=Web3.to_checksum_address(address), abi=VALIDATOR_ABI)

    def paused(self) -> bool:
        account = self._account()
        if self.w3.eth.chain_id != self.cfg.chain_id:
            raise ValidatorError("EVM chain ID differs from configuration")
        return bool(self._contract().functions.getValidator(account.address).call()[1])

    def set_paused(self, paused: bool) -> ActionResult:
        if not paused:
            raise ValidatorError("the guard can only pause a validator")
        lock_path = self.cfg.state_dir / "evm.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with FileLock(str(lock_path), timeout=180):
            account = self._account()
            if self.w3.eth.chain_id != self.cfg.chain_id:
                raise ValidatorError("EVM chain ID differs from configuration")
            contract = self._contract()
            current = bool(contract.functions.getValidator(account.address).call()[1])
            if current:
                return ActionResult("already_offline", None)
            journal = self.cfg.state_dir / "evm-tx.json"
            if journal.exists():
                pending = json.loads(journal.read_text(encoding="utf-8"))
                if pending.get("status") == "pending":
                    tx_hash = pending["hash"]
                    try:
                        receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                    except TransactionNotFound as exc:
                        raise ValidatorError("previous EVM transaction is unresolved; refusing a new nonce") from exc
                    if receipt is None:
                        raise ValidatorError("previous EVM transaction is unresolved; refusing a new nonce")
                    pending["status"] = "confirmed" if receipt.status == 1 else "reverted"
                    _write_json(journal, pending)
                    if receipt.status == 1 and bool(contract.functions.getValidator(account.address).call()[1]) == paused:
                        return ActionResult("confirmed", tx_hash)
                    if receipt.status == 1:
                        raise ValidatorError("previous transaction confirmed; recheck target state")
            fn = contract.functions.pauseSelf()
            base = {"from": account.address, "chainId": self.cfg.chain_id,
                    "nonce": self.w3.eth.get_transaction_count(account.address, "pending"),
                    "gasPrice": self.w3.eth.gas_price}
            gas = fn.estimate_gas({"from": account.address})
            base["gas"] = max(100000, int(gas * 1.25))
            signed = account.sign_transaction(fn.build_transaction(base))
            tx_hash = signed.hash.hex()
            _write_json(journal, {"hash": tx_hash, "nonce": base["nonce"], "action": "pause", "status": "pending"})
            self.w3.eth.send_raw_transaction(signed.raw_transaction)
            try:
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
            except Exception as exc:
                raise ValidatorError("EVM transaction outcome is unknown; check journal before retrying") from exc
            _write_json(journal, {"hash": tx_hash, "nonce": base["nonce"], "action": "pause", "status": "confirmed" if receipt.status == 1 else "reverted"})
            if receipt.status != 1 or bool(contract.functions.getValidator(account.address).call()[1]) != paused:
                raise ValidatorError("EVM receipt or resulting validator state does not match request")
            return ActionResult("confirmed", tx_hash)
