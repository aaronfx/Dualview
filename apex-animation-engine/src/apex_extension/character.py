from dataclasses import dataclass, field
from collections import OrderedDict
@dataclass
class Affect:
    valence: float=0.0
    arousal: float=0.0
    def update(self, reward, threat, dt):
        if dt<0: raise ValueError('negative dt')
        a=1-__import__('math').exp(-dt*3)
        self.valence=max(-1,min(1,self.valence+a*(max(-1,min(1,reward))-self.valence)))
        self.arousal=max(0,min(1,self.arousal+a*(max(0,min(1,threat))-self.arousal)))
        return self.valence,self.arousal
@dataclass
class Experience:
    capacity:int=128
    outcomes:OrderedDict=field(default_factory=OrderedDict)
    def __post_init__(self):
        if self.capacity<1: raise ValueError('capacity')
    def record(self,target,tactic,success):
        k=(target,tactic); wins,losses=self.outcomes.pop(k,(0,0)); self.outcomes[k]=(min(255,wins+int(success)),min(255,losses+int(not success)))
        while len(self.outcomes)>self.capacity:self.outcomes.popitem(last=False)
    def confidence(self,target,tactic):
        w,l=self.outcomes.get((target,tactic),(0,0));return (w+1)/(w+l+2)
def native_brain(personality):
    from apex.ai.character_brain import CharacterBrain
    return CharacterBrain(personality)
