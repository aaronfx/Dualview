import json
import time

import pytest

from apex.ai.director import PlanningError, StoryDirector, TemplatePlanner
from apex.scene.runtime import SceneRuntime


class FakeProvider:
    name = "fake"

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def complete(self, system, user, max_tokens=8000):
        self.calls.append(user)
        return self.replies.pop(0)


def test_director_validates_and_repairs(gravity_project):
    good = gravity_project.model_dump_json()
    fp = FakeProvider(["not json at all", '{"id": 1}', good])
    proj = StoryDirector(fp, max_repairs=2).plan("a gravity story")
    assert proj.id == gravity_project.id and len(fp.calls) == 3
    assert "INVALID" in fp.calls[1]  # validation errors were fed back


def test_director_gives_up_after_bounded_repairs():
    with pytest.raises(PlanningError):
        StoryDirector(FakeProvider(["{}"] * 3), max_repairs=2).plan("x")


def test_offline_template_planner_produces_simulatable_project():
    proj = TemplatePlanner().plan("Nova walks into the lab, presses the red switch and gravity flips to the left wall.")
    assert proj.characters[0].name == "Nova"
    assert proj.environments[0].switches[0].effect.to == (-1, 0)
    rt = SceneRuntime(proj, proj.scenes[0].id)
    r = rt.simulate()
    assert any(e.type == "impact" and e.data["surface"] == "wall_left" for e in r.events)


def test_api_project_lifecycle_and_render_job(gravity_project, tmp_path, monkeypatch):
    monkeypatch.setenv("APEX_DATA_DIR", str(tmp_path))
    import importlib
    import apex.api.app as appmod
    importlib.reload(appmod)
    from fastapi.testclient import TestClient
    c = TestClient(appmod.app)
    assert c.get("/health").json() == {"status": "ok"}
    bad = gravity_project.model_dump(mode="json")
    bad["scenes"][0]["shots"][1]["start"] = 3.9
    assert c.post("/projects", json=bad).status_code == 422
    r = c.post("/projects", json=gravity_project.model_dump(mode="json"))
    assert r.status_code == 200 and r.json()["scenes"] == ["switch_and_fall"]
    assert c.get("/projects").json()[0]["id"] == gravity_project.id
    job = c.post(f"/projects/{gravity_project.id}/scenes/switch_and_fall/render", json={"scale": 0.2, "qa": False}).json()["job"]
    for _ in range(300):
        st = c.get(f"/jobs/{job}").json()
        if st["status"] in ("done", "failed"):
            break
        time.sleep(0.5)
    assert st["status"] == "done", st.get("error")
    v = c.get(f"/jobs/{job}/video")
    assert v.status_code == 200 and len(v.content) > 10_000
    assert c.post("/projects/nope/scenes/x/render").status_code == 404


def test_template_planner_retimes_shots_from_simulation_and_aligns_frames():
    proj = TemplatePlanner().plan("Nova sprints into the lab, presses the red switch and gravity swings to the left wall.")
    sc = proj.scenes[0]
    assert abs(sc.duration * proj.fps - round(sc.duration * proj.fps)) < 1e-6
    r = SceneRuntime(proj, sc.id).simulate()
    impact = next(e.t for e in r.events if e.type == "impact")
    s3 = sc.shots[-1]
    assert s3.start <= impact <= s3.end  # the landing happens inside the landing shot
