from dataclasses import dataclass
@dataclass(frozen=True)
class Joint:
    name: str
    parent: str | None
    offset: tuple[float,float]
@dataclass(frozen=True)
class Rig:
    joints: tuple[Joint,...]
    roles: dict[str,str]
    def __post_init__(self):
        names=set()
        for j in self.joints:
            if j.name in names or (j.parent is not None and j.parent not in names): raise ValueError('duplicate or unordered parent')
            names.add(j.name)
        if not names or not set(self.roles.values()) <= names: raise ValueError('invalid roles')
    def retarget(self, angles: dict[str,float]) -> dict[str,float]:
        return {self.roles[k]:v for k,v in angles.items() if k in self.roles}
