"""Only monitor-specific fixtures; no training imports or scientific data reads."""
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import sqlite3
import uuid
import threading
import unittest
from http.server import ThreadingHTTPServer
from server import Reader, POPULATION, handler_for, metric_summary


class MonitorTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parent
        self.folder = (root / "test-fixtures" / uuid.uuid4().hex).resolve()
        if self.folder.parent.parent != root:
            raise ValueError("Fixtures must stay in monitor directory")
        self.folder.mkdir(parents=True)
        db = sqlite3.connect(self.folder / "updates.sqlite")
        db.execute("CREATE TABLE identity(value TEXT)")
        identity = dict(decision=dict(seed=2029, cap=8640, population_sha256=POPULATION), data={})
        db.execute("INSERT INTO identity VALUES (?)", (json.dumps(identity),))
        db.execute("CREATE TABLE updates(model TEXT,u INTEGER,state TEXT)")
        db.execute("INSERT INTO updates VALUES ('B3',1,'RETURNED')")
        db.execute("INSERT INTO updates VALUES ('B3',2,'INTENT')")
        db.commit(); db.close()

    def reader(self):
        return Reader(self.folder)

    def test_read_only_update_counts_and_no_false_liveness(self):
        path = self.folder / "updates.sqlite"
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        s = self.reader().snapshot(include_resources=False)
        self.assertEqual((s["returned"], s["reserved"], s["uncertain"]), (1, 2, 1))
        self.assertEqual(s["state"], "UNKNOWN")
        self.assertEqual(s["runs"][0]["epochs"][0]["phase"], "TRAINING")
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_validation_not_mistaken_for_completed_epoch(self):
        (self.folder / "B3_train_01.json").write_text('{"weighted_mean":0.7}')
        s = self.reader().snapshot(include_resources=False)
        self.assertEqual(s["runs"][0]["epochs"][0]["phase"], "VALIDATION")
        self.assertEqual(s["runs"][0]["sealed_epochs"], 0)

    def test_io_sums_completed_and_active_once(self):
        a = self.folder / "B3_train_reads_01"; a.mkdir()
        (a / "pass_receipt.json").write_text(json.dumps(dict(actual_reads=dict(
            opened_files=3, delivered_bytes=40, reserved_bytes=40, states={"READ_COMPLETE": 3}))))
        b = self.folder / "B3_dev_reads_01"; b.mkdir()
        db = sqlite3.connect(b / "reads.sqlite")
        db.execute("CREATE TABLE file_io(state TEXT,actual_bytes INTEGER,expected_bytes INTEGER)")
        db.execute("INSERT INTO file_io VALUES ('INTENT',5,10)"); db.commit(); db.close()
        io = self.reader().snapshot(include_resources=False)["io"]
        self.assertEqual((io["files"], io["bytes"], io["reserved_bytes"], io["sealed"]), (4, 45, 50, 1))
        self.assertEqual(len(io["active"]), 1)

    def test_failure_overrides_still_present_process(self):
        (self.folder / "failure.json").write_text('{"error":"fixture error"}')
        self.assertEqual(self.reader().snapshot(include_resources=False)["state"], "FAILED")

    def test_identity_mismatch_is_rejected(self):
        db = sqlite3.connect(self.folder / "updates.sqlite")
        db.execute("UPDATE identity SET value=?", (json.dumps(dict(decision=dict(seed=2027, cap=8640, population_sha256=POPULATION))),))
        db.commit(); db.close()
        with self.assertRaises(ValueError): self.reader()

    def test_metric_population_digest_and_missing_values_are_preserved(self):
        report = {"groups": {"all": {"ids_sha": "fixture-id-digest", "summary": {
            "scenes": 963, "coverage": [None] * 32, "brier": 0.05,
            "rain_strata": [{"upper": None, "n": 0, "conditional_pinball": None}]}}}}
        result = metric_summary(report)["all"]
        self.assertEqual(result["ids_sha"], "fixture-id-digest")
        self.assertIsNone(result["q32_coverage"])
        self.assertIsNone(result["rain_strata"][0]["conditional_pinball"])

    def test_http_is_loopback_static_allowlist_and_read_only(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.reader()))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            con = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
            for method, path, host, expected in [
                ("GET", "/", None, 200), ("GET", "/updates.sqlite", None, 404),
                ("GET", "/../server.py", None, 404), ("POST", "/api/start", None, 405),
                ("GET", "/", "external.example", 403)]:
                con.request(method, path, headers={"Host": host} if host else {})
                response = con.getresponse(); response.read()
                self.assertEqual(response.status, expected, (method, path, host))
            con.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()


class RecoveryMonitorTests(MonitorTests):
    def request(self):
        parent=self.folder/'parent';parent.mkdir()
        for e in (1,2,3):
            (parent/f'B3_train_{e:02d}.json').write_text('{"weighted_mean":0.5}')
            (parent/f'B3_LAST_epoch_{e:02d}.receipt.json').write_text('{"checkpoint_sha256":"fixture"}')
        (parent/'B3_train_04.json').write_text('{"weighted_mean":99}')
        verify=self.folder.with_name(self.folder.name+'_source_verification');verify.mkdir()
        (verify/'source_verification_receipt.json').write_text(json.dumps(dict(states={'READ_COMPLETE':1},delivered_bytes=5,reserved_bytes=5,opened_files=1)))
        request=dict(parent=str(parent),prior_updates=1920,inherited_updates=1440,cumulative_update_cap=9120,
            cumulative_read_cap=1003568959114,cumulative_file_cap=299968,prior_file_instances=61947,
            prior_delivered_bytes=207606187564,prior_reserved_bytes=207611205829,source_verification_bytes=5)
        request['request_sha256']=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        path=self.folder/'request.json';path.write_text(json.dumps(request))
        db=sqlite3.connect(self.folder/'updates.sqlite');identity=json.loads(db.execute('SELECT value FROM identity').fetchone()[0])
        identity['recovery']=dict(parent=str(parent),request_sha256=request['request_sha256'])
        db.execute('UPDATE identity SET value=?',(json.dumps(identity),));db.execute('UPDATE updates SET u=u+1440');db.commit();db.close()
        return path

    def test_cumulative_cost_and_effective_trajectory_are_separate(self):
        request=self.request();s=Reader(self.folder,recovery_request=request).snapshot(include_resources=False)
        self.assertEqual((s['returned'],s['reserved'],s['uncertain'],s['effective_updates']),(1921,1922,1,1441))
        self.assertEqual(s['runs'][0]['sealed_epochs'],3)
        self.assertIsNone(s['runs'][0]['epochs'][3]['training_loss'])
        self.assertEqual((s['io']['files'],s['io']['bytes']),(61948,207606187569))
        self.assertEqual(s['limits']['updates'],9120)

    def test_recovery_request_tampering_rejected(self):
        request=self.request();v=json.loads(request.read_text());v['cumulative_update_cap']=99999;request.write_text(json.dumps(v))
        with self.assertRaises(ValueError):Reader(self.folder,recovery_request=request)


if __name__ == "__main__": unittest.main(verbosity=2)
