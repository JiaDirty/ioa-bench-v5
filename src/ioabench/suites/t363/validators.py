from ioabench.suites._vertical import VerticalValidation, VerticalValidator
from .generation import DEFINITION

T363Validation = VerticalValidation

class T363Validator(VerticalValidator):
    def __init__(self) -> None:
        super().__init__(DEFINITION)
