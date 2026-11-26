"""Uniform native skill contracts: schema, preconditions and event witnesses.

Registry covers the native action type vocabulary. Only the explicit live
contracts below can be dispatched here; other skills retain their existing
native planners until a live feasibility adapter is added.
"""
from dataclasses import dataclass
from typing import get_args
from ..scene.schema import ActionType,ActionSpec
from .capabilities import EVENTS,REQUIRED,ALTERNATIVES

SUCCESS={"pick_up":"pick_up","offer_hand":"hand_grab","get_up":"stood_up","act":"act"}
FAILURES={"offer_hand":("help_missed",),"get_up":("help_missed","get_up_failed")}
def registry():
    return {name:{"required":REQUIRED.get(name,[]),"events":EVENTS.get(name,()),
                  "alternatives":ALTERNATIVES.get(name,[]),"live_adapter":name in SUCCESS,
                  "interruptible":name in ("walk_to","run_to","idle","look_at")}
            for name in get_args(ActionType)}

@dataclass(frozen=True)
class Ticket:
    action: ActionSpec
    started: float

def issue_native(controller,t,action):
    action=ActionSpec.model_validate(action)
    if action.type not in SUCCESS or action.character!=controller.cid:
        raise ValueError("no live adapter for action")
    if controller.cur is not None or controller.queue or controller.mode!="grounded":
        raise ValueError("native actor is not available")
    if action.type=="get_up":
        if not controller.lying:
            raise ValueError("get_up requires a prone actor")
    elif controller.lying:
        raise ValueError("standing skill requires upright actor")
    controller.queue.append(action)
    return Ticket(action,t)

def observe_skill_outcome(ticket,e):
    a=ticket.action
    if e.t+1e-9<ticket.started:
        return None
    target=(a.target or "").partition(":")[2]
    if a.type=="offer_hand":
        if e.character!=target:
            return None
        if e.type=="hand_grab" and e.data.get("with")==a.character:
            return "success"
        if e.type=="help_missed" and e.data.get("helper")==a.character:
            return "failure"
        return None
    if e.character!=a.character:
        return None
    if e.type=="action_impossible" or e.type in FAILURES.get(a.type,()):
        return "failure"
    if e.type!=SUCCESS[a.type]:
        return None
    if a.type=="pick_up" and e.data.get("prop")!=target:
        return None
    if a.type=="act" and e.data.get("clip")!=a.clip:
        return None
    if a.type=="get_up" and target and e.data.get("helper")!=target:
        return "failure"
    return "success"
