"""Opt-in original APEX Ink performer using native Skia and FK endpoints."""
import skia
from .ink_geometry import cubic_chain

def draw_ink(canvas,rig,style,pose,joints,project,scale,near,far,alpha,color,*,reflection=False):
    lw=max(.5,style.limb_width*scale)
    def paint(rgb,width,a):
        return skia.Paint(AntiAlias=True,Color=color(rgb,a),Style=skia.Paint.kStroke_Style,
                          StrokeWidth=width,StrokeCap=skia.Paint.kRound_Cap,StrokeJoin=skia.Paint.kRound_Join)
    def stroke(names,rgb,width):
        segments=cubic_chain([project(joints[n]) for n in names])
        path=skia.Path()
        if segments:
            path.moveTo(*segments[0][0])
            for _,a,b,c in segments:path.cubicTo(*a,*b,*c)
        if not reflection:canvas.drawPath(path,paint((9,13,18),width+max(1.,scale*1.4),alpha*.75))
        canvas.drawPath(path,paint(rgb,width,alpha))
    def arm(side,rgb,width):
        names=[f"shoulder_{side}",f"elbow_{side}",f"wrist_{side}"]
        if pose.hands.get(side) in ("point","open"):names.append(f"hand_{side}")
        stroke(names,rgb,width)
    def leg(side,rgb,width):
        stroke([f"hip_{side}",f"knee_{side}",f"ankle_{side}",f"toe_{side}"],rgb,width)
    arm("f",far,lw*.9);leg("f",far,lw*.93)
    stroke(["pelvis","spine_mid","neck_base","neck_top"],near,lw*1.02)
    center,_,_=rig.head_frame(pose)
    x,y=project(center);r=rig.p.head*.55*scale
    if not reflection:canvas.drawCircle(x,y,r,paint((9,13,18),lw*.9+max(1.,scale),alpha*.8))
    canvas.drawCircle(x,y,r,paint(near,lw*.82,alpha))
    leg("n",near,lw);arm("n",near,lw)
