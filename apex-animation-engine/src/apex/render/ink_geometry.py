"""Original APEX ink geometry: renderer only; native joints stay exact."""
from math import hypot

def sub(a,b):return (a[0]-b[0],a[1]-b[1])
def add(a,b):return (a[0]+b[0],a[1]+b[1])
def mul(a,k):return (a[0]*k,a[1]*k)
def unit(v):
    n=hypot(*v)
    return mul(v,1/n) if n>1e-9 else (0.,0.)

def cubic_chain(points,tension=.18):
    if not 0<=tension<=.24:raise ValueError("bounded tension")
    p=tuple(tuple(map(float,q)) for q in points)
    if len(p)<2:return ()
    directions,limits=[],[]
    for i,q in enumerate(p):
        before=sub(q,p[i-1]) if i else sub(p[1],q)
        after=sub(p[i+1],q) if i+1<len(p) else before
        u,v=unit(before),unit(after)
        directions.append(unit(add(u,v)) if u[0]*v[0]+u[1]*v[1]>-.5 else (0.,0.))
        limits.append(tension*min(hypot(*before),hypot(*after)))
    return tuple((a,add(a,mul(directions[i],limits[i])),sub(b,mul(directions[i+1],limits[i+1])),b)
                 if hypot(*sub(b,a))>1e-9 else (a,a,b,b) for i,(a,b) in enumerate(zip(p,p[1:])))
