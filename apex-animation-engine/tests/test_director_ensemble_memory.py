from types import SimpleNamespace as S
import pytest
from apex.ai.ensemble_planner import Task,topological
from apex.ai.production_memory import ProductionMemory
from apex.ai.character_brain import Perception,Intent
def task(id,after=()):
    return Task(id=id,actor="iko",after=list(after),proof="notice@"+id,alternatives=[[{"type":"idle","character":"iko","duration":1}]])
def test_dependencies_and_cycle():
    assert [x.id for x in topological([task("b",["a"]),task("a")])]==["a","b"]
    with pytest.raises(ValueError,match="cyclic"):topological([task("a",["b"]),task("b",["a"])])
    with pytest.raises(ValueError,match="unknown"):topological([task("a",["b"])])
def test_actor_task_cannot_control_other_actor():
    with pytest.raises(ValueError):Task(id="a",actor="iko",proof="notice@iko",alternatives=[[{"type":"idle","character":"pell","duration":1}]])
def test_memory_deduplication_and_approval(tmp_path):
    m=ProductionMemory(tmp_path/"memory.db")
    ev=S(t=1,type="push_fail",character="iko",data={"prop":"box"})
    c=S(records=[S(pos=(1,2),vel=(0,0))],violation=None,carrying=None)
    sim=S(events=[ev],controllers={"iko":c})
    h=m.record("p","s",sim);assert m.record("p","s",sim)==h
    assert len(m.recall("p"))==1 and m.recall("other")==[]
    assert m.actor_brain("p","iko").failed_attempts[("box",Intent.APPROACH)]==1
    assert not m.approved("p",h)
    m.approve("p",h,"owner review");assert m.approved("p",h)
