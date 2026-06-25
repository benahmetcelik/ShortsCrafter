from __future__ import annotations

from auto_video.config import Settings
from auto_video.services.script import generate_script
from auto_video.services.video import compose_video
from auto_video.utils import log


def run_full_pipeline(*, reset_seen: bool = False) -> None:
    settings = Settings.from_env()
    log("=== 1/2 Senaryo uretiliyor ===")
    generate_script(settings, reset_seen=reset_seen)
    log("\n=== 2/2 Video olusturuluyor ===")
    compose_video(settings)


def run_script_only(*, reset_seen: bool = False) -> None:
    settings = Settings.from_env()
    generate_script(settings, reset_seen=reset_seen)


def run_video_only() -> None:
    settings = Settings.from_env()
    compose_video(settings)
