"""Reference-triad story contract: Math, Arcade and long-form cinematic action."""
from types import SimpleNamespace as NS
import pytest
from pydantic import ValidationError

from apex.scene.creative import CreativePlan
from apex.qa.creative import audit_creative_plan


def I(v): return {"op": "int", "value": v}
def V(v): return {"op": "var", "value": v}
def E(op, a, b): return {"op": op, "args": [a, b]}


def beat(id, scene, t, kind, *, actor="iko", causes=None, **kw):
    return dict(id=id, scene=scene, t=t, kind=kind, actor=actor,
                intent=f"{id} changes the world", causes=causes or [], **kw)


def project(profile, beats, *, scenes=None, initial=None):
    plan = CreativePlan.model_validate(dict(profile=profile, premise="Physical rules tell an original story",
                                            initial_state=initial or {}, beats=beats))
    if scenes is None:
        scenes = [NS(id="s", duration=10.0, music=NS(bpm=120.0, offset=0.0),
                     placements=[NS(character="iko"), NS(character="pell")])]
    return NS(creative_plan=plan, scenes=scenes, fps=24)


def checks(project, evidence=None):
    return {r.name: r for r in audit_creative_plan(project, evidence)}


def test_math_reference_requires_true_equation_and_payoff():
    bs = [beat("setup", "s", 0, "setup", effects={"lock": "closed"}),
          beat("algebra", "s", 1, "response", causes=["setup"], requires={"lock": "closed"},
               math={"before": E("eq", E("add", V("x"), I(2)), I(5)), "after": E("eq", V("x"), I(3))},
               effects={"lock": "opened"}),
          beat("finish", "s", 2, "payoff", causes=["algebra"], requires={"lock": "opened"})]
    c = checks(project("math", bs))
    assert all(x.status == "PASS" for x in c.values() if x.name != "creative_human_artistic_review" and
               x.name != "creative_simulation_evidence")
    assert c["creative_human_artistic_review"].status == "SKIP"
    assert c["creative_simulation_evidence"].status == "SKIP"


def test_invalid_math_and_state_are_rejected():
    bs = [beat("start", "s", 0, "setup", effects={"gate": "locked"}),
          beat("fake", "s", 1, "response", causes=["start"], requires={"gate": "open"},
               math={"before": E("eq", E("add", V("x"), I(2)), I(5)), "after": E("eq", V("x"), I(4))}),
          beat("end", "s", 2, "payoff", causes=["fake"])]
    c = checks(project("math", bs))
    assert c["creative_math_truth"].status == "FAIL"
    assert c["creative_world_state"].status == "FAIL"


def test_arcade_reference_uses_actual_film_clock_not_story_clock():
    bs = [beat("start", "s", 0, "setup"),
          beat("orb", "s", 0.3, "response", causes=["start"], on_beat=True, film_t=0.5),
          beat("exit", "s", 0.9, "payoff", causes=["orb"], on_beat=True, film_t=1.0)]
    c = checks(project("arcade", bs))
    assert c["creative_music_sync"].status == "PASS"
    assert c["creative_reference_coverage"].status == "PASS"
    bs[2]["film_t"] = 1.2
    assert checks(project("arcade", bs))["creative_music_sync"].status == "FAIL"


def test_epic_reference_requires_actors_multiple_scenes_reversal_and_payoff():
    sc = [NS(id="tower", duration=10.0, music=None, placements=[NS(character="iko"), NS(character="pell")]),
          NS(id="summit", duration=10.0, music=None, placements=[NS(character="iko"), NS(character="pell")])]
    bs = [beat("theft", "tower", 0, "setup", actor="pell", effects={"core": "stolen"}),
          beat("defeat", "tower", 5, "reversal", causes=["theft"], requires={"core": "stolen"}),
          beat("restore", "summit", 4, "payoff", causes=["defeat"], actor="iko",
               effects={"core": "restored"})]
    c = checks(project("epic", bs, scenes=sc))
    assert c["creative_reference_coverage"].status == "PASS"
    assert c["creative_causality"].status == "PASS"


def test_hybrid_joins_three_capabilities_in_one_original_story():
    sc = [NS(id="math", duration=6.0, music=None, placements=[NS(character="iko")]),
          NS(id="dash", duration=6.0, music=NS(bpm=120.0, offset=0), placements=[NS(character="iko")]),
          NS(id="final", duration=6.0, music=None, placements=[NS(character="iko"), NS(character="pell")])]
    bs = [beat("a", "math", 0, "setup"),
          beat("b", "math", 1, "discovery", causes=["a"], math={"before": E("add", I(2), I(2)), "after": I(4)}),
          beat("c", "dash", 0.5, "obstacle", causes=["b"], on_beat=True, film_t=0.5),
          beat("d", "dash", 1.0, "response", causes=["c"], on_beat=True, film_t=1.0),
          beat("e", "final", 1.0, "reversal", actor="pell", causes=["d"]),
          beat("f", "final", 3.0, "payoff", causes=["e"])]
    c = checks(project("hybrid", bs, scenes=sc))
    assert c["creative_reference_coverage"].status == "PASS"
    assert all(c[k].status == "PASS" for k in
               ("creative_scene_integrity", "creative_causality", "creative_math_truth", "creative_music_sync"))


def test_simulation_event_evidence_fails_if_physical_action_did_not_happen():
    bs = [beat("begin", "s", 0, "setup"),
          beat("punch", "s", 1.0, "response", causes=["begin"], proof_event="hit@iko"),
          beat("win", "s", 2.0, "payoff", causes=["punch"])]
    p = project("epic", bs, scenes=[
        NS(id="s", duration=10.0, music=None, placements=[NS(character="iko"), NS(character="pell")]),
        NS(id="s2", duration=10.0, music=None, placements=[NS(character="iko"), NS(character="pell")])])
    assert checks(p)["creative_simulation_evidence"].status == "SKIP"
    wrong = {"s": [NS(type="whiff", character="iko", t=1, data={})]}
    good = {"s": [NS(type="hit", character="iko", t=1.1, data={})]}
    assert checks(p, wrong)["creative_simulation_evidence"].status == "FAIL"
    assert checks(p, good)["creative_simulation_evidence"].status == "PASS"


def test_rejects_invalid_schema_and_causal_cycles():
    with pytest.raises(ValidationError):
        project("math", [beat("a", "s", 0, "setup", on_beat=True)])
    bs = [beat("a", "s", 0, "setup", causes=["b"]),
          beat("b", "s", 1, "payoff", causes=["a"])]
    assert checks(project("math", bs))["creative_causality"].status == "FAIL"


def test_missing_actor_and_wrong_scene_time_fail():
    bs = [beat("a", "s", 1, "setup", actor="absent"),
          beat("b", "s", 11, "payoff", causes=["a"])]
    assert checks(project("epic", bs))["creative_scene_integrity"].status == "FAIL"
