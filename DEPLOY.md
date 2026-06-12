# digital-fabric-www — Deploy

Static marketing site for digital-fabric.com (no build step — pure HTML/CSS, fully crawlable).

## Status (2026-06-12)

- **LIVE** at https://www.digital-fabric.com — public repo, GitHub Pages, HTTPS enforced,
  custom domain currently `www.digital-fabric.com`.
- **Content** claims-censored: no BFT claim, no token, no benchmark numbers (NDA route),
  no X Compression, no Neo4j. (Patent filing gates only deeper *technical-disclosure* pages,
  not this positioning-level site.)
- **Old app** moved to `old.digital-fabric.com` (A-alias → prod ALB). Apex `digital-fabric.com`
  A record still points at that ALB and must be repointed to serve marketing.

## Apex cutover

The single remaining step is repointing the apex A record to GitHub Pages. Full ordered
commands + guardrails are in the canonical runbook:
`Product Guides/TrustDB Crypto/07 Marketing/Website (digital-fabric.com)/APEX-CUTOVER-RUNBOOK-2026-06-12.md`.

Summary: Step 1 (required) `UPSERT` apex A/AAAA → Pages IPs (zone `Z03515133FZH0VQBWNXXF`) —
this alone makes the apex serve marketing (GitHub auto-certs + redirects the apex⇄www pair).
Step 2 (optional) flip the Pages custom domain to the apex to make it canonical. **Never touch
the apex MX/TXT/NS/SOA records** (Google mail + SPF + delegation).

After cutover: submit to Google Search Console; verify `curl -s https://digital-fabric.com | grep "survives Q-day"`.

## Editing

`index.html` (home) and `claims.html` (claims & verification). Keep every claim consistent
with the Honest Gaps register and plan §3 claims table. New claims require shipped code.
