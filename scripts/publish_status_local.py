#!/usr/bin/env python3
"""Direct-host status job. Plans by default; never dispatches GitHub Actions."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from refresh_ledger_status import observe, write_snapshot

BUCKET = "s3://digital-fabric-www-static/data/ledger-status.json"
DISTRIBUTION = "E1N0BQ9H3UGHS8"
ACCOUNT = "635298978260"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def command(args, cwd=None):
    # Do not include CLI stderr, credentials or raw upstream bodies in receipts.
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError(f"{args[0]} command failed (exit {result.returncode})")
    return result.stdout.strip()


def receipt(path, event, **fields):
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({"at": utc_now(), "event": event, **fields}) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


@contextmanager
def exclusive(state):
    lock = state / "publisher.lock"
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode())
        os.close(descriptor)
        yield
    finally:
        lock.unlink()


def verify_identity(identity, role_name):
    prefix = f"arn:aws:sts::{ACCOUNT}:assumed-role/{role_name}/"
    if identity.get("Account") != ACCOUNT or not identity.get("Arn", "").startswith(prefix):
        raise RuntimeError("AWS identity does not match the approved account/role")


def execute(repo, state, source_sha, job_id, role_name, run=command, collect=observe):
    """One exact source/job. Reusing a job ID retries its saved bytes, not collection."""
    state.mkdir(parents=True, exist_ok=True)
    if state == repo or repo in state.parents:
        raise ValueError("state directory must be outside the source checkout")
    with exclusive(state):
        job = state / job_id
        job.mkdir(exist_ok=True)
        journal = job / "effects.jsonl"
        snapshot_path, manifest_path = job / "observation.json", job / "manifest.json"
        receipt(journal, "attempt", source_sha=source_sha, job_id=job_id)
        phase = "source"
        try:
            if run(["git", "rev-parse", "HEAD"], repo) != source_sha:
                raise RuntimeError("source SHA mismatch")
            if run(["git", "status", "--porcelain", "--untracked-files=no"], repo):
                raise RuntimeError("tracked source changes require a new qualified commit")
            phase = "identity"
            identity = json.loads(run(["aws", "sts", "get-caller-identity", "--output", "json"]))
            verify_identity(identity, role_name)
            receipt(journal, "identity_verified", account=ACCOUNT, role=role_name)
            phase = "observation"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text())
                if manifest["source_sha"] != source_sha or manifest["job_id"] != job_id:
                    raise RuntimeError("job identity changed")
                snapshot = json.loads(snapshot_path.read_text())
                if hashlib.sha256(snapshot_path.read_bytes()).hexdigest() != manifest["sha256"]:
                    raise RuntimeError("saved observation checksum mismatch")
            else:
                if snapshot_path.exists():
                    raise RuntimeError("incomplete saved job requires owner recovery; do not overwrite")
                previous_path = state / "latest-observation.json"
                if not previous_path.exists():
                    previous_path = repo / "data/ledger-status.json"
                # Corrupt state is an operational failure, not permission to erase history.
                previous = json.loads(previous_path.read_text(encoding="utf-8"))
                snapshot = collect(previous, utc_now())
                write_snapshot(snapshot_path, snapshot)
                manifest = {"job_id": job_id, "source_sha": source_sha,
                            "sha256": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
                            "bucket": BUCKET, "distribution": DISTRIBUTION}
                write_snapshot(manifest_path, manifest)
            # A recorded attempt remains the next observation's history even if publication fails.
            # Do not let retrying an old job overwrite newer collected/published state.
            latest = state / "latest-observation.json"
            if latest.exists() and json.loads(latest.read_text())["checked_at"] > snapshot["checked_at"]:
                raise RuntimeError("superseded job cannot replace a newer observation")
            write_snapshot(latest, snapshot)
            receipt(journal, "observation_saved", sha256=manifest["sha256"],
                    observation_status=snapshot["observation_status"], checked_at=snapshot["checked_at"])
            if (job / "published.json").exists():
                receipt(journal, "already_published", sha256=manifest["sha256"])
                return manifest
            phase = "upload"
            run(["aws", "s3", "cp", str(snapshot_path), BUCKET, "--content-type", "application/json",
                 "--cache-control", "public, max-age=300", "--metadata",
                 f"sha256={manifest['sha256']},job={job_id}", "--only-show-errors"])
            receipt(journal, "uploaded", sha256=manifest["sha256"])
            phase = "invalidation"
            batch = job / "invalidation.json"
            write_snapshot(batch, {"Paths": {"Quantity": 1, "Items": ["/data/ledger-status.json"]},
                                   "CallerReference": f"df-status-{job_id}-{manifest['sha256']}"})
            answer = json.loads(run(["aws", "cloudfront", "create-invalidation", "--distribution-id",
                                     DISTRIBUTION, "--invalidation-batch", "file://" + str(batch), "--output", "json"]))
            invalidation_id = answer["Invalidation"]["Id"]
            receipt(journal, "invalidation_requested", invalidation_id=invalidation_id)
            # Request receipt is not evidence that the CDN already serves the new bytes.
            write_snapshot(job / "published.json", {**manifest, "invalidation_id": invalidation_id,
                                                     "status": "uploaded_and_invalidation_requested"})
            return manifest
        except Exception as exc:
            receipt(journal, "failed", phase=phase, error_type=type(exc).__name__)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--expected-role", required=True, help="approved STS assumed-role name; no credential values")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_sha):
        parser.error("source-sha must be a full lowercase commit SHA")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", args.job_id):
        parser.error("job-id must be a bounded safe filename")
    if not re.fullmatch(r"[A-Za-z0-9+=,.@_-]{1,64}", args.expected_role):
        parser.error("expected-role must be an IAM role name")
    repo = Path(__file__).resolve().parents[1]
    if not args.execute:
        print(json.dumps({"mode": "plan_only", "source_sha": args.source_sha, "job_id": args.job_id,
                          "state_dir": str(args.state_dir.resolve()), "account": ACCOUNT,
                          "expected_role": args.expected_role, "object": BUCKET,
                          "invalidation_path": "/data/ledger-status.json",
                          "requires": ["qualified direct-host scheduler", "dedicated UID", "scoped temporary AWS identity",
                                       "durable state backup", "external freshness/failure check"]}, indent=2))
        return 0
    try:
        execute(repo, args.state_dir.resolve(), args.source_sha, args.job_id, args.expected_role)
    except Exception as exc:
        print(f"Status publication failed: {type(exc).__name__}. Inspect private effect receipts.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
