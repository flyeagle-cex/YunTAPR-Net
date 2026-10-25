"""Exercise the real guard in synthetic SQLite files, without project imports.

AST extraction avoids importing protocol modules that bind production paths or
look at environment configuration. It executes the unchanged function body.
"""
import ast
from contextlib import closing
import gc
from pathlib import Path
import sqlite3
import shutil
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "src/yuntapr/experimental/phase_b_v2_multiseed_candidate/protocol.py"
V7_DB = "phase_b_v2_seed2027_b1_epoch7_recovery_v7.sqlite"
V7_CAMPAIGN = "YUNTAPR_PHASE_B_V2_SEED2027_B1_EPOCH7_RECOVERY_V7"
FRESH_DB = "phase_b_v2_seed2027_fresh_v1.sqlite"
FRESH_CAMPAIGN = "YUNTAPR_PHASE_B_V2_SEED2027_FRESH_V1"


def extracted(path, name, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


def ledger(root, name, campaign, attempts, *, complete=True):
    path = root / ".git" / name
    with closing(sqlite3.connect(path)) as con, con:
        con.executescript("""
            CREATE TABLE campaign(id TEXT,status TEXT);
            CREATE TABLE attempts(status TEXT);
            CREATE TABLE runs(id TEXT,status TEXT,epoch INTEGER,updates INTEGER);
            CREATE TABLE epochs(run TEXT,epoch INTEGER,phase TEXT);
        """)
        con.execute("INSERT INTO campaign VALUES(?,?)", (campaign, "COMPLETE" if complete else "ACTIVE"))
        con.execute("""WITH RECURSIVE seq(n) AS (
            VALUES(1) UNION ALL SELECT n+1 FROM seq WHERE n<?)
            INSERT INTO attempts SELECT 'RETURNED_VERIFIED' FROM seq""", (attempts,))
        for model in ("B0_MATCHED_V2", "B1_V2"):
            for arm in ("E0", "E1", "E2"):
                ident = f"{model}__{arm}__s2027"
                con.execute("INSERT INTO runs VALUES(?,'COMPLETE',9,47052)", (ident,))
                con.executemany("INSERT INTO epochs VALUES(?,?,'LAST_COMMITTED')", [(ident, i) for i in range(1, 10)])
    return path


class PredecessorInterface(unittest.TestCase):
    def setUp(self):
        self.fixture_base = ROOT / "tmp/completed_review_fixtures"
        self.root = self.fixture_base / uuid.uuid4().hex
        self.root.mkdir(parents=True)
        (self.root / ".git").mkdir()
        self.guard = extracted(MODULE, "require_predecessor", dict(ROOT=self.root, SEED=2028, TOTAL=282312))

    def tearDown(self):
        gc.collect()  # sqlite's transaction context does not itself close a connection
        resolved = self.root.resolve()
        if resolved == self.fixture_base.resolve() or not resolved.is_relative_to(self.fixture_base.resolve()):
            raise PermissionError("Synthetic cleanup must remain in the isolated fixture directory")
        shutil.rmtree(resolved)

    def test_completed_authorized_v7_is_recognized_without_mutation(self):
        path = ledger(self.root, V7_DB, V7_CAMPAIGN, 198664)
        before = path.read_bytes()
        self.assertIsNone(self.guard())
        self.assertEqual(path.read_bytes(), before)

    def test_active_v7_cannot_fall_back_to_stale_completed_fresh(self):
        ledger(self.root, V7_DB, V7_CAMPAIGN, 198664, complete=False)
        ledger(self.root, FRESH_DB, FRESH_CAMPAIGN, 282312)
        with self.assertRaises(PermissionError):
            self.guard()

    def test_unchanged_completed_fresh_contract_still_works(self):
        ledger(self.root, FRESH_DB, FRESH_CAMPAIGN, 282312)
        self.assertIsNone(self.guard())

    def test_missing_one_v7_verified_attempt_is_rejected(self):
        ledger(self.root, V7_DB, V7_CAMPAIGN, 198663)
        with self.assertRaises(PermissionError):
            self.guard()

    def test_preparation_authority_still_refuses_seed2028(self):
        authority = MODULE.with_name("authority.py")
        guard = extracted(authority, "require_execution_authority", {})
        with self.assertRaisesRegex(PermissionError, "NOT_AUTHORIZED_PREPARATION_ONLY"):
            guard(2028)


if __name__ == "__main__":
    unittest.main(verbosity=2)
