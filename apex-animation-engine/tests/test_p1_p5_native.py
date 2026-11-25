"""Must run in the real installed APEX environment, not an isolated mock."""
from apex.scene.schema import CharacterStyle,BackdropSpec
from apex.rig.stickman import StickmanRig,Pose,base_pose
from apex.render.ink_character import draw_ink
from apex.render.skia_renderer import col
import skia
import numpy as np


def test_opt_in_profile_and_legacy_default():
    assert CharacterStyle().visual_profile=='legacy'
    assert BackdropSpec(kind='tower').art_profile=='legacy'
    assert CharacterStyle(visual_profile='apex_ink').visual_profile=='apex_ink'
    assert BackdropSpec(kind='tower',art_profile='industrial_depth').art_profile=='industrial_depth'


def test_native_ink_does_not_mutate_pose_and_has_visible_pixels():
    rig=StickmanRig(); pose=Pose(local=base_pose()); before=pose.copy()
    j=rig.world_joints(pose)
    surface=skia.Surface.MakeRasterN32Premul(480,480); c=surface.getCanvas();c.clear(skia.ColorBLACK)
    draw_ink(c,rig,CharacterStyle(visual_profile='apex_ink'),pose,j,
             lambda p:(240+p[0],300-p[1]),1.,(255,170,60),(170,100,40),1.,col)
    image=surface.makeImageSnapshot().toarray()
    assert np.any(image[:,:,:3])
    assert pose==before and rig.world_joints(pose)==j
