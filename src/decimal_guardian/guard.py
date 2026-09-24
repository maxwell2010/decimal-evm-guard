from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from functools import lru_cache

from . import rpc
from .config import Config
from .notify import NotificationError, send_validator_offline
from .validator import ValidatorProvider


LOG = logging.getLogger("decimal_guardian.guard")


class GuardError(RuntimeError):
    pass


@dataclass(frozen=True)
class Vote:
    height: int
    block_hash: str
    signed: bool


@lru_cache(maxsize=2048)
def _vote(root: str, height: int, consensus_address: str) -> Vote:
    # The commit in block H+1 attests to validator signatures for block H.
    block = rpc.fetch_json(f"{root}/block?height={height + 1}")["result"]
    commit = block["block"]["last_commit"]
    if int(commit["height"]) != height:
        raise GuardError("RPC commit height mismatch")
    block_hash = str(commit["block_id"]["hash"]).upper()
    if len(block_hash) != 64:
        raise GuardError("RPC returned an invalid commit hash")
    validators = rpc.fetch_json(f"{root}/validators?height={height}&per_page=100")["result"]
    total = int(validators["total"])
    if total > 100:
        raise GuardError("validator set exceeds safe single-page limit")
    addresses = [v["address"].upper() for v in validators["validators"]]
    address = consensus_address.upper()
    if address not in addresses:
        raise GuardError("validator is absent from the historical validator set")
    index = addresses.index(address)
    signatures = commit["signatures"]
    if len(signatures) != len(addresses):
        raise GuardError("commit signature count differs from validator set")
    signature = signatures[index]
    flag = int(signature.get("block_id_flag", 0))
    # 2 = signed this block, 1 = absent, 3 = voted nil.
    if flag not in (1, 2, 3):
        raise GuardError("unknown commit signature flag")
    if flag != 1 and signature.get("validator_address", "").upper() != address:
        raise GuardError("commit signature order differs from validator set")
    return Vote(height, block_hash, flag == 2 and bool(signature.get("signature")))


def evaluate(cfg: Config) -> dict:
    left, right = cfg.guard_references[:2]
    left_status, right_status = rpc.status(left), rpc.status(right)
    if left_status.network != right_status.network or left_status.catching_up or right_status.catching_up:
        raise GuardError("reference RPCs do not agree on a healthy network")
    if abs(left_status.height - right_status.height) > cfg.guard_max_lag:
        raise GuardError("reference RPC heights diverge")
    latest = min(left_status.height, right_status.height) - 1
    if latest < cfg.guard_window:
        raise GuardError("not enough finalized blocks for signature window")
    votes = []
    for height in range(latest - cfg.guard_window + 1, latest + 1):
        a = _vote(left, height, cfg.consensus_address)
        b = _vote(right, height, cfg.consensus_address)
        if a != b:
            raise GuardError(f"reference RPCs disagree at block {height}")
        votes.append(a)
    missed = sum(not vote.signed for vote in votes)
    consecutive = 0
    for vote in reversed(votes):
        if vote.signed:
            break
        consecutive += 1
    return {"latest": latest, "window": len(votes), "missed": missed, "consecutive_missed": consecutive,
            "should_pause": missed >= cfg.guard_max_missed or consecutive >= cfg.guard_max_consecutive_missed}


def run_forever(cfg: Config, provider: ValidatorProvider) -> None:
    if not cfg.guard_enabled:
        LOG.info("signature guard disabled")
        return
    last_height = 0
    last_progress = time.monotonic()
    last_action = float("-inf")
    while True:
        try:
            report = evaluate(cfg)
            LOG.info("signature window height=%s missed=%s/%s consecutive=%s", report["latest"], report["missed"], report["window"], report["consecutive_missed"])
            if report["latest"] > last_height:
                last_height = report["latest"]
                last_progress = time.monotonic()
            if time.monotonic() - last_progress > cfg.guard_block_timeout_seconds:
                LOG.warning("reference block production stopped; no automated transaction")
            elif report["should_pause"] and time.monotonic() - last_action >= cfg.guard_cooldown_seconds:
                if not provider.paused():
                    result = provider.set_paused(True)
                    LOG.warning("validator paused after missed signatures: tx=%s", result.tx_hash)
                    if result.status == "confirmed" and cfg.telegram_bot_token is not None:
                        try:
                            send_validator_offline(
                                cfg.telegram_bot_token, cfg.telegram_user_id, cfg.node_name, report, result.tx_hash
                            )
                        except NotificationError as exc:
                            LOG.warning("validator offline notification failed: %s", exc)
                last_action = time.monotonic()
        except (GuardError, rpc.RpcError, KeyError, ValueError, TypeError) as exc:
            LOG.error("guard sample rejected: %s", exc)
        time.sleep(cfg.guard_poll_seconds)
