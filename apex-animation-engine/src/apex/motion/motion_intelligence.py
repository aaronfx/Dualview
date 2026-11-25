"""CPU-only, native-rig adaptations of feature matching and critically damped inertialization.

No imported research weights, mocap data or third-party source.
References: theorangeduck.com/page/spring-roll-call and Motion-Matching.
"""
import math
FREE_UPPER=("spine","chest","head","upper_arm_n","upper_arm_f","forearm_n","forearm_f")

def decay_offset(x,v,t,half_life):
    """Critically damped offset; preserve the boundary value and derivative."""
    k=math.log(2)/half_life
    return (x+(v+k*x)*t)*math.exp(-k*t)

def apply_intent(pose,intent,run,phase):
    if intent=="neutral":
        return
    L=pose.local
    strength=.45+.55*run
    if intent=="hunter":
        L["spine"]+=.13*strength
        L["head"]-=.11*strength
        for side in ("n","f"):
            L["forearm_"+side]+=.28*strength
        pose.eye=max(.65,pose.eye-.18*strength)
    elif intent=="fugitive":
        L["spine"]+=.07*strength
        L["head"]+=.10*strength*phase
        pose.eye=min(2.,pose.eye+.25*strength)

def match_attack(feasible,history,gap,relative_speed,reach,moves):
    """Rank native contact-feasible skills by predicted range and novelty.
    This is skill-feature matching, not a mocap frame database.
    """
    def cost(name):
        contact=moves[name]["t_c"]
        predicted=gap+relative_speed*contact
        r=reach(name)
        error=abs(predicted-.82*r)/max(r,1)
        repetition=history[-3:].count(name)*.65
        return error+repetition+.25*contact
    return min(feasible,key=cost)
