"""Verify historical v1 artifact inventories from exact Git bytes, in fixtures."""
from pathlib import Path
import hashlib,json,subprocess,unittest
from unittest.mock import patch

HISTORICAL_FINAL_TEST_COMMIT='299d3f1080840b24db3ba6fe39684a1e6bca530a'

def historical_final_test_fixture(repo, root, proof, module):
    repo=Path(repo);root=Path(root);root.mkdir()
    value=json.loads(Path(proof).read_text(encoding='utf8'));expected=value['implementation_sha256']
    def put(rel,want=None):
        current=(repo/rel).read_bytes()
        if want is None or hashlib.sha256(current).hexdigest()==want:data=current
        else:
            blob=subprocess.check_output(['git','show',HISTORICAL_FINAL_TEST_COMMIT+':'+rel],cwd=repo)
            choices=[blob,blob.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')]
            data=next((x for x in choices if hashlib.sha256(x).hexdigest()==want),None)
            if data is None:raise ValueError('Exact historical Git/worktree bytes do not match pinned SHA: '+rel)
        target=root/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        if want and hashlib.sha256(target.read_bytes()).hexdigest()!=want:raise ValueError('Historical fixture byte identity failed')
    for rel,digest in expected.items():put(rel,digest)
    put(module.PROTOCOL_PATH,value['protocol_sha256'])
    import yaml
    protocol=yaml.safe_load((root/module.PROTOCOL_PATH).read_text(encoding='utf8'))
    put(protocol['identity']['finalfit_run_manifest']['path'])
    if module.implementation_hashes(root)!=expected:raise ValueError('Historical source inventory replay mismatch')
    return root


class HistoricalInventorySuite(unittest.TestSuite):
    def __init__(self,cases,module,fixture):
        super().__init__(cases);self.module=module;self.fixture=fixture
    def run(self,result,debug=False):
        original=self.module.implementation_hashes
        with patch.object(self.module,'implementation_hashes',side_effect=lambda:original(self.fixture)):
            return super().run(result,debug)


def scoped_final_test_suite(suite,module,fixture):
    def flatten(s):
        for item in s:
            if isinstance(item,unittest.TestSuite):yield from flatten(item)
            else:yield item
    cases=list(flatten(suite));prefix='tests.final_test_b0.test_final_test.PreflightArtifactTests.'
    historical=[case for case in cases if case.id().startswith(prefix)]
    remaining=[case for case in cases if not case.id().startswith(prefix)]
    return unittest.TestSuite([*remaining,HistoricalInventorySuite(historical,module,fixture)])
