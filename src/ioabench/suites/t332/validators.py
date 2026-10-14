from ioabench.suites._vertical import VerticalValidation, VerticalValidator
from .generation import DEFINITION

T332Validation = VerticalValidation


class T332Validator(VerticalValidator):
    def __init__(self) -> None:
        super().__init__(DEFINITION)
