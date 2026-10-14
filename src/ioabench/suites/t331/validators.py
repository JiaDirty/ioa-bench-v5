from ioabench.suites._vertical import VerticalValidation, VerticalValidator
from .generation import DEFINITION

T331Validation = VerticalValidation


class T331Validator(VerticalValidator):
    def __init__(self) -> None:
        super().__init__(DEFINITION)
