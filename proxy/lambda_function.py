"""
df-ledger-cors-proxy — a thin, READ-ONLY, CORS-enabled proxy in front of the
TrustDB ledger gateway so the static explorer (GitHub Pages) can read live state
from the browser. The gateway itself sends no CORS headers; this adds them.

Security: only read-only ledger tools are allowed. genesis/transfer and anything
that mutates are rejected — a public browser endpoint must never be able to move
value or open a ledger.
"""
import json
import urllib.request
import urllib.error

UPSTREAM = "https://api.digital-fabric.com/api/skills/execute"

# Read-only tools only. NO ledger_genesis / ledger_transfer / refresh.
ALLOWED_TOOLS = {
    "ledger_state",
    "ledger_balance",
    "ledger_verify",
    "ledger_sanctions_status",
    "ledger_sanctions_history",
    "ledger_sanctions_verify_chain",
}

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
    "Access-Control-Max-Age": "86400",
}


def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", **CORS},
        "body": json.dumps(body),
    }


def handler(event, context):
    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "POST"
    )
    if method == "OPTIONS":
        return {"statusCode": 204, "headers": CORS, "body": ""}

    try:
        raw = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            import base64
            raw = base64.b64decode(raw).decode("utf-8")
        payload = json.loads(raw)
    except Exception:
        return _resp(400, {"result": None, "error": "invalid JSON body", "tool": None})

    tool = payload.get("tool_name")
    if tool not in ALLOWED_TOOLS:
        return _resp(403, {
            "result": None,
            "error": f"tool not permitted via public proxy: {tool!r} (read-only only)",
            "tool": tool,
        })

    upstream_body = json.dumps({
        "tool_name": tool,
        "params": payload.get("params", {}),
    }).encode("utf-8")

    req = urllib.request.Request(
        UPSTREAM,
        data=upstream_body,
        headers={"Content-Type": "application/json", "X-Substrate-Stack": "fresh"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read().decode("utf-8")
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", **CORS},
            "body": data,  # pass the envelope through verbatim
        }
    except urllib.error.HTTPError as e:
        return _resp(e.code, {"result": None, "error": f"upstream {e.code}", "tool": tool})
    except Exception as e:
        return _resp(502, {"result": None, "error": f"upstream unreachable: {e}", "tool": tool})
