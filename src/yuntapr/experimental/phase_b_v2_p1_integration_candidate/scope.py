"""Owned artificial storage. Lexical rejection always precedes path I/O."""
from __future__ import annotations
import os
from pathlib import Path
import re
import uuid
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle

ROOT = Path(__file__).absolute().parents[4]
OUT = ROOT / 'docs/phase_b_v2_p1_integration_remediation/v1'
LOCAL = OUT / '.local'


def lexical(path: Path, root: Path) -> None:
    # Exact pathlib types avoid arbitrary __fspath__/resolve/stat side effects.
    if type(path) is not type(root):
        raise PermissionError('Native Path required before any filesystem operation')
    raw = str(path).replace('\\', '/')
    if ('2025' in raw or '..' in raw.split('/') or not path.is_absolute()
            or not path.is_relative_to(root) or ':' in raw[2:]):
        raise PermissionError('Artificial registered scope only')


class Workspace:
    """Retain no-delete directory handles; never resolve a supplied path."""
    def __init__(self):
        self.handles: list[ReadHandle] = []
        self.key = uuid.uuid4().hex
        try:
            for path in (ROOT, ROOT/'docs', OUT.parent, OUT):
                self._hold(path)
            LOCAL.mkdir(exist_ok=True)
            self._hold(LOCAL)
            self.root = LOCAL / ('checkpoint_' + self.key)
            lexical(self.root, LOCAL)
            self.root.mkdir(exist_ok=False)
            self._hold(self.root)
        except BaseException:
            self.close()
            raise

    def _hold(self, path: Path) -> None:
        lexical(path, ROOT)
        h = ReadHandle(str(path), directory=True)
        if os.path.normcase(h.final_path) != os.path.normcase(str(path)):
            h.close()
            raise PermissionError('Directory object redirected')
        self.handles.append(h)

    def file(self, name: str) -> Path:
        if type(name) is not str or re.fullmatch(r'[A-Za-z0-9_.-]{1,96}', name) is None:
            raise PermissionError('Simple artificial filename required')
        path = self.root/name
        lexical(path, self.root)
        return path

    def close(self) -> None:
        for h in reversed(self.handles):
            h.close()
        self.handles.clear()

    def __enter__(self): return self
    def __exit__(self, *args): self.close()
