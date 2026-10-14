from ioabench.suites._vertical import SuiteScore, score_events
from .generation import DEFINITION

T313Score = SuiteScore

class T313Scorer:
    def score(self, events, *, judge_provenance=None):
        return score_events(events, DEFINITION.metrics, judge_provenance=judge_provenance)
