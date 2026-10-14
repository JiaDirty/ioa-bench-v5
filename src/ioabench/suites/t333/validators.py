from ioabench.suites._vertical import VerticalValidation, VerticalValidator
from .generation import DEFINITION

T333Validation = VerticalValidation


class T333Validator(VerticalValidator):
    def __init__(self) -> None:
        super().__init__(DEFINITION)
