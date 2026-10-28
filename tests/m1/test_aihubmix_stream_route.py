"""The existing router binds retained stream bytes to its actual attempt file."""
import asyncio
import json
from pathlib import Path
import runpy

import pytest

from ioabench.v5.ai_generation.auxiliary_runtime import (
    AuxiliaryContract, AuxiliaryRouter, RequestUnresolved,
)


STREAM = runpy.run_path(str(Path(__file__).with_name("test_aihubmix_stream_evidence.py")))


@pytest.mark.parametrize("returncode,defect", [(56, None), (56, "done"), (0, None)])
def test_router_routes_stream_evidence_without_resending_or_exposing_local_metadata(
        monkeypatch, tmp_path, returncode, defect):
    port, profile, request, calls, data, headers = STREAM["stream_call"](
        monkeypatch, tmp_path, returncode=returncode, defect=defect)
    catalog = [{"model_id": profile.model_id, "developer_id": 1}]
    contract = AuxiliaryContract(profile, request.parameters, catalog[0], "offline-stream-fixture")
    router = AuxiliaryRouter(port, [contract], catalog, tmp_path / "router")
    directory = router.directory / "stream-case"
    attempt = directory / "attempt-001.json"

    if defect:
        with pytest.raises(RequestUnresolved) as failed:
            asyncio.run(router.invoke("GENERATOR", "stream-case", request))
        assert failed.value.transport_metadata["http_status"] == 200
        assert failed.value.transport_metadata["stream_evidence"]["sse_path"] == str(attempt.with_suffix('.sse'))
        saved = json.loads(attempt.read_text(encoding="utf-8"))
        assert saved["status"] == saved["category"] == "REQUEST_UNRESOLVED"
        transport = saved["transport_metadata"]
        assert not (directory / "RESPONSE.json").exists()
        with pytest.raises(RequestUnresolved):
            asyncio.run(router.invoke("GENERATOR", "stream-case", request))
    else:
        response = asyncio.run(router.invoke("GENERATOR", "stream-case", request))
        assert response.text == "{}" and response.finish_reason == "stop"
        saved = json.loads(attempt.read_text(encoding="utf-8"))
        assert saved["status"] == "SUCCEEDED"
        transport = saved["response"]["provider_metadata"]["transport_metadata"]
        replayed = asyncio.run(router.invoke("GENERATOR", "stream-case", request))
        assert replayed == response

    assert len(calls) == 1
    assert len(list(directory.glob("attempt-*.json"))) == 1
    assert not any(path.exists() for path in calls[0])
    assert not (tmp_path / "attempt-001.sse").exists()
    assert transport["http_status"] == 200 and transport["curl_returncode"] == returncode
    if returncode:
        evidence = transport["stream_evidence"]
        assert Path(evidence["sse_path"]) == attempt.with_suffix(".sse")
        assert Path(evidence["headers_path"]) == attempt.with_suffix(".headers")
        assert attempt.with_suffix(".sse").read_bytes() == data.encode("utf-8")
        assert attempt.with_suffix(".headers").read_bytes() == headers.encode("utf-8")
    else:
        assert "stream_evidence" not in transport
        assert not list(directory.glob("*.sse")) and not list(directory.glob("*.headers"))
    assert all(STREAM["SECRET"] not in path.read_text(encoding="utf-8")
               for path in directory.iterdir() if path.is_file())
    router.verify_ledger()
