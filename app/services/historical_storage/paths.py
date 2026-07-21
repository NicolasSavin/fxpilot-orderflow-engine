from __future__ import annotations
import os, re, tempfile
from pathlib import Path

COMPONENT_RE = re.compile(r'[^A-Za-z0-9._-]+')

def data_root() -> Path:
    return Path(os.getenv('FXPILOT_ORDERFLOW_DATA_DIR', './data')).expanduser().resolve()

def ensure_dirs(root: Path | None = None) -> dict[str, Path]:
    root = (root or data_root()).resolve()
    dirs = {name: root/name for name in ['raw','normalized','catalogs','manifests','mock','quarantine']}
    root.mkdir(parents=True, exist_ok=True)
    for d in dirs.values(): d.mkdir(parents=True, exist_ok=True)
    return dirs

def safe_component(value: str) -> str:
    cleaned = COMPONENT_RE.sub('-', str(value).strip()).strip('.-_')
    return cleaned or 'unknown'

def assert_within(path: Path, root: Path) -> Path:
    p = path.expanduser().resolve(); r = root.expanduser().resolve()
    if p != r and r not in p.parents:
        raise ValueError(f'path traversal or outside configured root rejected: {path}')
    return p

def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try: os.unlink(tmp)
        except FileNotFoundError: pass
        raise
