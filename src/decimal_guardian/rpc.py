from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen


class RpcError(RuntimeError):
    pass


@dataclass(frozen=True)
class NodeStatus:
    height: int
    catching_up: bool
    network: str
    node_id: str


def fetch_json(url: str, timeout: int = 15) -> dict:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read(2 * 1024 * 1024)
        data = json.loads(body)
        if not isinstance(data, dict) or data.get("error"):
            raise RpcError(f"RPC returned an error at {url}")
        return data
    except (OSError, URLError, ValueError) as exc:
        raise RpcError(f"RPC request failed at {url}: {exc}") from exc


def status(root: str) -> NodeStatus:
    result = fetch_json(root.rstrip("/") + "/status").get("result", {})
    try:
        sync = result["sync_info"]
        node = result["node_info"]
        height = int(sync["latest_block_height"])
        catching_up = sync["catching_up"]
        network = str(node["network"])
        node_id = str(node["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RpcError("RPC status is missing required fields") from exc
    if height <= 0 or not isinstance(catching_up, bool) or not network or not node_id:
        raise RpcError("RPC status has invalid values")
    return NodeStatus(height, catching_up, network, node_id)


def block_hash(root: str, height: int) -> str:
    result = fetch_json(root.rstrip("/") + "/block?height=" + quote(str(height))).get("result", {})
    try:
        actual_height = int(result["block"]["header"]["height"])
        value = str(result["block_id"]["hash"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RpcError("RPC block response is missing hash or height") from exc
    if actual_height != height or len(value) != 64 or any(c not in "0123456789ABCDEFabcdef" for c in value):
        raise RpcError("RPC block hash or height is invalid")
    return value.upper()
