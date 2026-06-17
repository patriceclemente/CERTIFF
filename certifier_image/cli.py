from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import native, state
from .paths import prepare_pipeline
from .pipeline import run_action, run_interactive_flow
from .utils import check_dependencies


def usage() -> None:
    print("Usage: python run.py [options] [action] base_dir image1.png [image2.png ...] [exif_date]")
    print("Actions : visible, exif, stegano, signature, blockchain,")
    print("          check_stegano, check_signature, check_blockchain, show_exif, report, pipeline")
    print("Options :")
    print("  -i, --interactive            : mode interactif (defaut)")
    print("  --no-interactive             : mode automatique, sans questions")
    print("  --wm-mode skip|manual|auto")
    print('  --wm-text "texte"')
    print("  --wm-spacing N")
    print("  --wm-size N")
    print("  --wm-opacity 0.x")
    print('  --wm-color "R,G,B"')
    print("  --wm-angle N")
    print('  --wm-font "NomPolice"')
    print('  --stegano-message "texte"')
    print("  --check")


def looks_like_exif_date(value: str) -> bool:
    return ":" in value and not Path(value).is_file()


def parse_pipeline_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pipeline complet de protection d'image, equivalent Python de script_api.sh",
        add_help=True,
    )
    parser.add_argument(
        "-i",
        "--interactive",
        dest="interactive",
        action="store_true",
        default=state.MODE_INTERACTIVE,
        help="mode interactif (defaut)",
    )
    parser.add_argument(
        "--no-interactive",
        dest="interactive",
        action="store_false",
        help="mode automatique, sans questions",
    )
    parser.add_argument("--wm-mode", choices=("skip", "manual", "auto"), default=state.WM_MODE)
    parser.add_argument("--wm-text", default=state.WM_TEXT)
    parser.add_argument("--wm-spacing", type=int, default=state.WM_SPACING)
    parser.add_argument("--wm-size", type=int, default=state.WM_POINTSIZE)
    parser.add_argument("--wm-opacity", type=float, default=state.WM_OPACITY)
    parser.add_argument("--wm-color", default=state.WM_COLOR)
    parser.add_argument("--wm-angle", type=float, default=state.WM_ANGLE)
    parser.add_argument("--wm-font", default=state.WM_FONT)
    parser.add_argument("--stegano-message", default=state.MESSAGE)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("items", nargs="*")
    return parser.parse_args(argv)


def configure_from_args(args: argparse.Namespace) -> bool:

    state.MODE_INTERACTIVE = args.interactive
    state.WM_MODE = args.wm_mode
    state.WM_TEXT = args.wm_text
    state.WM_SPACING = args.wm_spacing
    state.WM_POINTSIZE = args.wm_size
    state.WM_OPACITY = args.wm_opacity
    state.WM_COLOR = args.wm_color
    state.WM_TEXT_COLOR = args.wm_color
    state.WM_ANGLE = args.wm_angle
    state.WM_FONT = args.wm_font
    state.MESSAGE = args.stegano_message

    if args.check:
        return check_dependencies()

    items = list(args.items)
    if items and items[0] in state.KNOWN_ACTIONS:
        state.ACTION = items.pop(0)
    else:
        state.ACTION = "pipeline"

    if len(items) == 1:
        state.BASE_DIR = Path(".")
        state.INPUT_IMGS = [Path(items[0])]
        state.EXIF_CUSTOM_DATE = None
    elif len(items) >= 2:
        state.BASE_DIR = Path(items[0])
        image_items = items[1:]
        if len(image_items) >= 2 and looks_like_exif_date(image_items[-1]):
            state.EXIF_CUSTOM_DATE = image_items.pop()
        else:
            state.EXIF_CUSTOM_DATE = None

        state.INPUT_IMGS = [Path(item) for item in image_items]
        if not state.INPUT_IMGS:
            usage()
            return False
    else:
        usage()
        return False

    state.INPUT_IMG = state.INPUT_IMGS[0]
    return True


def run_for_current_image() -> bool:
    if not prepare_pipeline():
        return False

    if not check_dependencies(state.ACTION):
        return False

    if state.MODE_INTERACTIVE and state.ACTION == "pipeline":
        return run_interactive_flow()

    return run_action()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] in state.LEGACY_ACTIONS:
        return 0 if native.run_legacy_command(argv) else 1

    args = parse_pipeline_args(argv)
    configured = configure_from_args(args)
    if args.check:
        return 0 if configured else 1
    if not configured:
        return 1

    ok = True
    for index, image in enumerate(state.INPUT_IMGS, start=1):
        state.INPUT_IMG = image
        if len(state.INPUT_IMGS) > 1:
            print()
            print(f"=== Image {index}/{len(state.INPUT_IMGS)} : {image} ===")
        ok = run_for_current_image() and ok

    return 0 if ok else 1
