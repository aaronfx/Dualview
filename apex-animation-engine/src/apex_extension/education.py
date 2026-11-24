from dataclasses import dataclass
@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    source: str
    reviewer: str=''
    approved: bool=False
@dataclass(frozen=True)
class Lesson:
    subject: str
    objectives: tuple[str,...]
    claims: tuple[Claim,...]
    def validate_release(self):
        if not self.objectives or not self.claims: raise ValueError('missing lesson content')
        for c in self.claims:
            if not all((c.text.strip(),c.source.strip(),c.reviewer.strip(),c.approved)): raise ValueError('unreviewed claim '+c.id)
