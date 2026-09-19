# Development gateway observations

`refresh_ledger_status.py` calls only `ledger_state`, `ledger_verify` and
`ledger_sanctions_status` at the public skills endpoint. It never opens a ledger,
issues a licence or transfers value. `explorer.html` renders the resulting
`data/ledger-status.json` through `assets/js/ledger-status.js`.

## Timestamp and failure contract

Schema version 2 records every check, including unchanged successes and failures.
`checked_at` identifies the check run. `last_success_at` is the most recent run
that returned usable observations from all three tools. Each component separately
records its last successful observation and the last time a change in its public
values was observed. The first observation is a baseline, not evidence that the
ledger changed at that time, so its change timestamp is unknown. Tool latency and
wall-clock fields do not count as ledger changes.

A failed component retains its last validated public result and original success
time, marks the current observation as an error, and clears current latency.
Partial success is explicit. A failed check with no history has no invented result
or success time. A complete check following a failure is labelled recovered.

Only aggregate counts, total supply, braid length, state commitment, verification
result and installation flag are published. Raw upstream errors, account balances
and unknown fields are omitted. Errors are classified without retaining their
response bodies. Missing fields, wrong types, unsafe numeric values and malformed
commitments are failed observations. Legacy data can supply dated historical
values; it cannot establish a current check or a known last-change time.

The page marks checks older than three hours as stale and rejects a check timestamp
more than five minutes ahead of the browser clock. An open tab ages out without a
reload; reload retrieves the newest saved snapshot. Historical values use warning
styling and explicit labels. A complete check means that all three observations
were retrieved; it does not mean that integrity passed or the compliance gate was
installed. Those results remain visible individually. Separate calls to one
development gateway do not establish a simultaneous snapshot, multi-operator
finality or production licence availability.

## Verification

From the repository root, with Python 3 and Node.js 22 or newer:

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/ledger-status.test.cjs
```

On Windows, set `PYTHON=python` for the Node test process if `python3` is unavailable.
The shared fixtures are synthetic and make no upstream calls. The Python suite
checks observation transitions, field validation, retention and atomic file
replacement. The Node suite consumes those generated fixtures and the actual
page's element IDs. Browser review covers desktop and phone layouts as well as
successful, stale, incomplete, unknown and recovered renderings.

A read-only live check can be saved separately for inspection:

```sh
python3 scripts/refresh_ledger_status.py --output /tmp/ledger-observation.json
```

## Publication

The existing hourly workflow commits and publishes each observation to its single
S3 object, even when ledger values are unchanged. This intentionally allows up to
24 scheduled observation commits per day: preserving accurate check history takes
precedence over suppressing timestamp-only commits. The object is served through
the existing CloudFront distribution. No new infrastructure or service is deployed
by the generator. A failed observation is still published, with a workflow warning;
failure to write or publish remains a workflow failure. This page is a snapshot
display, not a substitute for direct service monitoring or paging.

The existing site deployment excludes test fixtures, Python cache files and the
Git ignore file. New-service deployment, DNS changes and legacy-host retirement
remain separate work.
