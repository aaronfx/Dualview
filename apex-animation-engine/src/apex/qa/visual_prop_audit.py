"""Report suspicious torso intersections with noncolliding visual props.
Warnings are diagnostic, not evidence of physical collision or automatic failure.
"""
from math import cos,sin

def inside_box(point,center,size,angle,margin=3.):
    dx,dy=point[0]-center[0],point[1]-center[1]
    x,y=cos(angle)*dx+sin(angle)*dy,-sin(angle)*dx+cos(angle)*dy
    return abs(x)<size[0]/2-margin and abs(y)<size[1]/2-margin

def inspect_visual_props(runtime,sample_hz=48):
    if not 24<=sample_hz<=120:raise ValueError('sample rate outside 24..120')
    sim=runtime.result or runtime.simulate()
    specs={p.id:p for p in runtime.env.props if not p.collide_characters and p.kind in ('crate','container','toolbox','post')}
    windows={};warnings=[]
    for i in range(int(sim.duration*sample_hz)+1):
        t=i/sample_hz;fs=runtime.evaluate(t);active=set()
        for cid,pose in fs.poses.items():
            j=runtime.rigs[cid].world_joints(pose)
            for pr in fs.props:
                if pr.id not in specs or abs(pr.z-fs.depth.get(cid,0.))>pr.depth/2+8:continue
                if any(inside_box(j[n],pr.pos,pr.size,pr.angle) for n in ('pelvis','spine_mid','neck_base')):
                    key=(cid,pr.id);active.add(key);windows.setdefault(key,t)
        for key,start in list(windows.items()):
            if key not in active:
                if t-start>=.10:warnings.append(dict(actor=key[0],prop=key[1],start=start,end=t,kind='visual_noncolliding_prop_overlap'))
                del windows[key]
    for key,start in windows.items():
        if sim.duration-start>=.10:warnings.append(dict(actor=key[0],prop=key[1],start=start,end=sim.duration,kind='visual_noncolliding_prop_overlap'))
    return warnings
