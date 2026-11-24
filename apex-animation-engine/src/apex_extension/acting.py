from math import isfinite
def smooth(t):
    t=max(0,min(1,t));return t*t*t*(10+t*(-15+6*t))
def blend(a,b,t,locked=()):
    if set(a)!=set(b):raise ValueError('pose channels differ')
    w=smooth(t);return {k:a[k] if k in locked else a[k]+(b[k]-a[k])*w for k in a}
def performance_curve(duration,anticipation=.15,recovery=.2,samples=60):
    if not isfinite(duration) or duration<=0 or not 0<anticipation<1 or not 0<recovery<1 or anticipation+recovery>=1 or samples<2:raise ValueError('invalid timing')
    out=[]
    for i in range(samples):
        u=i/(samples-1)
        if u<anticipation:v=-.2*smooth(u/anticipation)
        elif u<1-recovery:v=-.2+1.2*smooth((u-anticipation)/(1-recovery-anticipation))
        else:v=1-smooth((u-1+recovery)/recovery)
        out.append((u*duration,v))
    return out
