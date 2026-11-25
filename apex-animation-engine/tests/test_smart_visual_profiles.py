from types import SimpleNamespace
from apex.render.ink_geometry import cubic_chain
from apex.motion.performance_profile import blend_travel_upper
from apex.rig.stickman import Pose
from apex.scene.schema import CharacterStyle,BackdropSpec

def test_profile_backward_compatibility():
    assert CharacterStyle().visual_profile=="legacy"
    assert CharacterStyle().performance_profile=="legacy"
    assert BackdropSpec(kind="tower").art_profile=="legacy"

def test_ink_preserves_endpoints():
    p=[(0.,0.),(7.,10.),(11.,3.)]
    segs=cubic_chain(p)
    assert [segs[0][0],segs[0][-1],segs[1][-1]]==p

def test_travel_blend_preserves_incoming_contact_channels():
    old=Pose(root=(0,0),local={"spine":0.,"thigh_n":1.})
    new=Pose(root=(8,12),local={"spine":1.,"thigh_n":2.})
    pose=blend_travel_upper(old,new,.5)
    assert pose.root==new.root and pose.local["thigh_n"]==2.
    assert pose.local["spine"]==.5
    assert new.local["spine"]==1.
