from ioabench.suites._vertical import VerticalValidation, VerticalValidator
from .generation import DEFINITION

T322Validation = VerticalValidation

class T322Validator(VerticalValidator):
    def __init__(self) -> None:
        super().__init__(DEFINITION)
