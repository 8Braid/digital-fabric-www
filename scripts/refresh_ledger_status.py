#!/usr/bin/env python3
"""
Refresh data/ledger-status.json — the snapshot the public network status page
(explorer.html) renders.

Calls the read-only ledger tools on the live gateway (server-side, so no CORS and
no auth needed) and assembles the snapshot in the exact shape explorer.html
expects. Run by .github/workflows/refresh-ledger-status.yml on an hourly schedule.

READ-ONLY by construction: only ledger_state / ledger_verify /
ledger_sanctions_status are called. This script never mutates the ledger — it
cannot open a ledger or move value.

To keep the git history clean, the file (and its `generated_at` timestamp) is
only rewritten when the *substantive* state changes. Volatile fields that change
on every call — tool latency, the sanctions clock — are excluded from that
comparison, so an idle ledger does not produce hourly no-op commits.
"""
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

UPSTREAM = "https://api.digital-fabric.com/api/skills/execute"
HEADERS = {"Content-Type": "application/json", "X-Substrate-Stack": "fresh"}
OUT = "data/ledger-status.json"
TIMEOUT = 20


def call(tool):
    body = json.dumps({"tool_name": tool, "params": {}}).encode("utf-8")
    req = urllib.request.Request(UPSTREAM, data=body, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def signature(snap):
    """The fields that actually matter — excludes generated_at, latency_ms, and
    the sanctions wall-clock (now_iso/now_ms), which change on every call."""
    state = snap.get("state") or {}
    verify = snap.get("verify") or {}
    sanctions = snap.get("sanctions") or {}
    return {
        "gateway": snap.get("gateway"),
        "state": ({k: state.get(k) for k in
                   ("accounts", "balances", "total_supply", "braid_length", "state_commitment")}
                  if snap.get("state") is not None else None),
        "state_error": snap.get("state_error"),
        "verify": ({k: verify.get(k) for k in ("verified", "braid_length", "state_commitment")}
                   if snap.get("verify") is not None else None),
        "verify_error": snap.get("verify_error"),
        "sanctions_installed": sanctions.get("installed"),
        "sanctions_error": snap.get("sanctions_error"),
    }


def main():
    try:
        state = call("ledger_state")
        verify = call("ledger_verify")
        sanctions = call("ledger_sanctions_status")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        # Leave the last good snapshot in place rather than overwrite it with an
        # error — a transient gateway blip should not blank the public page.
        print(f"gateway unreachable, keeping last snapshot: {e}", file=sys.stderr)
        return 1

    snapshot = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "gateway": state.get("gateway") or verify.get("gateway") or "unreachable",
        "endpoint": "api.digital-fabric.com (fresh substrate stack)",
        "state": state.get("result"),
        "state_error": state.get("error"),
        "verify": verify.get("result"),
        "verify_error": verify.get("error"),
        "sanctions": sanctions.get("result"),
        "sanctions_error": sanctions.get("error"),
        "latency_ms": {
            "state": state.get("latency_ms"),
            "verify": verify.get("latency_ms"),
            "sanctions": sanctions.get("latency_ms"),
        },
    }

    try:
        with open(OUT, encoding="utf-8") as f:
            previous = json.load(f)
        if signature(previous) == signature(snapshot):
            print("no substantive change; leaving snapshot and its timestamp as-is")
            return 0
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(snapshot, f, indent=2)
        f.write("\n")

    st = snapshot["state"] or {}
    print(f"wrote {OUT}: accounts={st.get('accounts')} "
          f"braid_length={st.get('braid_length')} "
          f"verified={(snapshot['verify'] or {}).get('verified')} "
          f"gate_installed={(snapshot['sanctions'] or {}).get('installed')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
