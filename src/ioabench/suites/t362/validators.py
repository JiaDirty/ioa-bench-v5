from ioabench.suites._vertical import VerticalValidation, VerticalValidator
from .generation import DEFINITION

T362Validation = VerticalValidation

class T362Validator(VerticalValidator):
    def __init__(self) -> None:
        super().__init__(DEFINITION)
