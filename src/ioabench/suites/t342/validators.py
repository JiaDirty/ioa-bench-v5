from ioabench.suites._vertical import VerticalValidation, VerticalValidator
from .generation import DEFINITION

T342Validation = VerticalValidation

class T342Validator(VerticalValidator):
    def __init__(self) -> None:
        super().__init__(DEFINITION)
