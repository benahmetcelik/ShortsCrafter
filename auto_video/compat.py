from __future__ import annotations


def apply_pil_compat() -> None:
    """MoviePy 1.x icin Pillow 10+ uyumluluk yamasi."""
    try:
        from PIL import Image

        if not hasattr(Image, "ANTIALIAS"):
            Image.ANTIALIAS = Image.Resampling.LANCZOS
    except Exception:
        pass
