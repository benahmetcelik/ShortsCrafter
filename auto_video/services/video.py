from __future__ import annotations

import json
from pathlib import Path

from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips, CompositeVideoClip
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from auto_video.compat import apply_pil_compat
from auto_video.config import DATA_DIR, TEMP_AUDIO_DIR, Settings

apply_pil_compat()
from auto_video.models import Scene
from auto_video.services.audio_processing import remove_silence_from_clip
from auto_video.utils import log, sanitize_filename


def _load_scenes(input_file: Path) -> list[Scene]:
    payload = json.loads(input_file.read_text(encoding="utf-8"))
    return [Scene.from_dict(item) for item in payload]


def _resolve_output_name() -> str:
    sector_file = DATA_DIR / "sector.txt"
    if sector_file.exists():
        return sanitize_filename(sector_file.read_text(encoding="utf-8"))
    return "output"


def _map_sample_time(t: float, kept_segments: list[tuple[int, int, int, int]], sample_rate: int) -> float:
    sample_orig = int(t * sample_rate)
    for orig_start, orig_end, new_start, new_end in kept_segments:
        if orig_start <= sample_orig <= orig_end:
            fraction = (sample_orig - orig_start) / (orig_end - orig_start) if orig_end > orig_start else 0.0
            sample_new = new_start + fraction * (new_end - new_start)
            return sample_new / sample_rate
            
    if kept_segments and sample_orig < kept_segments[0][0]:
        return 0.0
        
    for i in range(len(kept_segments) - 1):
        prev_end_orig = kept_segments[i][1]
        next_start_orig = kept_segments[i+1][0]
        if prev_end_orig <= sample_orig <= next_start_orig:
            return kept_segments[i+1][2] / sample_rate
            
    if kept_segments:
        return kept_segments[-1][3] / sample_rate
        
    return t


def _map_word_timestamps(
    words: list[dict],
    kept_segments: list[tuple[int, int, int, int]],
    sample_rate: int
) -> list[dict]:
    mapped_words = []
    for w in words:
        start_new = _map_sample_time(w["start"], kept_segments, sample_rate)
        end_new = _map_sample_time(w["end"], kept_segments, sample_rate)
        if end_new > start_new:
            mapped_words.append({
                "text": w["text"],
                "start": start_new,
                "end": end_new
            })
    return mapped_words


def _estimate_word_timestamps(text: str, duration: float) -> list[dict]:
    words = text.split()
    if not words or duration <= 0:
        return []
    
    word_duration = duration / len(words)
    result = []
    for i, w in enumerate(words):
        result.append({
            "text": w,
            "start": i * word_duration,
            "end": (i + 1) * word_duration
        })
    return result


def _group_words_for_subtitles(words: list[dict], max_words: int = 3, max_gap: float = 0.5) -> list[dict]:
    if not words:
        return []
    
    groups = []
    current_group = []
    
    for w in words:
        if not current_group:
            current_group.append(w)
        else:
            last_word = current_group[-1]
            gap = w["start"] - last_word["end"]
            
            if len(current_group) < max_words and gap <= max_gap:
                current_group.append(w)
            else:
                groups.append(current_group)
                current_group = [w]
                
    if current_group:
        groups.append(current_group)
        
    subtitles = []
    for g in groups:
        if len(g) == 3:
            text = f"{g[0]['text'].upper()} {g[1]['text'].upper()}\n{g[2]['text'].upper()}"
        else:
            text = " ".join([w["text"] for w in g]).upper()
        start = g[0]["start"]
        end = g[-1]["end"]
        subtitles.append({
            "text": text,
            "start": start,
            "end": end
        })
    return subtitles


def _create_subtitle_clip(text: str, duration: float, settings: Settings) -> ImageClip:
    initial_font_size = int(settings.video_width * settings.subtitle_font_size_ratio)
    font_size = initial_font_size
    font_path = f"C:/Windows/Fonts/{settings.subtitle_font}"
    
    img_h = int(initial_font_size * 3.2) # Increased canvas height to safely fit 2 lines
    img_w = settings.video_width
    max_text_width = int(settings.video_width * 0.85)  # 85% of screen width to ensure margins
    
    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Scale down font size dynamically if it exceeds maximum text width
    while True:
        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size)
            except IOError:
                font = ImageFont.load_default()
                break
                
        try:
            bbox = draw.multiline_textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        except AttributeError:
            try:
                text_w, text_h = draw.textsize(text, font=font)
            except Exception:
                text_w, text_h = len(text) * (font_size * 0.6), font_size
            
        if text_w <= max_text_width or font_size <= 20:
            break
        font_size -= 4
        
    x = (img_w - text_w) / 2
    y = (img_h - text_h) / 2 - (text_h * 0.1)
    
    fill_color = settings.subtitle_fill_color
    stroke_color = settings.subtitle_stroke_color
    stroke_width = max(1, int(font_size * 0.08))
    
    draw.multiline_text(
        (x, y),
        text,
        font=font,
        fill=fill_color,
        stroke_width=stroke_width,
        stroke_fill=stroke_color,
        align="center"
    )
    
    rgba = np.array(img)
    rgb = rgba[:, :, :3]
    alpha = rgba[:, :, 3] / 255.0
    
    mask = ImageClip(alpha, ismask=True).set_duration(duration)
    txt_clip = ImageClip(rgb).set_mask(mask).set_duration(duration)
    
    y_pos = int(settings.video_height * settings.subtitle_y_ratio - img_h / 2)
    txt_clip = txt_clip.set_position(("center", y_pos))
    return txt_clip


def _process_scene_audio(audio_path: Path, settings: Settings) -> tuple[AudioFileClip, list[tuple[int, int, int, int]]]:
    clip = AudioFileClip(str(audio_path))
    original_duration = clip.duration
    processed, kept_segments = remove_silence_from_clip(
        clip,
        sample_rate=settings.audio_sample_rate,
        threshold=settings.silence_threshold,
        min_silence_sec=settings.min_silence_sec,
        keep_silence_sec=settings.keep_silence_sec,
    )
    clip.close()
    saved = original_duration - processed.duration
    if saved > 0.05:
        log(f"  Sessizlik kirpildi: {original_duration:.1f}s -> {processed.duration:.1f}s")
    return processed, kept_segments


def _build_scene_clip(
    image_path: Path,
    audio_clip: AudioFileClip,
    settings: Settings,
    *,
    apply_crossfade: bool,
    scene: Scene,
    kept_segments: list[tuple[int, int, int, int]],
    audio_path: Path,
) -> ImageClip | CompositeVideoClip:
    target_w = settings.video_width
    target_h = settings.video_height

    img_clip = ImageClip(str(image_path))
    if img_clip.w > 0 and img_clip.h > 0:
        scale = max(target_w / img_clip.w, target_h / img_clip.h)
        resized = img_clip.resize(scale)
        crop_x1 = int((resized.w - target_w) / 2)
        crop_y1 = int((resized.h - target_h) / 2)
        cropped = resized.crop(
            x1=crop_x1,
            y1=crop_y1,
            x2=crop_x1 + target_w,
            y2=crop_y1 + target_h,
        )
    else:
        cropped = img_clip.resize(height=target_h)

    video_clip = cropped.set_duration(audio_clip.duration)

    if settings.subtitles_enabled:
        words = []
        words_path = audio_path.parent / f"{audio_path.stem}_words.json"
        
        if words_path.exists():
            try:
                words = json.loads(words_path.read_text(encoding="utf-8"))
                words = _map_word_timestamps(words, kept_segments, settings.audio_sample_rate)
            except Exception as exc:
                log(f"  [UYARI] Altyazi kelime verisi yuklenemedi: {exc}. Tahminleme kullaniliyor.")
                words = _estimate_word_timestamps(scene.text, audio_clip.duration)
        else:
            log(f"  [UYARI] Altyazi kelime verisi bulunamadi: {words_path}. Tahminleme kullaniliyor.")
            words = _estimate_word_timestamps(scene.text, audio_clip.duration)
            
        subtitle_segments = _group_words_for_subtitles(words, max_words=3, max_gap=0.5)
        
        subtitle_clips = []
        for sub in subtitle_segments:
            duration = sub["end"] - sub["start"]
            if duration > 0:
                txt_clip = _create_subtitle_clip(sub["text"], duration, settings)
                txt_clip = txt_clip.set_start(sub["start"])
                subtitle_clips.append(txt_clip)
                
        if subtitle_clips:
            video_clip = CompositeVideoClip([video_clip, *subtitle_clips]).set_duration(audio_clip.duration)

    video_clip = video_clip.set_audio(audio_clip)

    if apply_crossfade:
        try:
            video_clip = video_clip.crossfadein(settings.crossfade_seconds)
        except Exception:
            pass
    return video_clip


def compose_video(settings: Settings, *, input_file: Path | None = None) -> Path:
    input_path = input_file or (DATA_DIR / "input.json")
    if not input_path.exists():
        raise FileNotFoundError(
            f"Senaryo dosyasi bulunamadi: {input_path}. Once script uretin."
        )

    log("Video olusturma sureci basliyor...")
    scenes = _load_scenes(input_path)
    output_name = _resolve_output_name()

    img_dir = DATA_DIR / output_name
    audio_dir = TEMP_AUDIO_DIR / output_name
    video_dir = DATA_DIR / "videos"
    img_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)

    from auto_video.services.images import ImageGenerator
    from auto_video.services.tts import generate_all_audio

    image_generator = ImageGenerator(settings)

    for scene in scenes:
        image_generator.generate_if_missing(
            scene.prompt,
            img_dir / f"image_{scene.scene}.jpg",
        )

    audio_jobs = [
        (
            scene.scene,
            scene.text,
            audio_dir / f"audio_{scene.scene}.mp3",
        )
        for scene in scenes
    ]

    import asyncio

    asyncio.run(generate_all_audio(audio_jobs, settings))

    scene_items: list[tuple[Scene, Path, AudioFileClip, list[tuple[int, int, int, int]], Path]] = []
    total_duration = 0.0
    for scene in scenes:
        audio_path = audio_dir / f"audio_{scene.scene}.mp3"
        audio_clip, kept_segments = _process_scene_audio(audio_path, settings)
        total_duration += audio_clip.duration
        scene_items.append((scene, img_dir / f"image_{scene.scene}.jpg", audio_clip, kept_segments, audio_path))

    log(f"Toplam ses suresi: {total_duration:.2f}s")

    clips = [
        _build_scene_clip(
            image_path,
            audio_clip,
            settings,
            apply_crossfade=index > 0,
            scene=scene,
            kept_segments=kept_segments,
            audio_path=audio_path,
        )
        for index, (scene, image_path, audio_clip, kept_segments, audio_path) in enumerate(scene_items)
    ]

    log("Video klipleri birlestiriliyor...")
    final_video = concatenate_videoclips(clips)
    out_path = video_dir / f"{output_name}.mp4"

    log(f"Video dosyasi yaziliyor: {out_path}")
    log(f"  FPS: {settings.video_fps}")
    log(f"  Video bitrate: {settings.video_bitrate}")
    log(f"  Audio bitrate: {settings.audio_bitrate}")
    log(f"  Boyut: {settings.video_width}x{settings.video_height}")

    final_video.write_videofile(
        str(out_path),
        fps=settings.video_fps,
        codec="libx264",
        audio_codec="aac",
        bitrate=settings.video_bitrate,
        audio_bitrate=settings.audio_bitrate,
        threads=4,
        verbose=False,
        logger=None,
    )
    log(f"[OK] Video basariyla kaydedildi: {out_path}")
    return out_path
