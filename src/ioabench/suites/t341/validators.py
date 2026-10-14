from ioabench.suites._vertical import VerticalValidation, VerticalValidator
from .generation import DEFINITION

T341Validation = VerticalValidation

class T341Validator(VerticalValidator):
    def __init__(self) -> None:
        super().__init__(DEFINITION)
