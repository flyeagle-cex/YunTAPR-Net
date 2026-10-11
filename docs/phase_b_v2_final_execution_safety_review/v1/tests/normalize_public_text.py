"""LF publication transport; preserve original new-task bytes locally, no old edits."""
from pathlib import Path

OUT=Path(__file__).absolute().parents[1]
originals=OUT/'.local/public_text_originals'
originals.mkdir(exist_ok=True)
count=0
for p in sorted(OUT.rglob('*')):
    if not p.is_file() or '.local' in p.parts or '__pycache__' in p.parts or p.suffix=='.pdf': continue
    raw=p.read_bytes()
    if raw.startswith(b'\xff\xfe'): text=raw.decode('utf-16')
    else: text=raw.decode('utf-8-sig')
    output=text.replace('\r\n','\n').encode('utf-8')
    if output!=raw:
        dest=originals/p.relative_to(OUT); dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists(): dest.write_bytes(raw)
        p.write_bytes(output); count+=1
print('New-task text files normalized:',count)
