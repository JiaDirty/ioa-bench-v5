from ioabench.suites._vertical import VerticalValidation, VerticalValidator
from .generation import DEFINITION

T343Validation = VerticalValidation

class T343Validator(VerticalValidator):
    def __init__(self) -> None:
        super().__init__(DEFINITION)
