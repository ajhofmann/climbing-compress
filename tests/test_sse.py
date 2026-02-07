import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.sse import sse_response


def test_sse_response_emits_error_event():
    app = FastAPI()

    @app.get("/stream")
    def stream():
        def worker(emit):
            emit({"progress": 0.2, "message": "Working"})
            raise RuntimeError("boom")

        return sse_response(worker)

    client = TestClient(app)
    response = client.get("/stream")
    assert response.status_code == 200

    lines = [line for line in response.text.splitlines() if line.startswith("data: ")]
    payloads = [json.loads(line.replace("data: ", "")) for line in lines]
    assert payloads[0]["progress"] == 0.2
    assert payloads[0]["message"] == "Working"
    assert payloads[-1]["error"] is True
    assert "Error: boom" in payloads[-1]["message"]


def test_sse_response_emits_progress():
    app = FastAPI()

    @app.get("/stream")
    def stream():
        def worker(emit):
            emit({"progress": 0.1, "message": "Start"})
            emit({"progress": 0.9, "message": "Almost"})

        return sse_response(worker)

    client = TestClient(app)
    response = client.get("/stream")
    assert response.status_code == 200

    lines = [line for line in response.text.splitlines() if line.startswith("data: ")]
    payloads = [json.loads(line.replace("data: ", "")) for line in lines]
    assert payloads[0]["message"] == "Start"
    assert payloads[1]["message"] == "Almost"
