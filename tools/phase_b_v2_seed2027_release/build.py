"""Publish seed2027 code without granting launch or creating an execution ledger."""
from pathlib import Path
import ast,hashlib,json
ROOT=Path(__file__).absolute().parents[2]
SRC=ROOT/'src/yuntapr/experimental/phase_b_v2_multiseed_candidate'
DEST=ROOT/'src/yuntapr/training/phase_b_v2_seed2027'
OUT=ROOT/'docs/phase_b_v2_formal_execution/seed2027_release_v1'
OLD=ROOT/'docs/phase_b_v2_formal_execution/seed2027_v1'
PINS=json.loads((OLD/'prepared_release.json').read_bytes())['source_pins']
def sha(raw):return hashlib.sha256(raw).hexdigest()
def write(path,raw):
    with path.open('xb') as f:f.write(raw)
def change(text,old,new):
    if text.count(old)!=1:raise ValueError('PRECISE_PUBLICATION_ADAPTATION:'+old[:60])
    return text.replace(old,new)
def main():
    DEST.mkdir(exist_ok=False);OUT.mkdir(exist_ok=False)
    reused={}
    for name in ('__init__','analysis','engine','evaluation','checkpoint','quota','recovery','resources','supervisor','worker','control'):
        p=SRC/(name+'.py');raw=p.read_bytes();key=p.relative_to(ROOT).as_posix()
        if sha(raw)!=PINS[key]:raise ValueError('PREPARED_ENGINE_SOURCE_CHANGED')
        reused[key]=sha(raw);text=raw.decode('utf-8')
        if name in ('control','supervisor'):
            text=change(text,'yuntapr.experimental.phase_b_v2_multiseed_candidate.', 'yuntapr.training.phase_b_v2_seed2027.')
        if name=='__init__':text='"""Published seed2027 runner; researcher explicitly withheld launch."""\n'
        if name=='engine':
            text=change(text,"execution_scope='PREPARATION_ONLY_PENDING_NEW_HUMAN_INSTRUCTION'", "execution_scope='SEED2027_RELEASE_PUBLISHED_LAUNCH_WITHHELD'")
        ast.parse(text);write(DEST/(name+'.py'),text.encode())
    # The scientific configuration remains exactly the prepared immutable bytes.
    write(OUT/'config.json',(OLD/'config.json').read_bytes())
    local=OUT/'.local';local.mkdir()
    write(local/'runtime.json',(OLD/'.local/runtime.json').read_bytes())
    write(OUT/'REUSED_SOURCE_PINS.json',(json.dumps(reused,indent=2)+'\n').encode())
    print('SEED2027_RUNTIME_CODE_PUBLISHED_LOCALLY_NO_START')
if __name__=='__main__':main()
