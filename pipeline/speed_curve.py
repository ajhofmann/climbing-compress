"""Constrained duration solver for speed curve generation."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d


def solve_speed_curve(
    scores: np.ndarray,
    fps: float,
    target_duration: float,
    min_speed: float = 0.25,
    max_speed: float = 6.0,
    sensitivity: float = 0.5,
    smoothing: float = 0.3,
    steepness: float = 12.0,
    pins: list | None = None,
) -> np.ndarray:
    """
    Generate a speed curve that hits a target output duration.

    High score -> low speed (slow-mo for action).
    Low score -> high speed (fast-forward through rest).
    """
    n = len(scores)
    dt = 1.0 / fps
    input_duration = n * dt
    target_duration = min(target_duration, input_duration)

    # Map scores to speeds via sigmoid
    sigmoid = 1.0 / (1.0 + np.exp(-steepness * (scores - sensitivity)))
    speeds = max_speed - (max_speed - min_speed) * sigmoid

    # Apply pin points
    if pins:
        for time_s, pin_speed in pins:
            frame_idx = int(time_s * fps)
            if 0 <= frame_idx < n:
                window = int(fps * 0.5)
                pin_speed = np.clip(pin_speed, min_speed, max_speed)
                for j in range(max(0, frame_idx - window), min(n, frame_idx + window)):
                    dist = abs(j - frame_idx) / max(window, 1)
                    weight = 1.0 - dist
                    speeds[j] = speeds[j] * (1 - weight) + pin_speed * weight

    # Iteratively solve for target duration
    for _ in range(20):
        current_duration = np.sum(dt / speeds)
        ratio = current_duration / target_duration
        if abs(ratio - 1.0) < 0.005:
            break
        speeds *= ratio
        speeds = np.clip(speeds, min_speed, max_speed)

    # Smooth
    sigma_frames = max(1, fps * smoothing)
    speeds = gaussian_filter1d(speeds, sigma=sigma_frames)
    speeds = np.clip(speeds, min_speed, max_speed)

    # Final duration adjustment
    current_duration = np.sum(dt / speeds)
    if current_duration > 0:
        speeds *= current_duration / target_duration
        speeds = np.clip(speeds, min_speed, max_speed)

    return speeds


def solve_constant_progress(
    progress_rate: np.ndarray,
    fps: float,
    target_duration: float,
    min_speed: float = 0.5,
    max_speed: float = 12.0,
    smoothing: float = 0.5,
    floor: float = 0.02,
    pins: list | None = None,
) -> np.ndarray:
    """
    Generate a speed curve that produces constant visual progress.

    Instead of "slow for action, fast for rest," this allocates output
    time proportional to how much the climber moves on the wall.

    When progress_rate is high: speed is low (lots happening per frame).
    When progress_rate is zero: speed is maxed (nothing happening).

    The result: at t=50% of the output, you're ~50% up the boulder.

    Args:
        progress_rate: per-frame spatial displacement, normalized [0,1]
        fps: video framerate
        target_duration: desired output duration in seconds
        min_speed: minimum speed (for fast-moving sections)
        max_speed: maximum speed (for stalled sections)
        smoothing: gaussian smoothing sigma in seconds
        floor: minimum progress rate (prevents infinite speed on zero-move frames)
        pins: optional list of (time_seconds, speed_multiplier) to pin
    """
    n = len(progress_rate)
    dt = 1.0 / fps
    input_duration = n * dt
    target_duration = min(target_duration, input_duration)

    # Add a floor so zero-progress frames don't get infinite speed
    rate = np.maximum(progress_rate, floor)

    # Speed is inversely proportional to progress rate:
    # high rate (lots of progress) -> low speed (give it screen time)
    # low rate (stalling) -> high speed (skip through)
    speeds = 1.0 / rate  # raw inverse

    # Normalize to [min_speed, max_speed] range
    s_min, s_max = speeds.min(), speeds.max()
    if s_max > s_min:
        speeds = min_speed + (speeds - s_min) / (s_max - s_min) * (max_speed - min_speed)
    else:
        speeds = np.full(n, (min_speed + max_speed) / 2)

    # Apply pin points
    if pins:
        for time_s, pin_speed in pins:
            frame_idx = int(time_s * fps)
            if 0 <= frame_idx < n:
                window = int(fps * 0.5)
                pin_speed = np.clip(pin_speed, min_speed, max_speed)
                for j in range(max(0, frame_idx - window), min(n, frame_idx + window)):
                    dist = abs(j - frame_idx) / max(window, 1)
                    weight = 1.0 - dist
                    speeds[j] = speeds[j] * (1 - weight) + pin_speed * weight

    # Iteratively solve for target duration
    for _ in range(20):
        current_duration = np.sum(dt / speeds)
        ratio = current_duration / target_duration
        if abs(ratio - 1.0) < 0.005:
            break
        speeds *= ratio
        speeds = np.clip(speeds, min_speed, max_speed)

    # Smooth
    sigma_frames = max(1, fps * smoothing)
    speeds = gaussian_filter1d(speeds, sigma=sigma_frames)
    speeds = np.clip(speeds, min_speed, max_speed)

    # Final duration adjustment
    current_duration = np.sum(dt / speeds)
    if current_duration > 0:
        speeds *= current_duration / target_duration
        speeds = np.clip(speeds, min_speed, max_speed)

    return speeds


def get_output_duration(speeds: np.ndarray, fps: float) -> float:
    dt = 1.0 / fps
    return float(np.sum(dt / speeds))


def get_time_mapping(speeds: np.ndarray, fps: float) -> np.ndarray:
    dt = 1.0 / fps
    output_times = dt / speeds
    return np.cumsum(output_times)
