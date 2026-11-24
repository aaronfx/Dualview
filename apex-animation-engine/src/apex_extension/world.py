from dataclasses import dataclass
from math import hypot
@dataclass(frozen=True)
class Object:
    id: str
    x: float
    y: float
    width: float
    height: float
    tags: frozenset[str] = frozenset()
    def __post_init__(self):
        if not self.id or min(self.width,self.height)<=0: raise ValueError('invalid object')
def perceive(objects, x, y, radius):
    if radius<0: raise ValueError('negative radius')
    return sorted((o for o in objects if hypot(max(0,abs(o.x-x)-o.width/2),max(0,abs(o.y-y)-o.height/2))<=radius),key=lambda o:(hypot(o.x-x,o.y-y),o.id))
def affordances(objects):
    return {o.id: tuple(sorted(o.tags & {'climb','push','carry','hazard','goal','cover'})) for o in objects}
def from_project(project, scene_id):
    env=project.environment(project.scene(scene_id).environment)
    from apex.scene.structures import obstacle_bounds
    out=[]
    for o in env.obstacles:
        l,r,b,t=obstacle_bounds(env,o.id)
        out.append(Object(o.id,(l+r)/2,(b+t)/2,r-l,t-b,frozenset({'climb'} if o.kind in ('platform','glyph') else ())))
    for p in env.props:
        out.append(Object(p.id,*p.position[:2],*p.size[:2],frozenset()))
    return tuple(out)
