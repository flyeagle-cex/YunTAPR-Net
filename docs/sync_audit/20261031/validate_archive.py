"""Static, read-only validation of the public archival copies; never import them."""
import ast
import csv
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SECRET = re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{24,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def main():
    records = list(csv.DictReader((HERE / 'archive_manifest.csv').open(encoding='utf-8')))
    checked_python = checked_json = 0
    for record in records:
        path = ROOT / record['path']
        assert path.resolve().is_relative_to((ROOT / 'research_snapshots/20261031_sync').resolve())
        data = path.read_bytes()
        assert len(data) == int(record['archived_bytes']) < 50_000_000, record['path']
        assert hashlib.sha256(data).hexdigest() == record['archived_sha256'], record['path']
        text = data.decode('utf-8')
        assert not SECRET.search(text), record['path']
        assert not re.search(r'(?i)\b[A-Z]:[\\/]', text), record['path']
        if record['source_relative_path'].endswith('.py'):
            ast.parse(text, filename=record['path'])
            checked_python += 1
        if path.suffix == '.json':
            json.loads(text)
            checked_json += 1
    print(json.dumps(dict(status='PASS', archived_files=len(records), python_ast=checked_python,
                          json_parse=checked_json, archive_bytes=sum(int(r['archived_bytes']) for r in records),
                          imported_archives=0, training=0, inference=0, raw_weather_reads=0, final_test_reads=0)))


if __name__ == '__main__':
    main()
