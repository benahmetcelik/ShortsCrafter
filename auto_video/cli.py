from __future__ import annotations

import argparse
import sys

from auto_video import __version__
from auto_video.pipeline import run_full_pipeline, run_script_only, run_video_only


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auto-video",
        description="Otomatik video uretim araci: senaryo, ses, gorsel ve montaj.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    script_parser = subparsers.add_parser("script", help="Yalnizca senaryo uret")
    script_parser.add_argument(
        "--reset-seen",
        action="store_true",
        help="Daha once kullanilan sektor listesini sifirla",
    )

    subparsers.add_parser("video", help="Mevcut senaryodan video olustur")

    all_parser = subparsers.add_parser("all", help="Senaryo uret ve video olustur")
    all_parser.add_argument(
        "--reset-seen",
        action="store_true",
        help="Daha once kullanilan sektor listesini sifirla",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "script":
            run_script_only(reset_seen=args.reset_seen)
        elif args.command == "video":
            run_video_only()
        elif args.command == "all":
            run_full_pipeline(reset_seen=args.reset_seen)
        else:
            parser.error(f"Bilinmeyen komut: {args.command}")
    except Exception as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
