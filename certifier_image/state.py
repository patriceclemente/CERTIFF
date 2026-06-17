from __future__ import annotations

import os
import tempfile
from pathlib import Path


MODE_INTERACTIVE = True
WM_MODE = "auto"

PLACE_MODE = "all"
WM_TEXT = "\u00a9 Cert-Art.fr"
WM_TEXT_COLOR = "128,128,128"
WM_SPACING = 300
WM_POINTSIZE = 35
WM_OPACITY = 0.2
WM_COLOR = "128,128,128"
WM_ANGLE = -45
WM_FONT = "Arial-Bold"
WM_STROKE_COLOR = "0,0,0"
WM_STROKE_WIDTH = 0.2

MESSAGE = "defaut"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
OPENSTEGO_JAR = PROJECT_DIR / "openstego.jar"
EXIFTOOL_BIN = "exiftool"
OTS_BIN = "ots"
DEFAULT_PW = "defaut"

ACTION = "pipeline"
BASE_DIR = Path(".")
STORAGE_DIR = None
INPUT_IMG = None
EXIF_CUSTOM_DATE = None
STATE_FILE = Path(os.environ.get("STATE_FILE", Path(tempfile.gettempdir()) / "last_img.txt"))

INPUT_IMG_PATH = None
IMG_BASE = ""
IMG_EXT = ""

WATERMARK_VISIBLE_DIR = None
WATERMARK_INVISIBLE_DIR = None
SIGNATURES_DIR = None
NUM_SIGNATURE_DIR = None

WM_VISIBLE_SUBDIR = None
WM_INVISIBLE_SUBDIR = None
WM_SIGNATURE_SUBDIR = None
WM_NUM_SIGNATURE_SUBDIR = None

FILE_WM_VISIBLE = None
FILE_WM_EXIF = None
FILE_WM_INVISIBLE = None
FILE_NUM_SIGNED = None
SIG_FILE = None

EXIF_DATE = None
EXIF_ARTIST = "\u00a9 Cert-Art.fr"
EXIF_COPYRIGHT = "\u00a9 Cert-Art.fr"

KNOWN_ACTIONS = {
    "visible",
    "exif",
    "stegano",
    "signature",
    "blockchain",
    "check_stegano",
    "check_signature",
    "check_blockchain",
    "show_exif",
    "report",
    "pipeline",
}

LEGACY_ACTIONS = {
    "convert",
    "filigrane_invisible",
    "signature_hash",
    "signature_verif",
    "lecture_filigrane_invisible",
}
