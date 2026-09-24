from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class NotificationError(RuntimeError):
    pass


def send_validator_offline(bot_token: str, user_id: int, node_name: str, report: dict, tx_hash: str | None) -> None:
    message = (
        f"Валидатор {node_name} отключен после пропуска подписей.\n"
        f"Пропущено: {report['missed']} из {report['window']}, подряд: {report['consecutive_missed']}."
    )
    if tx_hash:
        message += f"\nТранзакция: {tx_hash}"
    request = Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=urlencode({"chat_id": user_id, "text": message}).encode("utf-8"),
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
