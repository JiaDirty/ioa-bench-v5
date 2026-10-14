import asyncio
import os

import pytest

from ioabench.models import AIHubMixAdapter, ModelRequest


pytestmark = pytest.mark.integration


@pytest.mark.skipif(not os.environ.get("AIHUBMIX_API_KEY"), reason="AIHUBMIX_API_KEY is required")
def test_live_model_resolution_and_two_session_requests() -> None:
    adapter = AIHubMixAdapter()
    profile = asyncio.run(adapter.resolve("deepseek-v4.1-flash"))
    first = asyncio.run(adapter.generate(profile, ModelRequest(messages=({"role": "user", "content": "live-alpha"},), parameters=profile.default_parameters)))
    second = asyncio.run(adapter.generate(profile, ModelRequest(messages=({"role": "user", "content": "live-beta"},), parameters=profile.default_parameters)))

    assert profile.model_id == "deepseek-v4.1-flash"
    assert first.model_id == second.model_id == profile.model_id
