# df-ledger-cors-proxy

A thin, **read-only**, CORS-enabled proxy in front of the TrustDB ledger gateway, so the
static explorer (GitHub Pages) could read live ledger state from the browser. Only read-only
tools are allowed (see `ALLOWED_TOOLS` in `lambda_function.py`) — `ledger_genesis` /
`ledger_transfer` and anything mutating are rejected, so a public browser endpoint can never
move value.

## Status (2026-06-12): deployed, but PUBLIC access is blocked by an Org SCP

- Lambda `df-ledger-cors-proxy` (ca-central-1) is deployed and **works correctly** when invoked
  with IAM auth (`aws lambda invoke` → 200, real envelope).
- A public Function URL (`AuthType: NONE`) was created with a correct public-invoke resource
  policy, **but every anonymous request returns AWS `403 Forbidden`.** Root cause: an
  account/Organization **SCP denies `lambda:InvokeFunctionUrl` for `FunctionUrlAuthType=NONE`**
  (a common security guardrail). A resource policy cannot override an SCP deny.
- **Therefore the browser cannot reach this proxy directly.** The live explorer is NOT wired to
  it; the explorer continues to use the honest hourly snapshot (`data/ledger-status.json`,
  refreshed by the GitHub Action) — no regression.

## Two clean ways to finish the live explorer

1. **CloudFront + OAC in front of this Lambda** (recommended, no trustdb code): switch the
   Function URL to `AuthType: AWS_IAM`, put a CloudFront distribution in front with Origin
   Access Control (CloudFront signs requests with SigV4). The public hits CloudFront, which IS
   permitted; CloudFront invokes the IAM-auth'd Function URL. Reuses this Lambda as-is.
2. **CORS at the gateway** (trustdb code — needs CodeGraph): add the CORS response headers
   directly on `api.digital-fabric.com/api/skills/execute` and drop the proxy entirely.

## Deploy / teardown

`./deploy.sh` (idempotent; `REGION=ca-central-1`). Teardown commands are at the bottom of
`deploy.sh`.
