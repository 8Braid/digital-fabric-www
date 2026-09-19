#!/usr/bin/env python3
"""Publish observations of three read-only ledger tools, including failed checks.

Each check advances checked_at. Last-success and last-observed-change times are
separate. Failed components retain only their validated, public-safe last result.
No opening, issuance, transfer or other ledger mutation is available here.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone

UPSTREAM = "https://api.digital-fabric.com/api/skills/execute"
HEADERS = {"Content-Type": "application/json", "X-Substrate-Stack": "fresh"}
TOOLS = {"state": "ledger_state", "verify": "ledger_verify", "sanctions": "ledger_sanctions_status"}
TIMEOUT = 20
MAX_RESPONSE = 1024 * 1024


def call(tool):
    body = json.dumps({"tool_name": tool, "params": {}}).encode("utf-8")
    req = urllib.request.Request(UPSTREAM, data=body, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError("response too large")
        return json.loads(raw)


def public_value(name, value):
    """Allowlist aggregates; never publish balances, upstream errors or extra data."""
    if not isinstance(value, dict):
        raise ValueError("missing result")
    numbers = {"state": ("accounts", "total_supply", "braid_length"),
               "verify": ("braid_length",), "sanctions": ()}[name]
    result = {}
    for key in numbers:
        number = value.get(key)
        if type(number) is not int or not 0 <= number <= 2**53 - 1:
            raise ValueError("invalid aggregate")
        result[key] = number
    if name != "sanctions":
        commitment = value.get("state_commitment")
        if not isinstance(commitment, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", commitment):
            raise ValueError("invalid commitment")
        result["state_commitment"] = commitment.lower()
    flag = {"verify": "verified", "sanctions": "installed"}.get(name)
    if flag:
        if type(value.get(flag)) is not bool:
            raise ValueError("missing boolean")
        result[flag] = value[flag]
    return result


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is not None:
            return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        pass
    return None


def previous_component(previous, name):
    components = previous.get("components")
    old = components.get(name, {}) if isinstance(components, dict) else {}
    if not isinstance(old, dict):
        old = {}
    legacy = previous.get("schema_version") != 2
    value = previous.get(name) if legacy else old.get("value")
    success = timestamp(previous.get("generated_at") if legacy else old.get("last_success_at"))
    try:
        value = public_value(name, value)
        if not success:
            raise ValueError("undated result")
    except ValueError:
        return {"value": None, "last_success_at": None, "last_change_at": None}
    return {"value": value, "last_success_at": success,
            "last_change_at": timestamp(old.get("last_change_at")) if not legacy else None}


def observe(previous, now, fetch=call):
    previous = previous if isinstance(previous, dict) else {}
    components = {}
    for name, tool in TOOLS.items():
        old = previous_component(previous, name)
        component = {**old, "status": "error", "error": None, "latency_ms": None}
        try:
            response = fetch(tool)
            if not isinstance(response, dict):
                raise ValueError("invalid envelope")
            if response.get("error"):
                component["error"] = "tool_error"
            else:
                value = public_value(name, response.get("result"))
                component.update(status="ok", value=value, last_success_at=now,
                                 last_change_at=now if old["value"] is not None and value != old["value"] else old["last_change_at"])
                latency = response.get("latency_ms")
                if type(latency) in (int, float) and 0 <= latency <= TIMEOUT * 1000 and math.isfinite(latency):
                    component["latency_ms"] = latency
        except urllib.error.HTTPError:
            component["error"] = "http_error"
        except (TimeoutError, urllib.error.URLError, OSError):
            component["error"] = "unreachable"
        except (ValueError, UnicodeError):
            component["error"] = "invalid_response"
        components[name] = component
    successes = sum(c["status"] == "ok" for c in components.values())
    status = "success" if successes == len(TOOLS) else "partial" if successes else "error"
    old_success = timestamp(previous.get("last_success_at"))
    return {"schema_version": 2, "checked_at": now,
            "last_success_at": now if status == "success" else old_success,
            "observation_status": status,
            "recovered": status == "success" and bool(old_success) and
                         previous.get("observation_status") in ("error", "partial"),
            "endpoint": UPSTREAM, "components": components}


def write_snapshot(path, snapshot):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, delete=False) as output:
            temporary = output.name
            json.dump(snapshot, output, indent=2, allow_nan=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="data/ledger-status.json")
    args = parser.parse_args()
    try:
        previous = json.loads(Path(args.output).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        previous = {}
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    snapshot = observe(previous, now)
    write_snapshot(args.output, snapshot)
    print(f"Saved observation: {snapshot['observation_status']} at {now}")
    if snapshot["observation_status"] != "success":
        print("::warning::Incomplete upstream observation; retained values are historical.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
