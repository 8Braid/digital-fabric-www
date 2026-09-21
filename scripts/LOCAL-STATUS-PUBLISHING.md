# Direct-host status publication

Ashley prohibits GitHub Actions. This adapter does not use Actions, a GitHub runner,
GitHub OIDC, stored keys or a GitHub publishing token. `publish_status_local.py`
reuses the reviewed observation/allowlist logic and writes one fixed S3 object.
It is **prepared and locally tested**, not an installed or qualified daemon.

## Host contract

The infrastructure owner must bind a dedicated service UID, read-only checkout at
an exact qualified commit, writable durable state directory outside that checkout,
and an existing direct scheduler/queue. Proposed systemd service+timer is pending
host review; no timer is installed by this package. Limit overlap, apply a bounded
job timeout (allow the three20-second upstream calls and bounded90-second CLI
steps), retain private failure logs, and alert on job failure or stale public data.
Local exclusive locking provides a second overlap check. A crash may leave a lock;
the owner must confirm no process is active before removing that exact lock.

The default credential chain must resolve to an explicitly approved temporary
STS role in account635298978260. `--expected-role` is its name, never a credential.
Do not bind the historical broad infrastructure role. Required writes are only
`s3:PutObject` for `digital-fabric-www-static/data/ledger-status.json` and
`cloudfront:CreateInvalidation` for distribution `E1N0BQ9H3UGHS8`.
Actual policy/trust/credential refresh and supported CLI versions remain host
qualification work. The adapter checks caller identity but that does not prove
the role policy is appropriately narrow. No known current authenticated machine
profile has been verified; the interactive default profile is expired.

## Plan and execute

From the qualified checkout, run Python3 with these explicit arguments:

```text
python3 scripts/publish_status_local.py --source-sha FULL_COMMIT_SHA --job-id UNIQUE_SCHEDULE_SLOT --state-dir ABSOLUTE_PRIVATE_STATE_DIRECTORY --expected-role APPROVED_ROLE_NAME
```

This prints a plan and makes no network calls or state changes. Add `--execute`
only through the approved host binding. A source SHA must be40lowercasehexcharacters;
job IDs use letters/numbers/underscore/hyphen. The same job ID always reuses the
saved observation. A later check requires a new job ID even if values are unchanged.
The checkout and scripts must be immutable to the dedicated runtime identity.

Each job directory retains observation.json, its checksum/source manifest and an
append-only effects.jsonl. This preserves failed observations and publication
failures without raw upstream errors or credential data. Records are not technically
immutable; the host must back them up durably. Git observation commits are replaced
by these per-attempt files, not silently discarded. Seed history initially comes
from the existing checked-in snapshot; subsequent checks use local dated history.

S3 retries overwrite the same object with identical saved bytes. If bucket versioning
is enabled they may create another version; exactly-once S3 writes are not claimed.
CloudFront CallerReference is stable for a job+payload. An invalidation request is
not proof of edge delivery; the external host monitor must verify public JSON/hash,
timestamp and stale/failure rendering. Retrying an older job after a newer observation
is rejected, preventing stale publication. Corrupt/incomplete state fails closed.

## Verification and release

Run existing Python observation tests plus the new publisher tests and the Node
renderer tests directly, without Actions. Tests use synthetic upstream/CLI responses;
no AWS or upstream writes are made. Checks cover unchanged success, historical
failure retention, upload/invalidation failure, exact retry payload, duplicate
completion, old-job rejection, tamper detection, wrongsource/identity and overlap.

Release requires independent wrapper review, exact source identity, host/credential
binding, one observed real job, public freshness/hash validation, and failure/overlap
recovery on that host. Stop the local schedule and retain state on regression;
do not restore Actions or legacy Pages builds. Full-site deployment is a separate
hosted-site publishing contract and is not implemented by this one-object adapter.
