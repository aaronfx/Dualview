"""Isolated tests of staging policy; native tests retain their existing assertions."""
from apex.scene.math_rehearsal import variants
from copy import deepcopy


def test_retreat_preserves_equation_and_dwell():
    raw={'width':1280,'height':720,'environments':[{'room':{'width':2400},'props':[{'id':'transpose_evaluation','position':[150,65],'size':[162,86]}]}], 'scenes':[{'math_transfer':{'actor':'iko','name':'transpose','equation':{'example':True}},'actions':[{'type':'idle','character':'iko','duration':1.9},{'type':'point','character':'iko','target':'prop:transpose_term','duration':.8},{'type':'idle','character':'iko','duration':1.1},{'type':'act','character':'iko','clip':'cheer'}],'shots':[{'camera':{'center':[0,145],'view_height':480}}]}]}
    orig=deepcopy(raw);v=list(variants(raw));assert raw==orig and len(v)==5
    for name,case in v[1:]:
        sc=case['scenes'][0];assert sc['math_transfer']==orig['scenes'][0]['math_transfer'];assert case['environments']==orig['environments'];assert sc['actions'][0]['duration']==1.9;assert sc['actions'][2]['type']=='run_to';assert sc['actions'][2]['target_x']>231
