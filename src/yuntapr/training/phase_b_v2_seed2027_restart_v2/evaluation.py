"""New frozen-real identity envelope, reusing all tested metric calculations."""
from __future__ import annotations
import sqlite3
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.metrics import Evaluator as NumericEvaluator,empty
from .protocol import DEV_N,LIMITS,digest,SEED

class Evaluator(NumericEvaluator):
    def __init__(self,ids: tuple[str,...],source_sha: str,folder):
        if len(ids)!=DEV_N or len(set(ids))!=DEV_N:raise ValueError('FROZEN_REAL_DEVELOPMENT_IDENTITIES')
        self.ids,self.source,self.position,self.poisoned=ids,source_sha,0,False
        path=folder/'exact_scores.sqlite'
        if path.exists():raise PermissionError('NO_EVALUATOR_RESTART_OR_OVERWRITE')
        self.con=sqlite3.connect(path,isolation_level=None)
        self.con.execute('PRAGMA journal_mode=DELETE');self.con.execute('PRAGMA synchronous=FULL')
        page=self.con.execute('PRAGMA page_size').fetchone()[0]
        self.con.execute(f"PRAGMA max_page_count={LIMITS['max_score_database_bytes']//page}")
        self.con.execute('PRAGMA temp_store=FILE');self.con.execute('PRAGMA cache_size=-8192')
        self.con.execute('CREATE TABLE scores(block INTEGER,score BLOB,pos INTEGER,neg INTEGER,PRIMARY KEY(block,score)) WITHOUT ROWID')
        self.stats={-1:empty(),**{b:empty() for b in range(35)}};self.scene_blocks=[]
    def finish(self):
        report=super().finish();report.pop('receipt_sha')
        report['scope']=f'FORMAL_PHASE_B_V2_SEED{SEED}'
        report['scientific_scope']='2024_DEVELOPMENT_EXPLORATORY_M_C_NOT_INDEPENDENT_CONFIRMATION'
        report['scientific_success']='NOT_ESTABLISHED_NO_EFFECT_THRESHOLD_OR_POWER_CLAIM'
        report['receipt_sha']=digest(report);return report
