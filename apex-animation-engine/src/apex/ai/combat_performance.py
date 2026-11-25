"""Live, bounded combat performance policy; native combat owns contacts."""
from ..scene.schema import ActionSpec
from ..motion.acrobatics import BODY_PASS_Z
from ..motion.combat import MOVES

def choose_combat_action(brain,c,t):
    if c.lying or not c._upright() or c.carrying:
        return None
    interruptible=c.cur is None or (c.cur is brain.active_action and c.cur.type in ("run_to","walk_to"))
    if not interruptible:
        return None
    enemies=[o for o in c.others.values() if o is not c and not o._gone()
             and o.frame is c.frame and o.mode=="grounded" and not o.lying
             and abs(o.z-c.z)<BODY_PASS_Z and not c._path_blocker(c.s,o.s)
             and (getattr(brain,"ensemble_target",None)==o.cid or
                  getattr(getattr(o,"autonomous_brain",None),"ensemble_target",None)==c.cid or
                  brain.hostile and brain.pursuit==o.cid or
                  getattr(o,"autonomous_brain",None) is not None
                  and o.autonomous_brain.hostile and o.autonomous_brain.pursuit==c.cid)]
    if not enemies:
        return None
    enemy=min(enemies,key=lambda o:(0 if o.cur is not None and o.cur.type=="strike" and o.cur.target=="char:"+c.cid and not o.inter.get("resolved") else 1,abs(o.s-c.s),o.cid))
    gap=abs(enemy.s-c.s)
    direction=1 if enemy.s>=c.s else -1
    incoming=enemy.cur
    if (incoming is not None and incoming.type=="strike" and incoming.target=="char:"+c.cid
            and incoming.move in MOVES and not enemy.inter.get("resolved")
            and gap<=enemy._strike_reach(incoming.move)+20 and t-brain.last_threat>=.45):
        if MOVES[incoming.move]["height"]=="head":
            return "evade_attack",ActionSpec(character=c.cid,type="dodge",dodge="duck"),enemy.cid
        if c.facing==direction and MOVES[incoming.move]["height"]!="legs":
            return "defend",ActionSpec(character=c.cid,type="guard",duration=.42),enemy.cid
        if c.facing==direction and not c._path_blocker(c.s,c.s-direction*.8*c.stand_h):
            return "evade_attack",ActionSpec(character=c.cid,type="dodge",dodge="back"),enemy.cid
    engaged=getattr(brain,"role",None) is not None and brain.tactical_state in ("engage","fight_to_escape")
    cooldown=.48 if engaged else .8
    if getattr(brain,"ensemble_actor",False):
        cooldown=.95-.4*getattr(brain,"ensemble_aggression",.6)
    if (c.queue and not engaged) or t-brain.last_attack<cooldown:
        return None
    # The escape actor only counters a resolved attack, once per attack.
    resolved=bool(incoming is not None and incoming.type=="strike" and enemy.inter.get("resolved"))
    attack_time=getattr(enemy,"cur_t0",-10.0)
    counter=not brain.hostile and resolved and brain.last_threat>=attack_time-.05 and attack_time>brain.countered_at
    if not brain.hostile and not counter and not engaged:
        return None
    if engaged and c.facing!=direction:
        return "face_threat",ActionSpec(character=c.cid,type="turn",face=direction),enemy.cid
    moves=("jab","cross","hook","front_kick","side_kick") if brain.hostile else ("side_kick","cross","front_kick")
    feasible=[move for move in moves if .55*c._strike_reach(move)<=gap<=c._strike_reach(move)]
    if getattr(brain,"role",None) is not None or getattr(brain,"conflict_actor",False):
        # Reserve the swept limb envelope beyond both actors; avoid starting a
        # contact beside a beam when a recoil or follow-through can graze it.
        feasible=[move for move in feasible if not c._path_blocker(c.s,c.s+direction*(c._strike_reach(move)+28),top=c.stand_h+c.shoulder_up+25)
                  and not c._path_blocker(c.s,c.s-direction*35,top=c.stand_h+c.shoulder_up+25)]
    if not feasible:
        return None
    # Preserve variety without selecting a move outside actual reach.
    from ..motion.motion_intelligence import match_attack
    if getattr(c,"style",None) is not None and getattr(c.style,"motion_intelligence",False):
        move=match_attack(feasible,brain.combat_moves,gap,(enemy.v-c.v)*direction,c._strike_reach,MOVES)
    else:
        move=min(feasible,key=lambda name:(brain.combat_moves.count(name),moves.index(name)))
    brain.combat_moves.append(move)
    if counter:
        brain.countered_at=attack_time
    return ("counterattack" if counter or (engaged and not brain.hostile) else "attack"),ActionSpec(character=c.cid,type="strike",
            target="char:"+enemy.cid,move=move,distance=gap,power=1.0 if counter else .85,
            reaction="stagger" if counter else getattr(brain,"ensemble_impact","flinch")),enemy.cid
