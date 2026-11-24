from dataclasses import dataclass
from math import isfinite
@dataclass(frozen=True)
class Finding:
    code:str
    time:float
    detail:str
def track_checks(samples,max_speed):
    if max_speed<=0:raise ValueError('speed limit')
    findings=[];prev=None
    for t,x,y in samples:
        if not all(isfinite(v) for v in (t,x,y)):findings.append(Finding('nonfinite',t,'invalid sample'));prev=None;continue
        if prev:
            dt=t-prev[0]
            if dt<=0:findings.append(Finding('time_order',t,'nonmonotonic time'))
            elif ((x-prev[1])**2+(y-prev[2])**2)**.5/dt>max_speed:findings.append(Finding('speed',t,'speed exceeds configured limit'))
        prev=(t,x,y)
    return findings
def repair_loop(initial,inspect,repair,limit=3):
    if limit<0:raise ValueError('limit')
    state=initial;history=[]
    for i in range(limit+1):
        findings=tuple(inspect(state));history.append(findings)
        if not findings:return state,history,True
        if i<limit:state=repair(state,findings)
    return state,history,False
