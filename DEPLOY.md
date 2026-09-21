# digital-fabric-www — Deploy

Static marketing site for digital-fabric.com (no build step — pure HTML/CSS, fully crawlable).

## Current hosting observation (2026-09-21 UTC)

`https://www.digital-fabric.com/` is served by S3/CloudFront. DNS points to
`d185amnwxfcox2.cloudfront.net`; the existing deployment workflow targets
`digital-fabric-www-static` and distribution `E1N0BQ9H3UGHS8`. The June notes below
are retained history, not current DNS instructions. Do not execute the old apex
cutover plan without a separately reviewed migration.

GitHub Pages retains its existing deployment/custom domain so the historical
`https://8braid.github.io/digital-fabric-www/` entry point continues redirecting to
`http://www.digital-fabric.com/`. On September 21 its build setting changed from
`legacy` to `workflow` to stop rebuilding the secondary copy on every hourly
status commit. No Pages publishing workflow was added. No DNS, custom domain,
HTTPS setting, live content or S3 workflow was changed. Immediate verification
confirmed the primary HTTPS 200 and the unchanged legacy 301 destination.

The hourly observer must continue recording and publishing unchanged successes
and failures as described in `scripts/STATUS-OBSERVATIONS.md`. Do not skip an
observation merely because ledger values are unchanged. Full-site publication
remains the existing separately triggered S3 workflow. A documentation-only edit
does not call it.

Ashley subsequently prohibited GitHub Actions execution. Do not restore legacy
Pages builds, add a Pages workflow or dispatch any existing Actions workflow.
Keep the existing redirect/site settings intact. The still-configured hourly
collector and S3 publisher require a separately qualified host-scheduler
migration with least-privilege AWS credentials; preserving their YAML is historical
source, not authorization to execute it. Check primary reachability and observation
freshness during that migration. Do not delete or recreate the Pages site.

Coordination: Core task `DP-20260920-EXECUTION` / `recF4ixEIieMto3rr`.
The live primary homepage differed from repository main at observation time;
do not use this maintenance change to redeploy unrelated content.

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
