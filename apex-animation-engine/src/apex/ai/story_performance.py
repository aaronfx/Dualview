"""Typed story role -> live tactical state. No authored fight actions or LLM calls."""
from ..motion.acrobatics import BODY_PASS_Z

def observe_encounter(brain,c,t):
    from ..motion.controller import Event
    role=brain.role
    enemy=c.others[role.opponent]
    gap=abs(enemy.s-c.s)
    visible=(enemy.frame is c.frame and enemy.mode=="grounded" and not enemy.lying
             and abs(enemy.z-c.z)<BODY_PASS_Z and not c._path_blocker(c.s,enemy.s))
    near=visible and gap<1.4*c._strike_reach("jab")
    if near and t-brain.last_encounter>3 and t>brain.encounter_until:
        brain.encounter_until=t+(1.0+1.2*role.aggression+.25*role.resolve)
        brain.last_encounter=t
    engaged=visible and t<brain.encounter_until and gap<2.0*c._strike_reach("jab")
    state=("engage" if role.role=="hunter" else "fight_to_escape") if engaged else ("hunt" if role.role=="hunter" else "escape")
    if state!=brain.tactical_state:
        brain.tactical_state=state
        c.emit(Event(t,"actor_intent",c.cid,{"state":state,"role":role.role,"opponent":role.opponent,"gap":gap}))
    # An interception changes the hunter's destination to the opponent,
    # not the exit. Cancel only interruptible travel; respect obstacle skills.
    if role.role=="hunter" and visible and (enemy.s-c.s)*(brain.chase_ceiling-c.s)<0 and gap>c._strike_reach("jab"):
        direction=1 if enemy.s>c.s else -1
        brain.goal=enemy.s-direction*.85*c._strike_reach("jab")
        if c.cur is brain.active_action and c.cur is not None and c.cur.type in ("run_to","walk_to") and not c.queue and (c.cur.target_x-c.s)*direction<0:
            c._next_action(t)
            brain.active_action=None
            brain.pending=None
