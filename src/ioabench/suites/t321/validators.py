from ioabench.suites._vertical import VerticalValidation, VerticalValidator
from .generation import DEFINITION

T321Validation = VerticalValidation

class T321Validator(VerticalValidator):
    def __init__(self) -> None:
        super().__init__(DEFINITION)
