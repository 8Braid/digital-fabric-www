"""Synthetic observations shared by Python, renderer and browser checks."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from refresh_ledger_status import observe

TIMES = [(datetime(2026, 9, 19, 18, tzinfo=timezone.utc) + timedelta(hours=i)).isoformat()
         for i in range(5)]
RESULTS = {
    "ledger_state": {"accounts": 3, "total_supply": 3000000, "braid_length": 0,
                     "state_commitment": "a" * 64, "balances": [1000000] * 3},
    "ledger_verify": {"verified": True, "braid_length": 0, "state_commitment": "a" * 64},
    "ledger_sanctions_status": {"installed": False, "now_ms": 12345},
}


def good(tool):
    return {"result": deepcopy(RESULTS[tool]), "latency_ms": 0.4, "private_field": "DO NOT PUBLISH"}


def failed(tool):
    raise TimeoutError("private host and credentials MUST NOT LEAK")


def fixtures():
    first = observe({}, TIMES[0], good)
    unchanged = observe(first, TIMES[1], good)

    def changed(tool):
        response = good(tool)
        if tool == "ledger_state":
            response["result"]["accounts"] = 4
        return response

    error = observe(unchanged, TIMES[2], failed)
    partial = observe(unchanged, TIMES[2], lambda tool: failed(tool) if tool == "ledger_verify" else good(tool))
    return {"first": first, "unchanged": unchanged, "changed": observe(unchanged, TIMES[2], changed),
            "failed": error, "never": observe({}, TIMES[2], failed), "partial": partial,
            "recovered": observe(error, TIMES[3], good)}


if __name__ == "__main__":
    print(json.dumps(fixtures()))
