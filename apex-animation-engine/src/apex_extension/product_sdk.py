"""Product-neutral contracts; adapters must advertise only verified capabilities."""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol
class Product(str, Enum):
    STUDIO='studio'; EDU='edu'; INTERACTIVE='interactive'; SIMULATION='simulation'; ADS='ads'
@dataclass(frozen=True)
class Capability:
    name: str
    verified: bool = False
    evidence: str = ''
    def __post_init__(self):
        if self.verified and not self.evidence: raise ValueError('verification requires evidence')
class Backend(Protocol):
    def capabilities(self) -> tuple[Capability,...]: ...
    def render(self, project: dict, output: str) -> str: ...
def require(backend: Backend, names: set[str]):
    missing=names-{c.name for c in backend.capabilities() if c.verified}
    if missing: raise ValueError('Unverified capabilities: '+', '.join(sorted(missing)))
