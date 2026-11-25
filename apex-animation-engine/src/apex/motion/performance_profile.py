"""Opt-in continuity policy over native APEX Pose, not an alternate motion engine."""
from __future__ import annotations
from copy import deepcopy
from math import atan2, sin, cos


def angle_mix(a, b, w):
    return a + atan2(sin(b-a),cos(b-a))*w


def blend_travel_upper(previous, incoming, weight):
    """Blend only non-contact upper-body channels between two locomotion segments.

    Incoming root, body frame, facing, pelvis twist, legs, IK stretch and
    all native contact geometry stay authoritative. Only used if neither
    segment is carrying and both are locomotion in the same support frame.
    """
    if not 0 <= weight <= 1: raise ValueError('blend weight outside [0,1]')
    out=deepcopy(incoming)
    for name in ('spine','chest','neck','head','upper_arm_n','upper_arm_f',
                 'forearm_n','forearm_f','hand_n','hand_f'):
        if name in incoming.local and name in previous.local:
            out.local[name]=angle_mix(previous.local[name],incoming.local[name],weight)
    # Do not blend torso twist: it shifts native shoulder positions. Preserve
    # the incoming leg/hip chain and the animator's subsequent contact passes.
    out.eye=previous.eye+(incoming.eye-previous.eye)*weight
    out.head_facing=previous.head_facing+(incoming.head_facing-previous.head_facing)*weight
    return out


def can_blend_travel(previous_segment, current_segment, previous_pose, current_pose):
    return (previous_segment.kind==current_segment.kind=='loco'
            and previous_segment.frame==current_segment.frame
            and not previous_segment.data.get('carry')
            and not current_segment.data.get('carry')
            and previous_pose.facing*current_pose.facing>.8)
