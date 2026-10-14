from ioabench.suites._vertical import SuiteScore, score_events
from .generation import DEFINITION

T321Score = SuiteScore

class T321Scorer:
    def score(self, events, *, judge_provenance=None):
        return score_events(events, DEFINITION.metrics, judge_provenance=judge_provenance)
