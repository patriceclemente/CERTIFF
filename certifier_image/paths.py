from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from . import state
from .utils import ensure_dir, run_command


def prepare_input_image() -> bool:

    if state.INPUT_IMG is None:
        print("[ERROR] Image non specifiee.")
        return False

    source = Path(state.INPUT_IMG)
    if not source.is_file():
        print(f"[ERROR] Image source introuvable : {source}")
        return False

    raw_base = source.stem
    input_dir = state.BASE_DIR / "images_brutes"
    input_img_subdir = input_dir / raw_base

    print(f"DEBUG: INPUT_IMG_SUBDIR='{input_img_subdir}'")
    if not ensure_dir(input_img_subdir):
        return False

    dest_png = input_img_subdir / f"{raw_base}.png"
    src_ext_lc = source.suffix.lower().lstrip(".")

    if src_ext_lc == "png":
        try:
            same_file = source.resolve() == dest_png.resolve()
        except OSError:
            same_file = False

        if same_file:
            state.INPUT_IMG_PATH = source
        else:
            if not dest_png.exists():
                shutil.copy2(source, dest_png)
            state.INPUT_IMG_PATH = dest_png
    else:
        if dest_png.exists():
            print(f"[INFO] Fichier PNG deja present : {dest_png} (conversion sautee)")
            state.INPUT_IMG_PATH = dest_png
        else:
            print("[INFO] Conversion en PNG :")
            print(f"       source : {source}")
            print(f"       dest   : {dest_png}")
            try:
                run_command(
                    [
                        "magick",
                        str(source),
                        "-strip",
                        "-colorspace",
                        "sRGB",
                        str(dest_png),
                    ]
                )
            except FileNotFoundError:
                print("[ERROR] 'magick' introuvable. Installer ImageMagick.")
                return False
            except subprocess.CalledProcessError:
                print(f"[ERROR] Conversion de {source} vers PNG echouee.")
                return False

            if not dest_png.is_file():
                print(f"[ERROR] Fichier PNG non cree : {dest_png}")
                return False

            state.INPUT_IMG_PATH = dest_png
            print(f"[OK] Conversion terminee : {state.INPUT_IMG_PATH}")

    state.IMG_BASE = state.INPUT_IMG_PATH.stem
    state.IMG_EXT = state.INPUT_IMG_PATH.suffix.lstrip(".")
    print()
    print(f"INPUT_IMG_PATH = {state.INPUT_IMG_PATH}")
    print()
    return True


def prepare_pipeline_paths() -> bool:

    state.WATERMARK_VISIBLE_DIR = state.BASE_DIR / "watermark-filigrane-visible"
    state.WATERMARK_INVISIBLE_DIR = state.BASE_DIR / "watermark-filigrane-invisible"
    state.SIGNATURES_DIR = state.BASE_DIR / "watermark-signatures"
    state.NUM_SIGNATURE_DIR = state.BASE_DIR / "watermark-signature_num\u00e9rique"

    state.WM_VISIBLE_SUBDIR = state.WATERMARK_VISIBLE_DIR / state.IMG_BASE
    state.WM_INVISIBLE_SUBDIR = state.WATERMARK_INVISIBLE_DIR / state.IMG_BASE
    state.WM_SIGNATURE_SUBDIR = state.SIGNATURES_DIR / state.IMG_BASE
    state.WM_NUM_SIGNATURE_SUBDIR = state.NUM_SIGNATURE_DIR / state.IMG_BASE

    for directory in (
        state.WM_VISIBLE_SUBDIR,
        state.WM_INVISIBLE_SUBDIR,
        state.WM_SIGNATURE_SUBDIR,
        state.WM_NUM_SIGNATURE_SUBDIR,
    ):
        if not ensure_dir(directory):
            return False

    state.FILE_WM_VISIBLE = state.WM_VISIBLE_SUBDIR / f"{state.IMG_BASE}-watermarked.{state.IMG_EXT}"
    state.FILE_WM_EXIF = state.WM_VISIBLE_SUBDIR / f"{state.IMG_BASE}-watermarked_exif.{state.IMG_EXT}"
    state.FILE_WM_INVISIBLE = state.WM_INVISIBLE_SUBDIR / f"{state.IMG_BASE}-watermarked_exif-openstego.{state.IMG_EXT}"
    state.FILE_NUM_SIGNED = state.WM_NUM_SIGNATURE_SUBDIR / f"{state.IMG_BASE}-watermarked_exif-openstego-num_signed.{state.IMG_EXT}"
    state.SIG_FILE = state.WM_SIGNATURE_SUBDIR / "bleu-pastel.sig"
    state.EXIF_DATE = state.EXIF_CUSTOM_DATE or datetime.now().strftime("%Y:%m:%d %H:%M:%S")
    return True


def prepare_pipeline() -> bool:
    return prepare_input_image() and prepare_pipeline_paths()

