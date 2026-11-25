"""One symbolic planner, independently checked with Unified Planning.

Native action execution and observed outcomes remain authoritative.
The bounded native search keeps costs and deterministic tie-breaking; UP
checks causal preconditions/effects, not physical feasibility.
"""
from apex_extension.planning import Action, plan

def checked_plan(initial, goal, operators, budget=256):
    from unified_planning.shortcuts import Problem, Fluent, BoolType, InstantaneousAction, PlanValidator
    from unified_planning.plans import SequentialPlan, ActionInstance
    from unified_planning.engines.results import ValidationResultStatus
    operators = tuple(operators)
    names = {a.name:a for a in operators}
    if len(names) != len(operators):
        raise ValueError("duplicate symbolic action name")
    sequence = plan(initial,goal,operators,budget=budget)
    if sequence is None:
        return None
    facts = sorted(set(initial)|set(goal)|{f for a in operators for f in a.requires|a.adds|a.removes})
    problem = Problem("apex_native_skill_contract")
    fluents = {f:Fluent(f"fact_{i}",BoolType()) for i,f in enumerate(facts)}
    for f in fluents.values():
        problem.add_fluent(f,default_initial_value=False)
    for f in initial:
        problem.set_initial_value(fluents[f],True)
    for f in goal:
        problem.add_goal(fluents[f])
    compiled={}
    for i,a in enumerate(operators):
        op=InstantaneousAction(f"skill_{i}")
        for f in sorted(a.requires):
            op.add_precondition(fluents[f])
        for f in sorted(a.removes-a.adds):
            op.add_effect(fluents[f],False)
        for f in sorted(a.adds):
            op.add_effect(fluents[f],True)
        problem.add_action(op)
        compiled[a.name]=op
    candidate=SequentialPlan([ActionInstance(compiled[n]) for n in sequence])
    with PlanValidator(name="sequential_plan_validator") as validator:
        result=validator.validate(problem,candidate)
    if result.status != ValidationResultStatus.VALID:
        raise RuntimeError(f"Unified Planning rejected native symbolic plan: {result.status}")
    return sequence

def select_native_contract(candidates, relocation):
    """Select a bounded feasible local subgoal, preserving native preference.

    An approach is a subgoal, never a claim that the final destination is met.
    Relocation requires a free hand, acquisition and release in order.
    """
    ops=[]
    payload={}
    initial={"ready","hand_free"}
    for i,(key,action) in enumerate(candidates):
        name=f"candidate_{i}"
        cost=float(i+1)
        payload[name]=(key,action)
        if key[0]=="relocate":
            if relocation is None:
                continue
            held=f"held_{i}"
            ops.append(Action(name,frozenset({"ready","hand_free"}),frozenset({held}),frozenset({"ready","hand_free"}),cost))
            release=f"release_{i}"
            ops.append(Action(release,frozenset({held}),frozenset({"local_subgoal","hand_free"}),frozenset({held}),.1))
        else:
            ops.append(Action(name,frozenset({"ready"}),frozenset({"local_subgoal"}),frozenset({"ready"}),cost))
    seq=checked_plan(initial,{"local_subgoal"},ops)
    if not seq:
        return None
    key,action=payload[seq[0]]
    return key,action,seq
