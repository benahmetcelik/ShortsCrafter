from __future__ import annotations

import re
import sys


def log(message: str) -> None:
    """Windows konsolunda Unicode hatasi vermeden yazdir."""
    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        safe = message.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
            sys.stdout.encoding or "utf-8", errors="replace"
        )
        print(safe, flush=True)


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-zğüşöçıİĞÜŞÖÇ\- _]", "", name.strip())
    return cleaned.replace(" ", "_") or "output"
