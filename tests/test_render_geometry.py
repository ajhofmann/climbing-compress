"""Tests for render geometry helpers."""

from __future__ import annotations

from pipeline.render import _resolve_output_geometry


def test_resolve_output_geometry_original_keeps_scaled_shape():
    base_w, base_h, out_w, out_h = _resolve_output_geometry(
        src_w=1920,
        src_h=1080,
        scale=0.5,
        output_aspect="original",
    )
    assert (base_w, base_h) == (960, 540)
    assert (out_w, out_h) == (960, 540)


def test_resolve_output_geometry_vertical_crops_width():
    base_w, base_h, out_w, out_h = _resolve_output_geometry(
        src_w=1920,
        src_h=1080,
        scale=0.5,
        output_aspect="vertical",
    )
    assert (base_w, base_h) == (960, 540)
    assert out_h == 540
    # 540 * 9 / 16 = 303.75 -> even close value
    assert out_w in (302, 304)


def test_resolve_output_geometry_square_uses_min_axis():
    base_w, base_h, out_w, out_h = _resolve_output_geometry(
        src_w=1280,
        src_h=720,
        scale=0.5,
        output_aspect="square",
    )
    assert (base_w, base_h) == (640, 360)
    assert out_w == out_h
    assert out_w == 360
