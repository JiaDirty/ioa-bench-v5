from pathlib import Path
from tests.m5_support import assert_mini_dataset
def test_t352_mini_dataset() -> None:
    assert_mini_dataset(Path(__file__).parents[2], "T352")
