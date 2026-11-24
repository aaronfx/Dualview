from pathlib import Path
from hashlib import sha256
from dataclasses import dataclass
@dataclass(frozen=True)
class Asset:
    id: str
    path: str
    license: str
    digest: str

def register(root: Path, relative: str, license: str) -> Asset:
    p=(root/relative).resolve()
    if not p.is_relative_to(root.resolve()) or not p.is_file() or not license.strip(): raise ValueError('invalid asset')
    digest=sha256(p.read_bytes()).hexdigest()
    return Asset(digest[:20],relative,license,digest)
