"""Compare real Git identities/ancestry, reject corruption, and forbid process creation."""
import hashlib,json,subprocess,unittest,uuid,zlib
from pathlib import Path
from unittest.mock import patch
import operate
from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2 import metadata_process as m,protocol as p
class Tests(unittest.TestCase):
    def test_actual_HEAD_matches_original_Git(self):
        for root in m.REPOSITORIES.values():
            if not (root/'.git/HEAD').exists():continue
            expected=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(m.head(root)+'\n',expected)
    def test_real_ancestry_matches_original_Git(self):
        for root,relative in ((p.PREVIOUS_ROOT,'docs/formal_recovery/seed2027_b0_e1_epoch1_v1/release.json'),(p.ZERO_ROOT,'docs/formal_recovery/seed2027_b1_e1_epoch6_v1/release.json')):
            source=json.loads((root/relative).read_bytes())['source_commit'];head=m.head(root)
            for a,b in ((source,head),(head,source)):
                expected=subprocess.run(['git','merge-base','--is-ancestor',a,b],cwd=root,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW).returncode
                actual=m.evaluate(['git','merge-base','--is-ancestor',a,b],{'cwd':root})[0]
                # Unsupported packed/shallow negative paths fail closed (128), never pass.
                self.assertEqual(actual==0,expected==0)
    def test_metadata_adapter_does_not_create_any_child(self):
        root=p.LIVE_ROOT;expected=m.head(root)
        with patch.object(subprocess,'Popen',side_effect=AssertionError('NO_CHILD_PROCESS')):
            with m.no_console_git():
                self.assertEqual(subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),expected)
                with self.assertRaises(PermissionError):subprocess.run(['git','reset','--hard'],cwd=root)
        with m.no_console_git():
            self.assertEqual(subprocess.run(['git','merge-base','--is-ancestor','0'*40,'0'*40],cwd=root,capture_output=True).returncode,128)
    def test_unsupported_scope_and_process_options_fail(self):
        for args,kwargs in ((['python','x'],{'cwd':m.ROOT}),(['git','status'],{'cwd':m.ROOT}),(['git','rev-parse','HEAD'],{'cwd':m.ROOT.parent}),(['git','rev-parse','HEAD'],{'cwd':m.ROOT,'shell':True}),(['git','rev-parse','HEAD'],{'cwd':m.ROOT,'creationflags':0x01000000})):
            with self.assertRaises(PermissionError):m.evaluate(args,kwargs)
    def test_corrupted_commit_never_passes(self):
        root=p.LOCAL/('artificial_git_'+uuid.uuid4().hex);(root/'.git/objects').mkdir(parents=True)
        body=b'tree '+b'1'*40+b'\n\nartificial only\n';decoded=b'commit '+str(len(body)).encode()+b'\0'+body
        sha=hashlib.sha1(decoded).hexdigest();obj=root/'.git/objects'/sha[:2]/sha[2:];obj.parent.mkdir()
        obj.write_bytes(zlib.compress(decoded));self.assertEqual(m.parents(root,sha),[])
        obj.write_bytes(zlib.compress(decoded+b'x'))
        with self.assertRaises(ValueError):m.parents(root,sha)
if __name__=='__main__':unittest.main(verbosity=2)
