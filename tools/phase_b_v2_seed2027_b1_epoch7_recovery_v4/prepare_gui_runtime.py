"""Register only the fixed venv GUI launcher family, not another scientific runtime."""
from pathlib import Path
import hashlib,json,os,sys
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v4.protocol import LOCAL,digest

def main():
    runtime=json.loads((LOCAL/'runtime.json').read_text(encoding='utf-8'));python=Path(runtime['python'])
    cfg=python.parent.parent/'pyvenv.cfg';raw=cfg.read_bytes()
    homes=[line[7:] for line in raw.decode('utf-8').splitlines() if line.startswith('home = ')]
    if len(homes)!=1:raise ValueError('FROZEN_VENV_HOME')
    paths=dict(wrapper_path=str(python.with_name('pythonw.exe')),native_path=str(Path(homes[0])/'pythonw.exe'))
    row=dict(**paths,binaries={},venv_config_sha256=hashlib.sha256(raw).hexdigest())
    for key,text in paths.items():
        path=Path(text)
        if not path.is_absolute() or '..' in path.parts or '2025' in text or path.name.lower()!='pythonw.exe':raise PermissionError('REGISTERED_GUI_LEXICAL_SCOPE')
        content=path.read_bytes()
        row['binaries'][key]=dict(sha256=hashlib.sha256(content).hexdigest(),bytes=len(content),image_path_key=hashlib.sha256(os.path.normcase(text).encode('utf-8')).hexdigest())
    with (LOCAL/'gui_runtime.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(row,f,indent=2);f.flush();os.fsync(f.fileno())
    print(json.dumps(dict(status='GUI_BOOTSTRAP_RUNTIME_REGISTERED',sha256=digest(row),binaries={k:v['sha256'] for k,v in row['binaries'].items()})))

if __name__=='__main__':main()
