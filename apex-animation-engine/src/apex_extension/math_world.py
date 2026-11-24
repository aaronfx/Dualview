from dataclasses import dataclass
from fractions import Fraction
@dataclass(frozen=True)
class LinearEquation:
    a:Fraction
    b:Fraction
    c:Fraction
    def __post_init__(self):
        for k in ('a','b','c'):object.__setattr__(self,k,Fraction(getattr(self,k)))
        if self.a==0:raise ValueError('unique solution required')
    @property
    def solution(self):return (self.c-self.b)/self.a
    def subtract(self,n):return LinearEquation(self.a,self.b-Fraction(n),self.c-Fraction(n))
    def divide(self,n):
        n=Fraction(n)
        if not n:raise ValueError('division by zero')
        return LinearEquation(self.a/n,self.b/n,self.c/n)
def commit(before,after,event,expected_actor,expected_prop):
    if event.get('type')!='verified_contact' or event.get('actor')!=expected_actor or event.get('prop')!=expected_prop:raise ValueError('missing matching contact evidence')
    if before.solution!=after.solution:raise ValueError('not equivalent')
    return after
def native_pair(before,after,**kwargs):
    from apex.scene.math_stage import compile_proven_math_pair
    return compile_proven_math_pair(before,after,**kwargs)
