from __future__ import annotations

from pathlib import Path

from huggingface_hub import InferenceClient

from auto_video.config import Settings
from auto_video.utils import log


class ImageGenerator:
    def __init__(self, settings: Settings) -> None:
        self._client = InferenceClient(model=settings.flux_model, token=settings.hf_token)

    def generate(self, prompt: str, save_path: Path) -> None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        log(f"Resim uretiliyor: {prompt[:80]}...")
        image = self._client.text_to_image(prompt)
        image.save(save_path)
        log(f"Resim kaydedildi: {save_path.name}")

    def generate_if_missing(self, prompt: str, save_path: Path) -> None:
        if save_path.exists():
            return
        self.generate(prompt, save_path)
