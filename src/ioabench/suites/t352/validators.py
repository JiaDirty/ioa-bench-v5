from ioabench.suites._vertical import VerticalValidation, VerticalValidator
from .generation import DEFINITION

T352Validation = VerticalValidation

class T352Validator(VerticalValidator):
    def __init__(self) -> None:
        super().__init__(DEFINITION)
