"""Upper body blending only across compatible native locomotion segments."""
from copy import deepcopy
from math import atan2,sin,cos
def angle_mix(a,b,w):return a+atan2(sin(b-a),cos(b-a))*w

def can_blend_travel(previous_segment,current_segment,previous_pose,current_pose):
    return (previous_segment.kind==current_segment.kind=="loco"
            and previous_segment.frame==current_segment.frame
            and not previous_segment.data.get("carry") and not current_segment.data.get("carry")
            and previous_pose.facing*current_pose.facing>.8)

def blend_travel_upper(previous,incoming,weight):
    if not 0<=weight<=1:raise ValueError("invalid blend weight")
    out=deepcopy(incoming)
    for name in ("spine","chest","neck","head","upper_arm_n","upper_arm_f",
                 "forearm_n","forearm_f","hand_n","hand_f"):
        if name in incoming.local and name in previous.local:
            out.local[name]=angle_mix(previous.local[name],incoming.local[name],weight)
    out.eye=previous.eye+(incoming.eye-previous.eye)*weight
    out.head_facing=previous.head_facing+(incoming.head_facing-previous.head_facing)*weight
    return out
