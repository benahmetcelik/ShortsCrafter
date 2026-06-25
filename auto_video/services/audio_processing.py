from __future__ import annotations

import numpy as np
from moviepy.audio.AudioClip import AudioArrayClip
from moviepy.editor import AudioFileClip


def _to_mono(arr: np.ndarray) -> np.ndarray:
    if arr.ndim > 1:
        return np.mean(arr, axis=1)
    return arr.copy()


def _windowed_rms(mono: np.ndarray, window_size: int) -> np.ndarray:
    if len(mono) < window_size:
        return np.array([np.sqrt(np.mean(mono**2))])
    trimmed = mono[: len(mono) - (len(mono) % window_size)]
    frames = trimmed.reshape(-1, window_size)
    return np.sqrt(np.mean(frames**2, axis=1))


def _find_speech_segments(
    mono: np.ndarray,
    sample_rate: int,
    threshold: float,
    window_ms: int = 10,
) -> list[tuple[int, int]]:
    window_size = max(1, int(sample_rate * window_ms / 1000))
    rms = _windowed_rms(mono, window_size)
    speech_frames = rms > threshold

    segments: list[tuple[int, int]] = []
    start_frame: int | None = None
    for index, is_speech in enumerate(speech_frames):
        if is_speech and start_frame is None:
            start_frame = index
        elif not is_speech and start_frame is not None:
            segments.append((start_frame * window_size, index * window_size))
            start_frame = None

    if start_frame is not None:
        segments.append((start_frame * window_size, len(mono)))

    return segments


def _merge_close_segments(
    segments: list[tuple[int, int]],
    min_gap_samples: int,
) -> list[tuple[int, int]]:
    if not segments:
        return []

    merged = [segments[0]]
    for start, end in segments[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= min_gap_samples:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))
    return merged


def compress_silence_array(
    arr: np.ndarray,
    sample_rate: int,
    *,
    threshold: float = 0.012,
    min_silence_sec: float = 0.12,
    keep_silence_sec: float = 0.03,
    edge_pad_sec: float = 0.015,
) -> tuple[np.ndarray, list[tuple[int, int, int, int]]]:
    """Konusma icindeki uzun duraklamalari kisaltir, bas/son sessizligi temizler."""
    if arr.size == 0:
        return arr, []

    mono = _to_mono(arr)
    min_gap = int(min_silence_sec * sample_rate)
    keep_gap = int(keep_silence_sec * sample_rate)
    edge_pad = int(edge_pad_sec * sample_rate)

    segments = _find_speech_segments(mono, sample_rate, threshold)
    if not segments:
        return arr, [(0, arr.shape[0], 0, arr.shape[0])]

    segments = _merge_close_segments(segments, min_gap)
    total_samples = arr.shape[0]
    pieces: list[np.ndarray] = []
    
    kept_segments = []
    curr_new_start = 0

    for index, (start, end) in enumerate(segments):
        clip_start = max(0, start - edge_pad if index == 0 else start)
        clip_end = min(total_samples, end + edge_pad if index == len(segments) - 1 else end)
        
        piece_len = clip_end - clip_start
        pieces.append(arr[clip_start:clip_end])
        kept_segments.append((clip_start, clip_end, curr_new_start, curr_new_start + piece_len))
        curr_new_start += piece_len

        if index < len(segments) - 1:
            next_start = segments[index + 1][0]
            gap = next_start - end
            if gap > min_gap and keep_gap > 0:
                gap_start = max(end, next_start - keep_gap)
                
                gap_len = next_start - gap_start
                pieces.append(arr[gap_start:next_start])
                kept_segments.append((gap_start, next_start, curr_new_start, curr_new_start + gap_len))
                curr_new_start += gap_len

    if not pieces:
        return arr, [(0, arr.shape[0], 0, arr.shape[0])]

    return np.concatenate(pieces, axis=0), kept_segments


def clip_to_array(clip: AudioFileClip, sample_rate: int = 24000) -> np.ndarray:
    chunks = list(clip.iter_chunks(fps=sample_rate, chunksize=sample_rate, nbytes=2))
    if not chunks:
        return np.array([], dtype=np.float32)
    return np.vstack(chunks)


def remove_silence_from_clip(
    clip: AudioFileClip,
    *,
    sample_rate: int = 24000,
    threshold: float = 0.012,
    min_silence_sec: float = 0.12,
    keep_silence_sec: float = 0.03,
    edge_pad_sec: float = 0.015,
) -> tuple[AudioArrayClip | AudioFileClip, list[tuple[int, int, int, int]]]:
    arr = clip_to_array(clip, sample_rate)
    if arr.size == 0:
        return clip, []

    compressed, kept_segments = compress_silence_array(
        arr,
        sample_rate,
        threshold=threshold,
        min_silence_sec=min_silence_sec,
        keep_silence_sec=keep_silence_sec,
        edge_pad_sec=edge_pad_sec,
    )
    return AudioArrayClip(compressed, fps=sample_rate), kept_segments
