# digital-fabric-www — Deploy

Static marketing site for digital-fabric.com (no build step — pure HTML/CSS, fully crawlable).

## Status

- **Content:** built 2026-06-12 per `STRATEGIC-PLAN-2026-06-12.md` §6 (TrustDB Crypto folder).
  Claims-censored: no BFT claim, no token, no benchmark numbers (NDA route), no X Compression, no Neo4j.
- **Repo:** PRIVATE until the patent gate clears (Airtable task `recqQ89KrLzE11zWd`,
  resolved by Handoff 3). Going public = public disclosure; that decision is Ashley's, explicitly.

## Launch sequence (after the gate clears)

1. **Make repo public + enable GitHub Pages** (fastest path):
   ```bash
   gh repo edit DIGITAL-FABRIC-AI/digital-fabric-www --visibility public --accept-visibility-change-consequences
   gh api repos/DIGITAL-FABRIC-AI/digital-fabric-www/pages -X POST \
     -f "source[branch]=main" -f "source[path]=/" 2>/dev/null || true
   gh api repos/DIGITAL-FABRIC-AI/digital-fabric-www/pages -X PUT -f cname=www.digital-fabric.com
   ```
2. **DNS (Route53 zone `Z03515133FZH0VQBWNXXF`):**
   - Preview first: `preview.digital-fabric.com` CNAME → `digital-fabric-ai.github.io`
   - Cutover: point `www` CNAME at `digital-fabric-ai.github.io`; apex `digital-fabric.com`
     ALIAS → Pages IPs (or keep apex on the app and use www for marketing).
3. **The app problem:** the apex currently serves the operational platform-messaging app
   (auth-gated). Before apex cutover, the app must move to `app.digital-fabric.com`
   (new ALB listener rule / ingress host + frontend env update). Until then, marketing can
   live at `www.` while the apex keeps serving the app.
4. After launch: submit to Google Search Console; verify `curl -s https://www.digital-fabric.com | grep "survives Q-day"` returns real HTML.

## Editing

`index.html` (home) and `claims.html` (claims & verification). Keep every claim consistent
with the Honest Gaps register and plan §3 claims table. New claims require shipped code.
