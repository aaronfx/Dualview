"""Original APEX ink geometry. Renderer-only; never edits a joint or Pose."""
from __future__ import annotations
from math import hypot


def _sub(a, b): return (a[0]-b[0], a[1]-b[1])
def _add(a, b): return (a[0]+b[0], a[1]+b[1])
def _mul(a, k): return (a[0]*k, a[1]*k)


def _unit(v):
    n = hypot(*v)
    return _mul(v, 1/n) if n > 1e-9 else (0.0, 0.0)


def cubic_chain(points, tension=0.18):
    """Interpolating cubics, with short bounded handles; endpoints and joints exact.

    A near-180-degree fold gets zero tangents rather than a looping curve.
    Curves are presentation only; contact envelopes still need pixel review.
    """
    if not 0 <= tension <= .24:
        raise ValueError('tension outside bounded range')
    p = tuple(tuple(map(float, q)) for q in points)
    if len(p) < 2:
        return ()
    directions, limits = [], []
    for i, q in enumerate(p):
        before = _sub(q, p[i-1]) if i else _sub(p[1], q)
        after = _sub(p[i+1], q) if i+1 < len(p) else before
        u, v = _unit(before), _unit(after)
        dot = u[0]*v[0]+u[1]*v[1]
        directions.append(_unit(_add(u,v)) if dot > -.5 else (0.,0.))
        limits.append(tension*min(hypot(*before),hypot(*after)))
    out = []
    for i, (a,b) in enumerate(zip(p,p[1:])):
        if hypot(*_sub(b,a)) < 1e-9:
            out.append((a,a,b,b)); continue
        out.append((a,_add(a,_mul(directions[i],limits[i])),
                    _sub(b,_mul(directions[i+1],limits[i+1])),b))
    return tuple(out)
