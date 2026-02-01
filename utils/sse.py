"""Server-Sent Events helper — run a pipeline step with streamed progress."""

from __future__ import annotations

import json
import logging
import queue
import threading
from collections.abc import Callable

from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)


def sse_response(worker: Callable[[Callable[[dict], None]], None]) -> StreamingResponse:
    """Run *worker* in a background thread, streaming SSE progress events.

    *worker* receives an ``emit`` callback.  Calling ``emit({"progress": 0.5,
    "message": "…"})`` sends one SSE ``data:`` line to the client.

    The stream closes automatically when *worker* returns.  Unhandled
    exceptions are caught, logged, and forwarded as an ``error`` event.

    Usage in a FastAPI endpoint::

        @app.post("/api/analyze")
        async def analyze(req: AnalyzeRequest):
            def worker(emit):
                run_analysis(str(path), req, emit)
            return sse_response(worker)
    """
    progress_q: queue.Queue[dict | None] = queue.Queue()

    def _run() -> None:
        try:
            worker(progress_q.put)
        except Exception as exc:
            logger.exception("SSE worker failed")
            progress_q.put({"progress": 0, "message": f"Error: {exc}", "error": True})
        finally:
            progress_q.put(None)  # sentinel — closes the stream

    def _generate():
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        while True:
            try:
                msg = progress_q.get(timeout=0.3)
            except queue.Empty:
                continue
            if msg is None:
                break
            yield f"data: {json.dumps(msg)}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")
