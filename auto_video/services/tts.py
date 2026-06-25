from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from auto_video.config import PROJECT_ROOT, Settings
from auto_video.utils import log

try:
    import edge_tts

    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False


def _find_piper_exe() -> Path | None:
    candidates = [
        PROJECT_ROOT / "pipper" / "piper.exe",
        PROJECT_ROOT / "piper" / "piper.exe",
        PROJECT_ROOT / "piper.exe",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _find_piper_model(piper_dir: Path) -> Path:
    for name in ("tr_TR-fettah-medium.onnx", "tr_TR-fettah.onnx"):
        model = piper_dir / name
        if model.exists():
            return model
    raise FileNotFoundError(f"Piper model dosyasi bulunamadi: {piper_dir}")


def _run_piper(piper_exe: Path, model_path: Path, text: str, output_path: Path) -> None:
    args = [
        str(piper_exe),
        "--model",
        str(model_path),
        "--output_file",
        str(output_path),
    ]
    try:
        subprocess.run(args, input=text.encode("utf-8"), check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Piper TTS hatasi: {exc}") from exc


async def generate_audio(text: str, output_path: Path, settings: Settings) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if EDGE_TTS_AVAILABLE:
        import json
        communicate = edge_tts.Communicate(text, settings.voice, boundary="WordBoundary")
        words = []
        with open(output_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    words.append({
                        "text": chunk["text"],
                        "start": chunk["offset"] / 10000000.0,
                        "end": (chunk["offset"] + chunk["duration"]) / 10000000.0,
                    })
        words_path = output_path.parent / f"{output_path.stem}_words.json"
        words_path.write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    piper_exe = _find_piper_exe()
    if not piper_exe:
        raise RuntimeError(
            "TTS backend bulunamadi. Kurulum: pip install edge-tts "
            "veya pipper/piper.exe dosyasini projeye ekleyin."
        )

    model_path = _find_piper_model(piper_exe.parent)
    await asyncio.to_thread(_run_piper, piper_exe, model_path, text, output_path)
    log(f"Ses kaydedildi (Piper): {output_path.name}")


async def generate_all_audio(
    scenes: list[tuple[int, str, Path]],
    settings: Settings,
) -> None:
    for scene_id, text, audio_path in scenes:
        words_path = audio_path.parent / f"{audio_path.stem}_words.json"
        # Eğer altyazı aktifse, hem mp3 hem de json dosyalarının varlığını kontrol et
        if audio_path.exists() and (not settings.subtitles_enabled or words_path.exists()):
            log(f"Sahne {scene_id} sesi ve altyazi verisi zaten var.")
            continue
        log(f"Sahne {scene_id} icin ses olusturuluyor...")
        await generate_audio(text, audio_path, settings)
