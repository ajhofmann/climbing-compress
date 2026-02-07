"""Background job worker for climb-ramp.

Polls the SQLite job queue and executes analyze/render/preview jobs.
"""

from __future__ import annotations

import json
import logging
import time

from db import claim_next_job, update_job
import server


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")


def _handle_job(job: dict) -> None:
    job_id = job["id"]
    job_type = job["job_type"]
    request_json = job.get("request_json")
    try:
        payload = json.loads(request_json) if request_json else {}
    except json.JSONDecodeError as exc:
        update_job(job_id, status="failed", message=f"Invalid request payload: {exc}")
        return

    try:
        if job_type == "analyze":
            req = server.AnalyzeRequest(**payload)
            path = server._get_video_path(req.video_id)
            server._analysis_job_worker(job_id, path, req, lambda _payload: None)
        elif job_type == "render":
            req = server.RenderRequest(**payload)
            path = server._get_video_path(req.video_id)
            server._render_job_worker(job_id, path, req, lambda _payload: None)
        elif job_type == "preview":
            req = server.PreviewRequest(**payload)
            path = server._get_video_path(req.video_id)
            preview_req = server._build_preview_request(req, path)
            server._preview_job_worker(job_id, path, preview_req, lambda _payload: None)
        else:
            update_job(job_id, status="failed", message=f"Unknown job type: {job_type}")
    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        update_job(job_id, status="failed", message=str(exc))


def main() -> None:
    logger.info("Worker started")
    while True:
        job = claim_next_job()
        if job:
            logger.info("Processing job %s (%s)", job["id"], job["job_type"])
            _handle_job(job)
        else:
            time.sleep(2)


if __name__ == "__main__":
    main()
