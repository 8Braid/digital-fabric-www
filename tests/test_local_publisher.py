import json
from pathlib import Path
import tempfile
import unittest
from status_fixtures import fixtures, TIMES
from publish_status_local import execute, exclusive, verify_identity, ACCOUNT

SHA = "a" * 40


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.state = Path(self.tmp.name) / "state"
        (self.repo / "data").mkdir(parents=True)
        self.cases = fixtures()
        (self.repo / "data/ledger-status.json").write_text(json.dumps(self.cases["first"]))
        self.calls = []
        self.collections = 0
        self.fail = None
        self.snapshot = self.cases["unchanged"]

    def cli(self, args, cwd=None):
        self.calls.append(args)
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            return SHA
        if args[:2] == ["git", "status"]:
            return ""
        if args[:3] == ["aws", "sts", "get-caller-identity"]:
            return json.dumps({"Account": ACCOUNT, "Arn": f"arn:aws:sts::{ACCOUNT}:assumed-role/status-host/session"})
        if args[:3] == ["aws", "s3", "cp"]:
            if self.fail == "upload":
                raise RuntimeError("private CLI failure should not be journaled")
            return ""
        if args[:3] == ["aws", "cloudfront", "create-invalidation"]:
            if self.fail == "invalidation":
                raise RuntimeError("private invalidation failure")
            return json.dumps({"Invalidation": {"Id": "test-id"}})
        raise AssertionError(args)

    def collect(self, previous, now):
        self.collections += 1
        return self.snapshot

    def publish(self, job="hour01"):
        return execute(self.repo, self.state, SHA, job, "status-host", self.cli, self.collect)

    def test_unchanged_success_publishes_and_retains_dated_history(self):
        self.publish()
        saved = json.loads((self.state / "hour01/observation.json").read_text())
        self.assertEqual(saved["checked_at"], TIMES[1])
        self.assertEqual(saved["components"]["state"]["value"], self.cases["first"]["components"]["state"]["value"])
        self.assertTrue((self.state / "hour01/published.json").exists())
        self.assertEqual(len([x for x in self.calls if x[:3] == ["aws", "s3", "cp"]]), 1)

    def test_failed_observation_is_published_with_original_success_time(self):
        self.snapshot = self.cases["failed"]
        self.publish()
        saved = json.loads((self.state / "hour01/observation.json").read_text())
        self.assertEqual(saved["observation_status"], "error")
        self.assertEqual(saved["last_success_at"], TIMES[1])
        self.assertTrue((self.state / "hour01/published.json").exists())

    def test_upload_failure_keeps_snapshot_and_retry_does_not_recollect(self):
        self.fail = "upload"
        with self.assertRaises(RuntimeError):
            self.publish()
        raw = (self.state / "hour01/observation.json").read_bytes()
        self.assertFalse((self.state / "hour01/published.json").exists())
        self.assertNotIn("private CLI", (self.state / "hour01/effects.jsonl").read_text())
        self.fail = None
        self.publish()
        self.assertEqual(self.collections, 1)
        self.assertEqual(raw, (self.state / "hour01/observation.json").read_bytes())

    def test_invalidation_failure_is_visible_and_caller_reference_stable(self):
        self.fail = "invalidation"
        with self.assertRaises(RuntimeError):
            self.publish()
        batch = (self.state / "hour01/invalidation.json").read_bytes()
        self.assertFalse((self.state / "hour01/published.json").exists())
        self.fail = None
        self.publish()
        self.assertEqual(batch, (self.state / "hour01/invalidation.json").read_bytes())
        self.assertEqual(self.collections, 1)

    def test_complete_retry_has_no_second_external_write(self):
        self.publish()
        self.publish()
        self.assertEqual(self.collections, 1)
        self.assertEqual(len([x for x in self.calls if x[:3] == ["aws", "s3", "cp"]]), 1)

    def test_old_job_cannot_revert_newer_observation(self):
        self.publish()
        self.snapshot = self.cases["changed"]
        self.publish("hour02")
        with self.assertRaisesRegex(RuntimeError, "superseded"):
            self.publish()
        self.assertEqual(json.loads((self.state / "latest-observation.json").read_text())["checked_at"], TIMES[2])

    def test_tampered_payload_fails_before_upload(self):
        self.publish()
        (self.state / "hour01/observation.json").write_text("{}")
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            self.publish()

    def test_wrong_identity_and_source_fail_closed(self):
        for identity in [{"Account": "wrong"}, {"Account": ACCOUNT, "Arn": f"arn:aws:sts::{ACCOUNT}:assumed-role/broad-admin/session"}]:
            with self.assertRaises(RuntimeError):
                verify_identity(identity, "status-host")
        with self.assertRaisesRegex(RuntimeError, "SHA"):
            execute(self.repo, self.state, "b" * 40, "wrongsha", "status-host", self.cli, self.collect)
        self.assertEqual(self.collections, 0)

    def test_overlap_is_rejected_without_removing_owners_lock(self):
        self.state.mkdir()
        with exclusive(self.state):
            with self.assertRaises(FileExistsError):
                self.publish()
            self.assertTrue((self.state / "publisher.lock").exists())
        self.assertFalse((self.state / "publisher.lock").exists())


if __name__ == "__main__":
    unittest.main()
