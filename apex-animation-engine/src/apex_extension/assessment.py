from dataclasses import dataclass
@dataclass(frozen=True)
class Question:
    id: str
    objective: str
    choices: tuple[str,...]
    correct: int
    explanation: str
    def __post_init__(self):
        if len(self.choices)<2 or not 0<=self.correct<len(self.choices) or not self.explanation: raise ValueError('invalid question')
def grade(questions, answers):
    questions=list(questions)
    if not questions or len({q.id for q in questions})!=len(questions): raise ValueError('invalid assessment')
    return {q.id:{'correct':answers.get(q.id)==q.correct,'explanation':q.explanation} for q in questions}
