"""Deterministic affect derived from observed events, not an LLM per frame."""
from ..scene.schema import ActionSpec

def affect_after_event(state,role,e):
    if e.type=="hurt":
        state.fear=min(1.,state.fear+.45*(1-.5*role.courage))
        state.tension=min(1.,state.tension+.35)
    elif e.type=="hit":
        state.tension=min(1.,state.tension+.15)
    elif e.type in ("hand_grab","stood_up","pulled_up","autonomous_reached"):
        state.relief=min(1.,state.relief+.35)
        state.fear=max(0.,state.fear-.2)
    elif e.type=="whiff":
        state.tension=min(1.,state.tension+.1)

def completion_performance(cid,state,role):
    # Keep expressive motion separate from contact physics; a real completed
    # objective can trigger a short native relief or celebration performance.
    if state.fear>.2 or role.objective=="assist" or state.relief>.3:
        return ActionSpec(character=cid,type="act",clip="recover_relief",emotion="relieved",tempo=1.35,intensity=.8)
    return ActionSpec(character=cid,type="act",clip="cheer",emotion="excited",tempo=1.35,intensity=.65)
