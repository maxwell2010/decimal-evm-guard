from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import Config


class NotificationError(RuntimeError):
    pass


def send_validator_offline(cfg: Config, report: dict, tx_hash: str | None) -> None:
    reasons = []
    if report["missed"] >= cfg.max_missed:
        reasons.append(f"max_missed: {report['missed']} >= {cfg.max_missed} в окне из {report['window']} блоков")
    if report["consecutive_missed"] >= cfg.max_consecutive_missed:
        reasons.append(f"max_consecutive_missed: {report['consecutive_missed']} >= {cfg.max_consecutive_missed} подряд")
    if not reasons:
        raise NotificationError("pause report has no triggered threshold")
    message = f"Узел: {cfg.node_name}\nВалидатор отключен после пропуска подписей.\nПричина: " + "; ".join(reasons)
    if tx_hash:
        message += f"\nТранзакция: {tx_hash}"
    request = Request(
        f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendMessage",
        data=urlencode({"chat_id": cfg.telegram_user_id, "text": message}).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise NotificationError(f"Telegram returned HTTP {exc.code}") from None
    except (URLError, OSError, ValueError) as exc:
        raise NotificationError(f"Telegram request failed ({type(exc).__name__})") from None
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise NotificationError("Telegram did not confirm delivery")
