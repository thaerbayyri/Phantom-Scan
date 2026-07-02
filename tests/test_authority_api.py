import json
import socket
from urllib.request import Request, urlopen

from phantom.api import RuntimeApiServer
from phantom.runtime import PhantomRuntime, RuntimeConfig


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return int(port)


def test_authority_sensing_frame_endpoint(tmp_path):
    runtime = PhantomRuntime(RuntimeConfig(output_dir=str(tmp_path)))
    port = _free_port()
    api = RuntimeApiServer(runtime, host="127.0.0.1", port=port)
    api.start()
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/sensing/frame", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        api.stop()

    assert payload["status"] == "ok"
    assert payload["authority"] is True
    assert payload["synthetic_enabled"] is False
    assert payload["source"] == "live"
    assert payload["derived"] is None


def test_authority_health_and_status_endpoints(tmp_path):
    runtime = PhantomRuntime(RuntimeConfig(output_dir=str(tmp_path)))
    port = _free_port()
    api = RuntimeApiServer(runtime, host="127.0.0.1", port=port)
    api.start()
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
            health_payload = json.loads(response.read().decode("utf-8"))
        with urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2) as response:
            status_payload = json.loads(response.read().decode("utf-8"))
    finally:
        api.stop()

    assert health_payload["status"] == "ok"
    assert health_payload["authority"] is True
    assert health_payload["source"] == "live"
    assert health_payload["synthetic_enabled"] is False
    assert status_payload["status"] == "ok"
    assert status_payload["authority"] is True
    assert status_payload["source"] == "live"
    assert status_payload["synthetic_enabled"] is False


def test_authority_control_start_stop_exposes_paused_state(tmp_path):
    runtime = PhantomRuntime(RuntimeConfig(output_dir=str(tmp_path)))
    port = _free_port()
    api = RuntimeApiServer(runtime, host="127.0.0.1", port=port)
    api.start()
    try:
        start_request = Request(f"http://127.0.0.1:{port}/api/control/start", method="POST")
        with urlopen(start_request, timeout=2) as response:
            start_payload = json.loads(response.read().decode("utf-8"))

        stop_request = Request(f"http://127.0.0.1:{port}/api/control/stop", method="POST")
        with urlopen(stop_request, timeout=2) as response:
            stop_payload = json.loads(response.read().decode("utf-8"))
    finally:
        api.stop()

    assert start_payload["success"] is True
    assert start_payload["status"]["started"] is True
    assert start_payload["status"]["ingest_paused"] is False
    assert stop_payload["success"] is True
    assert stop_payload["status"]["started"] is False
    assert stop_payload["status"]["ingest_paused"] is True
    assert stop_payload["status"]["source_pinning"] == {}
