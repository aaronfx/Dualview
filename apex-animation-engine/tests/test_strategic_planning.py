from apex.ai.strategic_planning import checked_plan
from apex_extension.planning import Action

def op(name,requires,adds,removes=(),cost=1):
    return Action(name,frozenset(requires),frozenset(adds),frozenset(removes),cost)

def test_multi_step_contract_and_alternative():
    ops=[op("pick_tool",["free"],["tool"],["free"]),
         op("release_barrier",["tool"],["clear"]),
         op("cross",["clear"],["destination"]),
         op("jump",["jump_possible"],["destination"],cost=1)]
    assert checked_plan({"free"},{"destination"},ops)==("pick_tool","release_barrier","cross")
    assert checked_plan({"free","jump_possible"},{"destination"},ops)==("jump",)
    assert checked_plan(set(),{"destination"},ops) is None

def test_relocation_requires_pickup_and_release():
    ops=[op("pickup",["free","available"],["held"],["free","available"]),
         op("place",["held","safe_area"],["clear","free"],["held"])]
    assert checked_plan({"free","available","safe_area"},{"clear"},ops)==("pickup","place")
    assert checked_plan({"free","available"},{"clear"},ops) is None
