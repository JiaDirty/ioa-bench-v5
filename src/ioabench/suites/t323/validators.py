from ioabench.suites._vertical import VerticalValidation, VerticalValidator
from .generation import DEFINITION

T323Validation = VerticalValidation

class T323Validator(VerticalValidator):
    def __init__(self) -> None:
        super().__init__(DEFINITION)
