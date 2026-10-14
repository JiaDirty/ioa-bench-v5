from ioabench.suites._vertical import VerticalValidation, VerticalValidator
from .generation import DEFINITION

T313Validation = VerticalValidation

class T313Validator(VerticalValidator):
    def __init__(self) -> None:
        super().__init__(DEFINITION)
