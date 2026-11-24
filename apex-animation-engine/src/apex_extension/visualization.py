from math import isfinite

def polyline(points, width=640,height=360):
    points=list(points)
    if len(points)<2 or width<=0 or height<=0 or not all(isfinite(v) for p in points for v in p): raise ValueError('invalid chart')
    xs,ys=zip(*points); dx=max(xs)-min(xs) or 1; dy=max(ys)-min(ys) or 1
    return [(width*(x-min(xs))/dx,height*(1-(y-min(ys))/dy)) for x,y in points]
