from ioabench.suites._vertical import VerticalValidation, VerticalValidator
from .generation import DEFINITION

T353Validation = VerticalValidation

class T353Validator(VerticalValidator):
    def __init__(self) -> None:
        super().__init__(DEFINITION)
