"""P1: APEX's original minimalist performer; native Skia / native FK endpoints."""
from __future__ import annotations
import skia
from .ink_geometry import cubic_chain


def draw_ink(canvas, rig, style, pose, joints, project, scale, near, far, alpha, color, *, reflection=False):
    """Use the same world joints and projection as SkiaRenderer._character.

    A hollow head, one continuous silhouette, no visor/scarf; original APEX
    palettes remain configurable. All existing rig, IK, depth and physics are
    unchanged. The legacy renderer still handles its own style.
    """
    lw = max(.5, style.limb_width * scale)
    j = joints
    def path_for(names):
        segments = cubic_chain([project(j[n]) for n in names])
        p = skia.Path()
        if segments:
            p.moveTo(*segments[0][0])
            for _, a,b,c in segments:
                p.cubicTo(a[0],a[1],b[0],b[1],c[0],c[1])
        return p
    def paint(rgb, width, a):
        return skia.Paint(AntiAlias=True, Color=color(rgb,a),
                          Style=skia.Paint.kStroke_Style, StrokeWidth=width,
                          StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)
    def stroke(names, rgb, width):
        p = path_for(names)
        if not reflection:
            canvas.drawPath(p, paint((9,13,18),width+max(1.,scale*1.4),alpha*.75))
        canvas.drawPath(p,paint(rgb,width,alpha))
    def arm(s, rgb, width):
        # Preserve the wrist contact for fists; native pointing/grasping uses fingertip.
        names = [f'shoulder_{s}', f'elbow_{s}', f'wrist_{s}']
        if pose.hands.get(s) in ('point','open'):
            names.append(f'hand_{s}')
        stroke(names,rgb,width)
    def leg(s,rgb,width):
        stroke([f'hip_{s}',f'knee_{s}',f'ankle_{s}',f'toe_{s}'],rgb,width)
    arm('f',far,lw*.9); leg('f',far,lw*.93)
    stroke(['pelvis','spine_mid','neck_base','neck_top'],near,lw*1.02)
    center, _, _ = rig.head_frame(pose)
    x,y = project(center)
    # Match existing rig head envelope; ring remains transparent.
    radius = rig.p.head*.55*scale
    if not reflection:
        canvas.drawCircle(x,y,radius,paint((9,13,18),lw*.90+max(1.,scale),alpha*.8))
    canvas.drawCircle(x,y,radius,paint(near,lw*.82,alpha))
    leg('n',near,lw); arm('n',near,lw)
