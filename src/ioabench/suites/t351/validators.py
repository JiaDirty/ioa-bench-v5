from ioabench.suites._vertical import VerticalValidation, VerticalValidator
from .generation import DEFINITION

T351Validation = VerticalValidation

class T351Validator(VerticalValidator):
    def __init__(self) -> None:
        super().__init__(DEFINITION)
