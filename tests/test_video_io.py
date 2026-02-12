import json

import cv2
import pytest

import utils.video_io as video_io


def test_parse_rate_handles_fraction_and_invalid_values():
    assert video_io._parse_rate("30000/1001") == pytest.approx(29.97003, rel=1e-5)
    assert video_io._parse_rate("24") == 24.0
    assert video_io._parse_rate("0/0") == 0.0
    assert video_io._parse_rate("abc") == 0.0
    assert video_io._parse_rate(None) == 0.0


def test_video_info_ffprobe_parses_video_stream(monkeypatch):
    payload = {
        "streams": [
            {"codec_type": "audio", "sample_rate": "44100"},
            {
                "codec_type": "video",
                "avg_frame_rate": "24000/1001",
                "width": 1080,
                "height": 1920,
                "nb_frames": "1200",
            },
        ],
        "format": {"duration": "50.0"},
    }

    class Result:
        returncode = 0
        stdout = json.dumps(payload)

    monkeypatch.setattr(video_io.subprocess, "run", lambda *args, **kwargs: Result())

    info = video_io._video_info_ffprobe("/tmp/fake.mp4")
    assert info is not None
    assert info["fps"] == pytest.approx(23.976, rel=1e-3)
    assert info["width"] == 1080
    assert info["height"] == 1920
    assert info["frame_count"] == 1200
    assert info["duration"] == 50.0


def test_video_info_ffprobe_estimates_frame_count_when_missing(monkeypatch):
    payload = {
        "streams": [
            {
                "codec_type": "video",
                "avg_frame_rate": "24/1",
                "width": 480,
                "height": 640,
            },
        ],
        "format": {"duration": "2.0"},
    }

    class Result:
        returncode = 0
        stdout = json.dumps(payload)

    monkeypatch.setattr(video_io.subprocess, "run", lambda *args, **kwargs: Result())

    info = video_io._video_info_ffprobe("/tmp/fake.mp4")
    assert info is not None
    assert info["frame_count"] == 48
    assert info["duration"] == 2.0


def test_get_video_info_falls_back_to_cv2_when_ffprobe_missing(monkeypatch):
    monkeypatch.setattr(video_io, "_video_info_ffprobe", lambda _path: None)
    cap_state = {"released": False}

    class FakeCap:
        def isOpened(self):
            return True

        def get(self, prop):
            mapping = {
                cv2.CAP_PROP_FPS: 30.0,
                cv2.CAP_PROP_FRAME_WIDTH: 640.0,
                cv2.CAP_PROP_FRAME_HEIGHT: 360.0,
                cv2.CAP_PROP_FRAME_COUNT: 300.0,
            }
            return mapping.get(prop, 0.0)

        def release(self):
            cap_state["released"] = True

    monkeypatch.setattr(video_io.cv2, "VideoCapture", lambda _path: FakeCap())

    info = video_io.get_video_info("/tmp/fallback.mp4")
    assert info["fps"] == 30.0
    assert info["width"] == 640
    assert info["height"] == 360
    assert info["frame_count"] == 300
    assert info["duration"] == 10.0
    assert cap_state["released"] is True


def test_get_video_info_raises_when_unreadable(monkeypatch):
    monkeypatch.setattr(video_io, "_video_info_ffprobe", lambda _path: None)

    class FakeCap:
        def isOpened(self):
            return False

        def release(self):
            pass

    monkeypatch.setattr(video_io.cv2, "VideoCapture", lambda _path: FakeCap())

    with pytest.raises(ValueError, match="Cannot open video"):
        video_io.get_video_info("/tmp/unreadable.mp4")
