from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
TEMP_AUDIO_DIR = PROJECT_ROOT / "temp_audio"

DEFAULT_SECTORS = [
    "Kahve dükkanı",
    "E-ticaret girişimi",
    "Yazılım ajansı",
    "Kuru temizleme",
    "Organik tarım",
    "Berber dükkanı",
    "Pastane",
    "Oto yıkama",
    "Kuaför salonu",
    "Pet shop",
]


@dataclass(frozen=True)
class Settings:
    hf_token: str
    openrouter_api_key: str | None = None
    voice: str = "tr-TR-AhmetNeural"
    video_width: int = 1080
    video_height: int = 1920
    video_fps: int = 30
    video_bitrate: str = "3000k"
    audio_bitrate: str = "192k"
    flux_model: str = "black-forest-labs/FLUX.1-schnell"
    openrouter_model: str = "gpt-3.5-turbo"
    scene_count: int = 6
    crossfade_seconds: float = 0.0
    audio_sample_rate: int = 24000
    silence_threshold: float = 0.012
    min_silence_sec: float = 0.12
    keep_silence_sec: float = 0.03
    sectors: tuple[str, ...] = field(default_factory=lambda: tuple(DEFAULT_SECTORS))
    subtitles_enabled: bool = True
    subtitle_font: str = "ariblk.ttf"
    subtitle_font_size_ratio: float = 0.07
    subtitle_fill_color: str = "yellow"
    subtitle_stroke_color: str = "black"
    subtitle_y_ratio: float = 0.65

    @classmethod
    def from_env(cls) -> Settings:
        hf_token = os.getenv("HF_TOKEN", "").strip()
        if not hf_token:
            raise RuntimeError(
                "HF_TOKEN bulunamadi. .env dosyasina HF_TOKEN=... ekleyin veya "
                "ortam degiskeni olarak tanimlayin: https://huggingface.co/settings/tokens"
            )

        sectors_file = DATA_DIR / "sectors.json"
        sectors = tuple(DEFAULT_SECTORS)
        if sectors_file.exists():
            import json

            loaded = json.loads(sectors_file.read_text(encoding="utf-8"))
            if isinstance(loaded, list) and loaded:
                sectors = tuple(str(s) for s in loaded)

        return cls(
            hf_token=hf_token,
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip() or None,
            voice=os.getenv("TTS_VOICE", "tr-TR-AhmetNeural"),
            video_width=int(os.getenv("VIDEO_WIDTH", "1080")),
            video_height=int(os.getenv("VIDEO_HEIGHT", "1920")),
            video_fps=int(os.getenv("VIDEO_FPS", "30")),
            video_bitrate=os.getenv("VIDEO_BITRATE", "3000k"),
            audio_bitrate=os.getenv("AUDIO_BITRATE", "192k"),
            flux_model=os.getenv("FLUX_MODEL", "black-forest-labs/FLUX.1-schnell"),
            openrouter_model=os.getenv("OPENROUTER_MODEL", "gpt-3.5-turbo"),
            scene_count=int(os.getenv("SCENE_COUNT", "6")),
            crossfade_seconds=float(os.getenv("CROSSFADE_SECONDS", "0")),
            audio_sample_rate=int(os.getenv("AUDIO_SAMPLE_RATE", "24000")),
            silence_threshold=float(os.getenv("SILENCE_THRESHOLD", "0.012")),
            min_silence_sec=float(os.getenv("MIN_SILENCE_SEC", "0.12")),
            keep_silence_sec=float(os.getenv("KEEP_SILENCE_SEC", "0.03")),
            sectors=sectors,
            subtitles_enabled=os.getenv("SUBTITLES_ENABLED", "True").lower() == "true",
            subtitle_font=os.getenv("SUBTITLE_FONT", "ariblk.ttf"),
            subtitle_font_size_ratio=float(os.getenv("SUBTITLE_FONT_SIZE_RATIO", "0.07")),
            subtitle_fill_color=os.getenv("SUBTITLE_FILL_COLOR", "yellow"),
            subtitle_stroke_color=os.getenv("SUBTITLE_STROKE_COLOR", "black"),
            subtitle_y_ratio=float(os.getenv("SUBTITLE_Y_RATIO", "0.65")),
        )

    @property
    def use_openrouter(self) -> bool:
        return bool(self.openrouter_api_key)
