from ioabench.suites._vertical import VerticalValidation, VerticalValidator
from .generation import DEFINITION

T361Validation = VerticalValidation

class T361Validator(VerticalValidator):
    def __init__(self) -> None:
        super().__init__(DEFINITION)
