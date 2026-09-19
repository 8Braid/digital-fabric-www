from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from status_fixtures import TIMES, failed, fixtures, good
from refresh_ledger_status import observe, write_snapshot


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.cases = fixtures()

    def test_unchanged_success_advances_check_and_success_not_change(self):
        old, new = self.cases["first"], self.cases["unchanged"]
        self.assertEqual(new["checked_at"], TIMES[1])
        self.assertEqual(new["last_success_at"], TIMES[1])
        for name in old["components"]:
            self.assertIsNone(new["components"][name]["last_change_at"])
            self.assertEqual(new["components"][name]["value"], old["components"][name]["value"])

    def test_changed_success_updates_only_changed_component(self):
        new = self.cases["changed"]
        self.assertEqual(new["components"]["state"]["last_change_at"], TIMES[2])
        self.assertIsNone(new["components"]["verify"]["last_change_at"])

    def test_failure_retains_last_good_as_historical(self):
        old, new = self.cases["unchanged"], self.cases["failed"]
        self.assertEqual(new["checked_at"], TIMES[2])
        self.assertEqual(new["last_success_at"], TIMES[1])
        self.assertEqual(new["observation_status"], "error")
        for name, c in new["components"].items():
            self.assertEqual(c["status"], "error")
            self.assertEqual(c["last_success_at"], TIMES[1])
            self.assertEqual(c["value"], old["components"][name]["value"])
            self.assertIsNone(c["latency_ms"])
        self.assertNotIn("credentials", json.dumps(new))

    def test_never_successful_has_no_invented_data_or_time(self):
        new = self.cases["never"]
        self.assertIsNone(new["last_success_at"])
        for c in new["components"].values():
            self.assertIsNone(c["value"])
            self.assertIsNone(c["last_success_at"])
            self.assertIsNone(c["last_change_at"])

    def test_recovery_keeps_original_change_time(self):
        new = self.cases["recovered"]
        self.assertTrue(new["recovered"])
        self.assertEqual(new["last_success_at"], TIMES[3])
        self.assertIsNone(new["components"]["state"]["last_change_at"])

    def test_partial_failure_does_not_hide_good_components(self):
        new = self.cases["partial"]
        self.assertEqual(new["observation_status"], "partial")
        self.assertEqual(new["components"]["state"]["last_success_at"], TIMES[2])
        self.assertEqual(new["components"]["verify"]["last_success_at"], TIMES[1])
        self.assertEqual(new["last_success_at"], TIMES[1])

    def test_tool_error_is_classified_without_raw_details(self):
        new = observe({}, TIMES[0], lambda _: {"error": "SECRET", "result": {}})
        self.assertEqual(new["components"]["state"]["error"], "tool_error")
        self.assertNotIn("SECRET", json.dumps(new))

    def test_invalid_envelopes_and_fields_fail_closed(self):
        for bad in (None, [], "gateway text", {}, {"result": {}}, {"result": {"installed": "false"}}):
            with self.subTest(bad=bad):
                new = observe({}, TIMES[0], lambda _: bad)
                self.assertEqual(new["observation_status"], "error")
        for field, value in (("accounts", True), ("total_supply", -1), ("braid_length", 2**53),
                             ("state_commitment", "<img onerror=alert(1)>")):
            def fetch(tool):
                response = good(tool)
                if tool == "ledger_state":
                    response["result"][field] = value
                return response
            with self.subTest(field=field):
                self.assertEqual(observe({}, TIMES[0], fetch)["components"]["state"]["error"], "invalid_response")

    def test_only_public_aggregates_survive(self):
        serialized = json.dumps(self.cases["first"])
        for secret in ("balances", "private_field", "DO NOT PUBLISH", "now_ms"):
            self.assertNotIn(secret, serialized)

    def test_legacy_result_retained_without_inventing_check_or_change(self):
        legacy = {"generated_at": TIMES[0], **{n: good(t)["result"] for n, t in
                  (("state", "ledger_state"), ("verify", "ledger_verify"), ("sanctions", "ledger_sanctions_status"))}}
        new = observe(legacy, TIMES[2], failed)
        self.assertIsNone(new["last_success_at"])
        self.assertEqual(new["components"]["state"]["last_success_at"], TIMES[0])
        self.assertIsNone(new["components"]["state"]["last_change_at"])
        self.assertNotIn("balances", json.dumps(new))

    def test_corrupt_previous_cannot_create_success(self):
        for old in (None, [], {"components": []}, {"schema_version": 2, "components": {"state": 42}}):
            with self.subTest(old=old):
                self.assertIsNone(observe(old, TIMES[0], failed)["components"]["state"]["value"])

    def test_transport_and_decode_errors_are_public_safe(self):
        for exception, expected in ((urllib.error.HTTPError("SECRET", 500, "SECRET", {}, None), "http_error"),
                                    (urllib.error.URLError("SECRET"), "unreachable"),
                                    (json.JSONDecodeError("SECRET", "", 0), "invalid_response")):
            def fetch(_):
                raise exception
            with self.subTest(expected=expected):
                new = observe({}, TIMES[0], fetch)
                self.assertEqual(new["components"]["state"]["error"], expected)
                self.assertNotIn("SECRET", json.dumps(new))

    def test_nonfinite_or_huge_latency_is_omitted(self):
        for value in (float("nan"), float("inf"), 10**500, -1, True):
            def fetch(tool):
                return {**good(tool), "latency_ms": value}
            with self.subTest(value=str(value)[:20]):
                new = observe({}, TIMES[0], fetch)
                self.assertEqual(new["observation_status"], "success")
                self.assertIsNone(new["components"]["state"]["latency_ms"])

    def test_atomic_replace_failure_keeps_old_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            write_snapshot(path, self.cases["first"])
            with patch("refresh_ledger_status.os.replace", side_effect=OSError("test")):
                with self.assertRaises(OSError):
                    write_snapshot(path, self.cases["changed"])
            self.assertEqual(json.loads(path.read_text()), self.cases["first"])
            self.assertEqual(len(list(Path(directory).iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
