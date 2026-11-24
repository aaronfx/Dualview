from dataclasses import dataclass
@dataclass(frozen=True)
class Line:
    speaker: str
    text: str
    start_ms: int
    end_ms: int

def srt(lines: list[Line]):
    def stamp(ms):
        s,m=divmod(ms,1000); h,s=divmod(s,3600); minute,s=divmod(s,60)
        return f'{h:02}:{minute:02}:{s:02},{m:03}'
    out=[]; end=0
    for i,l in enumerate(lines,1):
        if l.start_ms<end or l.end_ms<=l.start_ms or not l.text.strip(): raise ValueError('invalid subtitle timing')
        out.append(f'{i}\n{stamp(l.start_ms)} --> {stamp(l.end_ms)}\n{l.text}\n'); end=l.end_ms
    return '\n'.join(out)
