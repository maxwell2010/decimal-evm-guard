from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .evm import EvmProvider
from .guard import GuardError, evaluate, run_forever
from .rpc import RpcError
from .validator import ValidatorError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Decimal EVM validator signature guard")
    parser.add_argument("--config", type=Path, default=Path("/etc/decimal-guardian/config.json"))
    parser.add_argument("action", choices=("guard", "guard-check", "doctor", "status"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)
    try:
        cfg = load_config(args.config)
        if args.action == "status":
            result = {"node": cfg.node_name, "enabled": cfg.enabled}
        elif args.action == "guard-check":
            result = evaluate(cfg)
        elif args.action == "doctor":
            result = {**evaluate(cfg), "validator_paused": EvmProvider(cfg).paused(), "doctor": "ok"}
        else:
            run_forever(cfg, EvmProvider(cfg))
            result = {"result": "guard_stopped"}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ConfigError, GuardError, RpcError, ValidatorError, OSError, ValueError, KeyError, TypeError) as exc:
        logging.error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
