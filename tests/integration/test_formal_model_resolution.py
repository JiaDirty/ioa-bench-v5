import asyncio
import os

import pytest

from ioabench.models import AIHubMixAdapter


pytestmark = pytest.mark.integration


@pytest.mark.skipif(not os.environ.get("AIHUBMIX_API_KEY"), reason="AIHUBMIX_API_KEY is required")
def test_formal_model_resolution_uses_exact_requested_id() -> None:
    profile = asyncio.run(AIHubMixAdapter().resolve("deepseek-v4.1-flash"))
    assert profile.provider == "aihubmix"
    assert profile.model_id == "deepseek-v4.1-flash"
    assert isinstance(profile.capabilities, dict)
    assert isinstance(profile.default_parameters, dict)
