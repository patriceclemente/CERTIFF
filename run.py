from __future__ import annotations

import argparse
import getpass
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


# -------------------------------------------------------
# Parametres par defaut, equivalents a script_api.sh
# -------------------------------------------------------
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
PROJECT_DIR = SCRIPT_DIR
OPENSTEGO_JAR = PROJECT_DIR / "openstego.jar"
EXIFTOOL_BIN = "exiftool"
OTS_BIN = "ots"
DEFAULT_PW = "defaut"

ACTION = "pipeline"
BASE_DIR = Path(".")
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


# -------------------------------------------------------
# Fonctions utilitaires
# -------------------------------------------------------
def ensure_dir(directory: str | Path | None) -> bool:
    if not directory:
        print("[WARN] ensure_dir: chemin vide")
        return False

    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        print(f"[ERROR] Impossible de creer le dossier : '{directory}'")
        return False


def command_exists(command: str) -> bool:
    if Path(command).is_file():
        return True
    return shutil.which(command) is not None


def resolve_exiftool_bin() -> str:
    if shutil.which(EXIFTOOL_BIN):
        return EXIFTOOL_BIN

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        installed_exiftool = Path(local_appdata) / "Programs" / "ExifTool" / "ExifTool.exe"
        if installed_exiftool.is_file():
            return str(installed_exiftool)

    return EXIFTOOL_BIN


def dependencies_for_action(action: str | None = None) -> tuple[list[tuple[str, str]], bool]:
    if action is None or action in {"pipeline", "report"}:
        return (
            [
                (resolve_exiftool_bin(), "exiftool"),
                ("java", "openjdk"),
                (OTS_BIN, "opentimestamps-client"),
                ("magick", "imagemagick"),
            ],
            True,
        )

    commands = []
    needs_openstego = False

    if action == "visible":
        commands.append(("magick", "imagemagick"))
    elif action in {"exif", "show_exif"}:
        commands.append((resolve_exiftool_bin(), "exiftool"))
    elif action in {"stegano", "signature", "check_stegano", "check_signature"}:
        commands.append(("java", "openjdk"))
        needs_openstego = True
    elif action in {"blockchain", "check_blockchain"}:
        commands.append((OTS_BIN, "opentimestamps-client"))

    if INPUT_IMG and Path(INPUT_IMG).suffix.lower() != ".png":
        commands.append(("magick", "imagemagick"))

    return commands, needs_openstego


def check_dependencies(action: str | None = None) -> bool:
    print("[INFO] Verification des dependances...")
    ok = True
    commands, needs_openstego = dependencies_for_action(action)

    for command, package in dict(commands).items():
        if not command_exists(command):
            print(f"[WARN] Commande '{command}' introuvable. Installer {package}.")
            ok = False

    if needs_openstego and not Path(OPENSTEGO_JAR).is_file():
        print(f"[WARN] OpenStego JAR introuvable : {OPENSTEGO_JAR}")
        ok = False

    if ok:
        print("[OK] Dependances pretes")
    return ok


def run_command(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, **kwargs)


def imagemagick_has_font(font_name: str) -> bool:
    try:
        result = subprocess.run(
            ["magick", "-list", "font"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

    font_line = f"Font: {font_name}"
    return any(line.strip() == font_line for line in result.stdout.splitlines())


def get_imagemagick_font_option() -> list[str]:
    if not WM_FONT:
        return []

    if imagemagick_has_font(WM_FONT):
        return ["-font", WM_FONT]

    print(f"[WARN] Police ImageMagick introuvable : {WM_FONT}. Police par defaut utilisee.")
    return []


def first_existing(paths: list[str | Path | None]) -> Path | None:
    for path in paths:
        if path and Path(path).is_file():
            return Path(path)
    return None


def latest_pipeline_file() -> Path | None:
    return first_existing(
        [
            FILE_NUM_SIGNED,
            FILE_WM_INVISIBLE,
            FILE_WM_EXIF,
            FILE_WM_VISIBLE,
            INPUT_IMG_PATH,
        ]
    )


def explain_source_fallback(step_name: str, source: Path, preferred: str | Path | None) -> None:
    if preferred and source == Path(preferred):
        return
    print(f"[INFO] {step_name}: utilisation de {source} comme entree")


def usage() -> None:
    print("Usage: python page_python.py [options] [action] base_dir image.png [exif_date]")
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
        default=MODE_INTERACTIVE,
        help="mode interactif (defaut)",
    )
    parser.add_argument(
        "--no-interactive",
        dest="interactive",
        action="store_false",
        help="mode automatique, sans questions",
    )
    parser.add_argument("--wm-mode", choices=("skip", "manual", "auto"), default=WM_MODE)
    parser.add_argument("--wm-text", default=WM_TEXT)
    parser.add_argument("--wm-spacing", type=int, default=WM_SPACING)
    parser.add_argument("--wm-size", type=int, default=WM_POINTSIZE)
    parser.add_argument("--wm-opacity", type=float, default=WM_OPACITY)
    parser.add_argument("--wm-color", default=WM_COLOR)
    parser.add_argument("--wm-angle", type=float, default=WM_ANGLE)
    parser.add_argument("--wm-font", default=WM_FONT)
    parser.add_argument("--stegano-message", default=MESSAGE)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("items", nargs="*")
    return parser.parse_args(argv)


def configure_from_args(args: argparse.Namespace) -> bool:
    global ACTION, BASE_DIR, EXIF_CUSTOM_DATE, INPUT_IMG
    global MESSAGE, MODE_INTERACTIVE, WM_ANGLE, WM_COLOR, WM_FONT, WM_MODE
    global WM_OPACITY, WM_POINTSIZE, WM_SPACING, WM_TEXT, WM_TEXT_COLOR

    MODE_INTERACTIVE = args.interactive
    WM_MODE = args.wm_mode
    WM_TEXT = args.wm_text
    WM_SPACING = args.wm_spacing
    WM_POINTSIZE = args.wm_size
    WM_OPACITY = args.wm_opacity
    WM_COLOR = args.wm_color
    WM_TEXT_COLOR = args.wm_color
    WM_ANGLE = args.wm_angle
    WM_FONT = args.wm_font
    MESSAGE = args.stegano_message

    if args.check:
        return check_dependencies()

    items = list(args.items)
    if items and items[0] in KNOWN_ACTIONS:
        ACTION = items.pop(0)
    else:
        ACTION = "pipeline"

    if len(items) == 1:
        BASE_DIR = Path(".")
        INPUT_IMG = Path(items[0])
        EXIF_CUSTOM_DATE = None
    elif len(items) >= 2:
        BASE_DIR = Path(items[0])
        INPUT_IMG = Path(items[1])
        EXIF_CUSTOM_DATE = items[2] if len(items) >= 3 else None
    else:
        usage()
        return False

    return True


# -------------------------------------------------------
# Preparation des chemins du pipeline
# -------------------------------------------------------
def prepare_input_image() -> bool:
    global IMG_BASE, IMG_EXT, INPUT_IMG_PATH

    if INPUT_IMG is None:
        print("[ERROR] Image non specifiee.")
        return False

    source = Path(INPUT_IMG)
    if not source.is_file():
        print(f"[ERROR] Image source introuvable : {source}")
        return False

    raw_base = source.stem
    input_dir = BASE_DIR / "images_brutes"
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
            INPUT_IMG_PATH = source
        else:
            if not dest_png.exists():
                shutil.copy2(source, dest_png)
            INPUT_IMG_PATH = dest_png
    else:
        if dest_png.exists():
            print(f"[INFO] Fichier PNG deja present : {dest_png} (conversion sautee)")
            INPUT_IMG_PATH = dest_png
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

            INPUT_IMG_PATH = dest_png
            print(f"[OK] Conversion terminee : {INPUT_IMG_PATH}")

    IMG_BASE = INPUT_IMG_PATH.stem
    IMG_EXT = INPUT_IMG_PATH.suffix.lstrip(".")
    print()
    print(f"INPUT_IMG_PATH = {INPUT_IMG_PATH}")
    print()
    return True


def prepare_pipeline_paths() -> bool:
    global EXIF_DATE, FILE_NUM_SIGNED, FILE_WM_EXIF, FILE_WM_INVISIBLE
    global FILE_WM_VISIBLE, NUM_SIGNATURE_DIR, SIG_FILE, SIGNATURES_DIR
    global WATERMARK_INVISIBLE_DIR, WATERMARK_VISIBLE_DIR
    global WM_INVISIBLE_SUBDIR, WM_NUM_SIGNATURE_SUBDIR, WM_SIGNATURE_SUBDIR
    global WM_VISIBLE_SUBDIR

    WATERMARK_VISIBLE_DIR = BASE_DIR / "watermark-filigrane-visible"
    WATERMARK_INVISIBLE_DIR = BASE_DIR / "watermark-filigrane-invisible"
    SIGNATURES_DIR = BASE_DIR / "watermark-signatures"
    NUM_SIGNATURE_DIR = BASE_DIR / "watermark-signature_num\u00e9rique"

    WM_VISIBLE_SUBDIR = WATERMARK_VISIBLE_DIR / IMG_BASE
    WM_INVISIBLE_SUBDIR = WATERMARK_INVISIBLE_DIR / IMG_BASE
    WM_SIGNATURE_SUBDIR = SIGNATURES_DIR / IMG_BASE
    WM_NUM_SIGNATURE_SUBDIR = NUM_SIGNATURE_DIR / IMG_BASE

    for directory in (
        WM_VISIBLE_SUBDIR,
        WM_INVISIBLE_SUBDIR,
        WM_SIGNATURE_SUBDIR,
        WM_NUM_SIGNATURE_SUBDIR,
    ):
        if not ensure_dir(directory):
            return False

    FILE_WM_VISIBLE = WM_VISIBLE_SUBDIR / f"{IMG_BASE}-watermarked.{IMG_EXT}"
    FILE_WM_EXIF = WM_VISIBLE_SUBDIR / f"{IMG_BASE}-watermarked_exif.{IMG_EXT}"
    FILE_WM_INVISIBLE = WM_INVISIBLE_SUBDIR / f"{IMG_BASE}-watermarked_exif-openstego.{IMG_EXT}"
    FILE_NUM_SIGNED = WM_NUM_SIGNATURE_SUBDIR / f"{IMG_BASE}-watermarked_exif-openstego-num_signed.{IMG_EXT}"
    SIG_FILE = WM_SIGNATURE_SUBDIR / "bleu-pastel.sig"
    EXIF_DATE = EXIF_CUSTOM_DATE or datetime.now().strftime("%Y:%m:%d %H:%M:%S")
    return True


def prepare_pipeline() -> bool:
    return prepare_input_image() and prepare_pipeline_paths()


# -------------------------------------------------------
# Fonctions pipeline
# -------------------------------------------------------
def run_filigrane_visible_manual() -> bool:
    if not ensure_dir(WM_VISIBLE_SUBDIR):
        return False

    print("=== Filigrane visible (manuel) ===")
    try:
        shutil.copy2(INPUT_IMG_PATH, FILE_WM_VISIBLE)
    except OSError as error:
        print(f"[ERROR] Impossible de copier l'image : {error}")
        return False

    input(f"Creer filigrane visible avec Watermarkly sur {FILE_WM_VISIBLE}, puis Entree...")
    return True


def run_filigrane_visible_auto() -> bool:
    global PLACE_MODE, WM_ANGLE, WM_OPACITY, WM_POINTSIZE, WM_SPACING
    global WM_STROKE_COLOR, WM_STROKE_WIDTH, WM_TEXT, WM_TEXT_COLOR

    if not ensure_dir(WM_VISIBLE_SUBDIR):
        return False

    print("=== Filigrane visible (IMv7 compatible) ===")

    if MODE_INTERACTIVE:
        value = input(f"Texte du watermark [defaut: {WM_TEXT}] : ")
        WM_TEXT = value or WM_TEXT

        value = input(f"Taille police (pt) [defaut: {WM_POINTSIZE}] : ")
        WM_POINTSIZE = int(value or WM_POINTSIZE)

        value = input(f"Couleur texte R,G,B [defaut: {WM_TEXT_COLOR}] : ")
        WM_TEXT_COLOR = value or WM_TEXT_COLOR

        value = input(f"Couleur contour R,G,B [defaut: {WM_STROKE_COLOR}] : ")
        WM_STROKE_COLOR = value or WM_STROKE_COLOR

        value = input(f"Epaisseur contour (px) [defaut: {WM_STROKE_WIDTH}] : ")
        WM_STROKE_WIDTH = float(value or WM_STROKE_WIDTH)

        value = input(f"Opacite (0-1) [defaut: {WM_OPACITY}] : ")
        WM_OPACITY = float(value or WM_OPACITY)

        value = input(f"Angle [defaut: {WM_ANGLE}] : ")
        WM_ANGLE = float(value or WM_ANGLE)

        value = input(f"Espacement entre watermarks (px) [defaut: {WM_SPACING}] : ")
        WM_SPACING = int(value or WM_SPACING)

        value = input("Placement : coins (c) / partout (p) [defaut: partout] : ")
        PLACE_MODE = "corners" if value.lower() == "c" else "all"

    tmp_text = WM_VISIBLE_SUBDIR / "wm_text.txt"
    tmp_wm = WM_VISIBLE_SUBDIR / "wm_label.png"
    tmp_text.write_text(WM_TEXT, encoding="utf-8")

    angle = 0 if PLACE_MODE == "corners" else WM_ANGLE
    fill_color = f"rgba({WM_TEXT_COLOR},{WM_OPACITY})"
    stroke_color = f"rgb({WM_STROKE_COLOR})"

    command = [
        "magick",
        "-size",
        f"{WM_SPACING}x{WM_SPACING}",
        "-background",
        "none",
        "-fill",
        fill_color,
        "-stroke",
        stroke_color,
        "-strokewidth",
        str(WM_STROKE_WIDTH),
        "-pointsize",
        str(WM_POINTSIZE),
        "-gravity",
        "center",
    ]
    command.extend(get_imagemagick_font_option())
    command.extend([f"label:@{tmp_text}", "-rotate", str(angle), str(tmp_wm)])

    try:
        run_command(command)

        if PLACE_MODE == "all":
            dimensions = run_command(
                ["magick", "identify", "-format", "%wx%h", str(INPUT_IMG_PATH)],
                capture_output=True,
                text=True,
            ).stdout
            run_command(
                [
                    "magick",
                    str(INPUT_IMG_PATH),
                    "-size",
                    dimensions,
                    f"tile:{tmp_wm}",
                    "-compose",
                    "over",
                    "-composite",
                    str(FILE_WM_VISIBLE),
                ]
            )
        else:
            command = ["magick", str(INPUT_IMG_PATH)]
            for gravity in ("northwest", "northeast", "southwest", "southeast"):
                command.extend(
                    [
                        "(",
                        str(tmp_wm),
                        "-geometry",
                        "+10+10",
                        ")",
                        "-gravity",
                        gravity,
                        "-composite",
                    ]
                )
            command.append(str(FILE_WM_VISIBLE))
            run_command(command)
    except FileNotFoundError:
        print("[ERROR] ImageMagick est introuvable")
        return False
    except subprocess.CalledProcessError as error:
        print(f"[ERROR] Echec ImageMagick : {error}")
        return False
    finally:
        tmp_text.unlink(missing_ok=True)
        tmp_wm.unlink(missing_ok=True)

    print(f"[OK] Filigrane applique sur {FILE_WM_VISIBLE}")
    return True


def run_exif() -> bool:
    global EXIF_DATE

    if not ensure_dir(WM_VISIBLE_SUBDIR):
        return False

    print("=== Ajout des metadonnees EXIF ===")
    source_file = first_existing([FILE_WM_VISIBLE, INPUT_IMG_PATH])
    if not source_file:
        print("[WARN] Image source introuvable, saut EXIF")
        return False
    explain_source_fallback("EXIF", source_file, FILE_WM_VISIBLE)

    current_date = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
    if MODE_INTERACTIVE:
        value = input(
            f"Date/heure EXIF (YYYY:mm:dd HH:MM:SS) [defaut: {current_date}] : "
        )
        EXIF_DATE = value or current_date
    else:
        EXIF_DATE = EXIF_CUSTOM_DATE or current_date

    try:
        shutil.copy2(source_file, FILE_WM_EXIF)
        run_command(
            [
                resolve_exiftool_bin(),
                "-overwrite_original",
                f"-DateTimeOriginal={EXIF_DATE}",
                f"-CreateDate={EXIF_DATE}",
                f"-ImageUniqueID={EXIF_DATE}:001",
                "-Creator=\u00a9 Cert-Art.fr",
                "-Artist=\u00a9 Cert-Art.fr",
                "-Copyright=\u00a9 Cert-Art.fr",
                str(FILE_WM_EXIF),
            ]
        )
    except FileNotFoundError:
        print("[ERROR] exiftool est introuvable")
        return False
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"[ERROR] Impossible d'ajouter les metadonnees EXIF : {error}")
        return False

    print(f"[OK] Metadonnees EXIF ajoutees sur {FILE_WM_EXIF}")
    return True


def run_stegano() -> bool:
    global MESSAGE

    ensure_dir(WM_INVISIBLE_SUBDIR)
    ensure_dir(WM_SIGNATURE_SUBDIR)

    print("=== Filigrane invisible (steganographie) ===")
    carrier_file = first_existing([FILE_WM_EXIF, FILE_WM_VISIBLE, INPUT_IMG_PATH])
    if not carrier_file:
        print("[WARN] Image source introuvable, saut steganographie")
        return False
    explain_source_fallback("Steganographie", carrier_file, FILE_WM_EXIF)

    if MODE_INTERACTIVE:
        value = input(f"Message a cacher [defaut: {MESSAGE}] : ")
        MESSAGE = value or MESSAGE

        value = input("Voulez-vous saisir un mot de passe pour le filigrane invisible ? (y/n) [n] : ")
        if value.lower() == "y":
            password = getpass.getpass("Mot de passe : ")
        else:
            password = MESSAGE
    else:
        password = MESSAGE

    msg_file = WM_SIGNATURE_SUBDIR / "signature.txt"
    pw_file = WM_SIGNATURE_SUBDIR / "pw.txt"
    msg_file.write_text(MESSAGE, encoding="utf-8")
    pw_file.write_text(password, encoding="utf-8")

    print(f"[DEBUG] Mot de passe utilise : {password}")
    print(f"[INFO] Fichier message cree dans : {msg_file}")
    print(f"[DEBUG] Mot de passe sauvegarde dans : {pw_file}")

    try:
        run_command(
            [
                "java",
                "-jar",
                str(OPENSTEGO_JAR),
                "embed",
                "-mf",
                str(msg_file),
                "-cf",
                str(carrier_file),
                "-sf",
                str(FILE_WM_INVISIBLE),
                "-p",
                password,
            ]
        )
    except FileNotFoundError:
        print("[ERROR] java est introuvable")
        return False
    except subprocess.CalledProcessError as error:
        print(f"[ERROR] Echec OpenStego embed : {error}")
        return False

    print(f"[OK] Filigrane invisible applique : {FILE_WM_INVISIBLE}")
    return True


def run_signature() -> bool:
    ensure_dir(WM_NUM_SIGNATURE_SUBDIR)
    ensure_dir(WM_SIGNATURE_SUBDIR)
    print("=== Signature numerique ===")

    carrier_file = first_existing([FILE_WM_INVISIBLE, FILE_WM_EXIF, FILE_WM_VISIBLE, INPUT_IMG_PATH])
    if not carrier_file:
        print("[WARN] Image source introuvable, saut signature")
        return False
    explain_source_fallback("Signature", carrier_file, FILE_WM_INVISIBLE)

    ensure_dir(SIG_FILE.parent)
    if not Path(SIG_FILE).is_file():
        sig_pwd = f"{IMG_BASE}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        print(f"[INFO] Mot de passe genere automatiquement : {sig_pwd}")

        if MODE_INTERACTIVE:
            want_pwd = input("Voulez-vous saisir un mot de passe personnalise ? (y/n) [n] : ") or "n"
            if want_pwd.lower() == "y":
                sig_pwd = getpass.getpass("Entrer mot de passe : ")
                sig_pwd2 = getpass.getpass("Confirmer mot de passe : ")
                if sig_pwd != sig_pwd2:
                    print("[ERROR] Les mots de passe ne correspondent pas")
                    return False

        try:
            run_command(
                ["java", "-jar", str(OPENSTEGO_JAR), "gensig", "-gf", str(SIG_FILE)],
                input=f"{sig_pwd}\n{sig_pwd}\n",
                text=True,
            )
        except FileNotFoundError:
            print("[ERROR] java est introuvable")
            return False
        except subprocess.CalledProcessError as error:
            print(f"[ERROR] Echec OpenStego gensig : {error}")
            return False

        if not Path(SIG_FILE).is_file():
            print(f"[ERROR] La signature n'a pas ete creee : {SIG_FILE}")
            return False
        print(f"[OK] Fichier de signature cree : {SIG_FILE}")
    else:
        print(f"[INFO] Fichier de signature deja present : {SIG_FILE}")

    try:
        run_command(
            [
                "java",
                "-jar",
                str(OPENSTEGO_JAR),
                "embedmark",
                "-gf",
                str(SIG_FILE),
                "-cf",
                str(carrier_file),
                "-sf",
                str(FILE_NUM_SIGNED),
            ]
        )
    except FileNotFoundError:
        print("[ERROR] java est introuvable")
        return False
    except subprocess.CalledProcessError as error:
        print(f"[ERROR] Echec OpenStego embedmark : {error}")
        return False

    print(f"[OK] Signature appliquee sur {FILE_NUM_SIGNED}")
    return True


def run_blockchain() -> bool:
    print("=== Enregistrement sur la blockchain ===")
    target_file = first_existing([FILE_NUM_SIGNED, FILE_WM_INVISIBLE, FILE_WM_EXIF, FILE_WM_VISIBLE, INPUT_IMG_PATH])
    if not target_file:
        print("[WARN] Aucun fichier image disponible, saut blockchain")
        return False
    explain_source_fallback("Blockchain", target_file, FILE_NUM_SIGNED)

    try:
        run_command([OTS_BIN, "stamp", str(target_file)])
    except FileNotFoundError:
        print(f"[ERROR] Commande '{OTS_BIN}' introuvable")
        return False
    except subprocess.CalledProcessError as error:
        print(f"[ERROR] Echec blockchain : {error}")
        return False

    print(f"[OK] Blockchain : {target_file}")
    return True


# -------------------------------------------------------
# Fonctions verification
# -------------------------------------------------------
def check_stegano() -> bool:
    print("=== Verification du filigrane invisible ===")
    if not Path(FILE_WM_INVISIBLE).is_file():
        print("[INFO] Filigrane invisible : aucune info")
        return False

    pw_file = WM_SIGNATURE_SUBDIR / "pw.txt"
    if not pw_file.is_file():
        print(f"[WARN] Mot de passe introuvable ({pw_file}), impossible de verifier")
        return False

    password = pw_file.read_text(encoding="utf-8")
    msg_file = WM_SIGNATURE_SUBDIR / "signature.txt"
    print(f'[INFO] Extraction avec -p "{password}" ...')

    try:
        run_command(
            [
                "java",
                "-jar",
                str(OPENSTEGO_JAR),
                "extract",
                "-sf",
                str(FILE_WM_INVISIBLE),
                "-p",
                password,
            ]
        )
    except FileNotFoundError:
        print("[ERROR] java est introuvable")
        return False
    except subprocess.CalledProcessError as error:
        print(f"[ERROR] Echec OpenStego extract : {error}")
        return False

    if msg_file.is_file():
        print(f"[OK] Message extrait : {msg_file.read_text(encoding='utf-8')}")
    return True


def check_signature() -> bool:
    print("=== Verification de la signature numerique ===")
    if not Path(FILE_NUM_SIGNED).is_file():
        print("[INFO] Tatouage numerique : aucune info")
        return False

    try:
        run_command(
            [
                "java",
                "-jar",
                str(OPENSTEGO_JAR),
                "checkmark",
                "-gf",
                str(SIG_FILE),
                "-sf",
                str(FILE_NUM_SIGNED),
            ]
        )
    except FileNotFoundError:
        print("[ERROR] java est introuvable")
        return False
    except subprocess.CalledProcessError as error:
        print(f"[ERROR] Echec OpenStego checkmark : {error}")
        return False

    return True


def check_blockchain(ots_file: str | Path | None = None) -> bool:
    print("=== Verification sur la blockchain (mode distant) ===")

    if ots_file:
        target = Path(ots_file)
    else:
        stamped_file = latest_pipeline_file()
        if not stamped_file:
            print("[ERREUR] Aucun fichier image disponible pour retrouver une preuve .ots")
            return False
        target = Path(f"{stamped_file}.ots")

    if not target.is_file():
        print(f"[ERREUR] Fichier .ots introuvable : {target}")
        print("         Verifiez le chemin ou genereez d'abord le timestamp avec :")
        if ots_file:
            print(f'         ots stamp "{Path(ots_file).with_suffix("")}"')
        elif stamped_file:
            print(f'         ots stamp "{stamped_file}"')
        return False

    print("[OPTIONS Verif Blockchain]")
    print(f"  Fichier OTS : {target}")
    print(f"  Commande : {OTS_BIN}")
    print()
    print("[INFO] Verification du timestamp distant pour :")
    print(f"       {target}")
    print()

    print("[INFO] Verification initiale...")
    verify_out = subprocess.run(
        [OTS_BIN, "verify", str(target)],
        capture_output=True,
        text=True,
    )
    output = (verify_out.stdout or "") + (verify_out.stderr or "")

    if "Timestamped by transaction" in output:
        print(output, end="" if output.endswith("\n") else "\n")
        print("[OK] Timestamp completement confirme sur la blockchain.")
        return True

    print("[WARN] Verification initiale non confirmee.")
    print("[INFO] Details :")
    print("\n".join(output.splitlines()[:200]))
    print()

    if MODE_INTERACTIVE:
        choice = input("Souhaitez-vous mettre a jour la preuve OTS maintenant ? (y/n) [y] : ") or "y"
    else:
        choice = "y"

    if choice.lower() == "y":
        print("[INFO] Tentative de mise a jour de la preuve (upgrade)...")
        log_file = Path(tempfile.gettempdir()) / "ots_upgrade.log"
        with log_file.open("w", encoding="utf-8") as log:
            upgraded = subprocess.run(
                [OTS_BIN, "upgrade", str(target)],
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
        if upgraded.returncode == 0:
            print("[OK] Mise a jour effectuee avec succes.")
        else:
            print("[ERREUR] Echec de la mise a jour du fichier .ots")
            print(f"         Consultez {log_file} pour le detail.")
            return False
    else:
        print("[INFO] Mise a jour ignoree a la demande de l'utilisateur.")

    print()
    print("[INFO] Verification apres mise a jour...")
    verify_after = subprocess.run(
        [OTS_BIN, "verify", str(target)],
        capture_output=True,
        text=True,
    )
    output_after = (verify_after.stdout or "") + (verify_after.stderr or "")
    filtered_lines = [
        line
        for line in output_after.splitlines()
        if "Could not connect to Bitcoin node" not in line
        and "Cookie file unusable" not in line
        and "rpcpassword" not in line
    ]
    filtered_output = "\n".join(filtered_lines)
    print(filtered_output)

    if "Timestamped by transaction" in filtered_output:
        print("[OK] Timestamp completement confirme sur la blockchain.")
        return True
    if "PendingAttestation" in filtered_output:
        print("[WARN] Timestamp encore en attente de confirmation sur un ou plusieurs serveurs calendrier.")
        print("[INFO] Reessayez plus tard avec :")
        print(f'       ots upgrade "{target}"')
        print(f'       ots verify "{target}"')
        return False
    if "Assuming target filename" in filtered_output:
        print("[INFO] Le fichier est reconnu par ots mais aucune attestation n'est encore disponible.")
        print("[INFO] Reessayez dans quelques heures avec :")
        print(f'       ots upgrade "{target}"')
        return False

    print("[WARN] Impossible de determiner le statut exact.")
    print("[INFO] Consultez le contenu brut avec :")
    print(f'       ots info "{target}"')
    return False


def show_exif() -> bool:
    print("=== Affichage des metadonnees EXIF ===")
    target_file = first_existing([FILE_WM_EXIF, FILE_WM_VISIBLE, INPUT_IMG_PATH])
    if not target_file:
        print("[INFO] EXIF : aucun fichier disponible")
        return False
    explain_source_fallback("Affichage EXIF", target_file, FILE_WM_EXIF)

    try:
        run_command([resolve_exiftool_bin(), str(target_file)])
    except FileNotFoundError:
        print("[ERROR] exiftool est introuvable")
        return False
    except subprocess.CalledProcessError as error:
        print(f"[ERROR] Echec exiftool : {error}")
        return False

    return True


def report_final() -> bool:
    print("=== Rapport final (mode auto) ===")
    ok = True
    ok = check_stegano() and ok
    ok = check_signature() and ok
    ok = check_blockchain() and ok
    ok = show_exif() and ok
    return ok


def write_state(file_path: str | Path | None) -> None:
    if file_path and Path(file_path).is_file():
        ensure_dir(STATE_FILE.parent)
        STATE_FILE.write_text(str(file_path), encoding="utf-8")
        print(f"[STATE] Derniere image : {file_path}")


def run_visible_action() -> bool:
    if WM_MODE == "skip":
        print("[INFO] Etape filigrane visible sautee")
        return True
    if WM_MODE == "manual":
        return run_filigrane_visible_manual()
    if WM_MODE == "auto":
        return run_filigrane_visible_auto()

    print(f"[ERROR] WM_MODE inconnu : {WM_MODE}")
    return False


def run_action() -> bool:
    if ACTION == "visible":
        print("[ACTION] Watermark visible")
        ok = run_visible_action()
        if ok:
            write_state(FILE_WM_VISIBLE)
        return ok

    if ACTION == "exif":
        print("[ACTION] EXIF")
        ok = run_exif()
        if ok:
            write_state(FILE_WM_EXIF)
        return ok

    if ACTION == "stegano":
        print("[ACTION] Steganographie")
        ok = run_stegano()
        if ok:
            write_state(FILE_WM_INVISIBLE)
        return ok

    if ACTION == "signature":
        print("[ACTION] Signature numerique")
        ok = run_signature()
        if ok:
            write_state(FILE_NUM_SIGNED)
        return ok

    if ACTION == "blockchain":
        print("[ACTION] Blockchain")
        ok = run_blockchain()
        if ok:
            write_state(latest_pipeline_file())
        return ok

    if ACTION == "check_stegano":
        print("[ACTION] Verification steganographie")
        return check_stegano()

    if ACTION == "check_signature":
        print("[ACTION] Verification signature")
        return check_signature()

    if ACTION == "check_blockchain":
        print("[ACTION] Verification blockchain")
        return check_blockchain()

    if ACTION == "show_exif":
        print("[ACTION] Affichage EXIF")
        return show_exif()

    if ACTION == "report":
        print("[ACTION] Rapport final")
        return report_final()

    if ACTION == "pipeline":
        print(f"[ACTION] Pipeline complet pour {INPUT_IMG}")
        ok = run_visible_action()
        if ok:
            write_state(FILE_WM_VISIBLE)

        step_ok = run_exif()
        if step_ok:
            write_state(FILE_WM_EXIF)
        ok = step_ok and ok

        step_ok = run_stegano()
        if step_ok:
            write_state(FILE_WM_INVISIBLE)
        ok = step_ok and ok

        step_ok = run_signature()
        if step_ok:
            write_state(FILE_NUM_SIGNED)
        ok = step_ok and ok

        step_ok = run_blockchain()
        if step_ok:
            write_state(latest_pipeline_file())
        ok = step_ok and ok
        return ok

    print(f"Action inconnue : {ACTION}")
    print("Actions disponibles : " + ", ".join(sorted(KNOWN_ACTIONS)))
    return False


def run_interactive_flow() -> bool:
    print("=== Mode interactif ===")
    print("[INFO] Le mode interactif garde le comportement guide.")
    ok = True

    choice = input("Voulez-vous appliquer le filigrane visible ? (y/n) [n] : ")
    if choice.lower() == "y":
        step_ok = run_filigrane_visible_auto()
        if step_ok:
            write_state(FILE_WM_VISIBLE)
        ok = step_ok and ok

    choice = input("Voulez-vous ajouter les metadonnees EXIF ? (y/n) [n] : ")
    if choice.lower() == "y":
        step_ok = run_exif()
        if step_ok:
            write_state(FILE_WM_EXIF)
        ok = step_ok and ok

    choice = input("Voulez-vous appliquer le filigrane invisible (steganographie) ? (y/n) [n] : ")
    if choice.lower() == "y":
        step_ok = run_stegano()
        if step_ok:
            write_state(FILE_WM_INVISIBLE)
        ok = step_ok and ok

    choice = input("Voulez-vous signer numeriquement l'image ? (y/n) [n] : ")
    if choice.lower() == "y":
        step_ok = run_signature()
        if step_ok:
            write_state(FILE_NUM_SIGNED)
        ok = step_ok and ok

    choice = input("Voulez-vous enregistrer sur la blockchain ? (y/n) [n] : ")
    if choice.lower() == "y":
        step_ok = run_blockchain()
        if step_ok:
            write_state(latest_pipeline_file())
        ok = step_ok and ok

    print("=== Verifications interactives ===")

    choice = input("Voulez-vous afficher les metadonnees EXIF ? (y/n) [n] : ")
    if choice.lower() == "y":
        print("[OPTIONS Verif EXIF]")
        print(f"  Fichier : {FILE_WM_EXIF}")
        ok = show_exif() and ok

    choice = input("Voulez-vous verifier le filigrane invisible ? (y/n) [n] : ")
    if choice.lower() == "y":
        print("[OPTIONS Verif Steganographie]")
        print(f"  Fichier : {FILE_WM_INVISIBLE}")
        print(f"  Message attendu : {MESSAGE}")
        ok = check_stegano() and ok

    choice = input("Voulez-vous verifier la signature numerique ? (y/n) [n] : ")
    if choice.lower() == "y":
        print("[OPTIONS Verif Signature]")
        print(f"  Fichier : {FILE_NUM_SIGNED}")
        print(f"  Signature attendue : {SIG_FILE}")
        ok = check_signature() and ok

    choice = input("Voulez-vous verifier l'enregistrement sur la blockchain ? (y/n) [n] : ")
    if choice.lower() == "y":
        print("[OPTIONS Verif Blockchain]")
        print(f"  Fichier OTS : {FILE_NUM_SIGNED}.ots")
        print(f"  Commande : {OTS_BIN}")
        ok = check_blockchain() and ok

    return ok


# -------------------------------------------------------
# Fonctions Python natives deja presentes dans page_python.py
# -------------------------------------------------------
def convertir_en_png(chemin_entree: str, chemin_sortie: str | None = None) -> None:
    from PIL import Image

    input_path = Path(chemin_entree)
    if input_path.suffix.lower() == ".png":
        print("L'image est deja au format PNG.")
        return

    output_path = Path(chemin_sortie) if chemin_sortie else input_path.with_suffix(".png")
    with Image.open(input_path) as img:
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        img.save(output_path, format="PNG")
    print(f"Image sauvegardee : {output_path}")


def derive_key(password: str, salt: bytes) -> bytes:
    from Crypto.Protocol.KDF import PBKDF2

    return PBKDF2(password.encode(), salt, dkLen=32, count=100_000)


def chiffrer(message: str, password: str) -> bytes:
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes

    salt = get_random_bytes(16)
    nonce = get_random_bytes(12)
    key = derive_key(password, salt)

    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(message.encode("utf-8"))
    return salt + nonce + tag + ciphertext


def dechiffrer(data: bytes, password: str) -> str:
    from Crypto.Cipher import AES

    salt = data[:16]
    nonce = data[16:28]
    tag = data[28:44]
    ciphertext = data[44:]

    key = derive_key(password, salt)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    try:
        return cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8")
    except ValueError as error:
        raise ValueError("Mot de passe incorrect ou donnees corrompues.") from error


def bytes_en_bits(data: bytes):
    for byte in data:
        for i in range(7, -1, -1):
            yield (byte >> i) & 1


def cacher_message(image_path: str, message: str, password: str, output_path: str) -> None:
    from PIL import Image

    img = Image.open(image_path).convert("RGBA")
    pixels = list(img.getdata())
    payload = chiffrer(message, password)
    header = struct.pack(">I", len(payload))
    bits = list(bytes_en_bits(header + payload))

    capacite = len(pixels) * 3
    if len(bits) > capacite:
        raise ValueError(f"Image trop petite : capacite {capacite} bits, message necessite {len(bits)} bits.")

    nouveaux_pixels = []
    bit_idx = 0
    for r, g, b, a in pixels:
        canaux = [r, g, b]
        for i in range(3):
            if bit_idx < len(bits):
                canaux[i] = (canaux[i] & 0xFE) | bits[bit_idx]
                bit_idx += 1
        nouveaux_pixels.append((*canaux, a))

    img.putdata(nouveaux_pixels)
    img.save(output_path, format="PNG")
    print(f"[OK] Message cache dans '{output_path}' ({len(payload)} octets chiffres).")


def extraire_message(image_path: str, password: str) -> str:
    from PIL import Image

    img = Image.open(image_path).convert("RGBA")
    pixels = list(img.getdata())

    bits = []
    for r, g, b, _ in pixels:
        bits += [(r & 1), (g & 1), (b & 1)]

    def bits_en_bytes(bits_list, n_bytes):
        result = bytearray()
        for i in range(n_bytes):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | bits_list[i * 8 + j]
            result.append(byte)
        return bytes(result)

    taille = struct.unpack(">I", bits_en_bytes(bits, 4))[0]
    payload = bits_en_bytes(bits[32:], taille)
    return dechiffrer(payload, password)


def hash_image(image_path: str) -> bytes:
    from PIL import Image

    img = Image.open(image_path).convert("RGBA")
    return hashlib.sha256(bytes(img.tobytes())).digest()


def verif_sign(image_path: str, signature: bytes) -> bool:
    return hash_image(image_path) == signature


def parse_legacy_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Commandes Python natives historiques.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    convert_parser = subparsers.add_parser("convert", help="Convertir l'image en PNG")
    convert_parser.add_argument("--input", required=True)
    convert_parser.add_argument("--output")

    steg_parser = subparsers.add_parser("filigrane_invisible", help="Cacher un message chiffre dans une image")
    steg_parser.add_argument("--input", required=True)
    steg_parser.add_argument("--msg", required=True)
    steg_parser.add_argument("--password", required=True)
    steg_parser.add_argument("--output", required=True)

    signature_parser = subparsers.add_parser("signature_hash", help="Creer un hash de l'image")
    signature_parser.add_argument("--image", required=True)

    verif_parser = subparsers.add_parser("signature_verif", help="Verifier une signature hash")
    verif_parser.add_argument("--image", required=True)
    verif_parser.add_argument("--signature", required=True)

    read_parser = subparsers.add_parser("lecture_filigrane_invisible", help="Lire le filigrane invisible natif")
    read_parser.add_argument("--input", required=True)
    read_parser.add_argument("--password", required=True)

    return parser.parse_args(argv)


def run_legacy_command(argv: list[str]) -> bool:
    args = parse_legacy_args(argv)
    try:
        if args.command == "convert":
            convertir_en_png(args.input, args.output)
        elif args.command == "filigrane_invisible":
            cacher_message(args.input, args.msg, args.password, args.output)
        elif args.command == "signature_hash":
            print(hash_image(args.image).hex())
        elif args.command == "signature_verif":
            print(verif_sign(args.image, bytes.fromhex(args.signature)))
        elif args.command == "lecture_filigrane_invisible":
            print(extraire_message(args.input, args.password))
        else:
            return False
    except Exception as error:
        print(f"[ERROR] {error}")
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] in LEGACY_ACTIONS:
        return 0 if run_legacy_command(argv) else 1

    args = parse_pipeline_args(argv)
    configured = configure_from_args(args)
    if args.check:
        return 0 if configured else 1
    if not configured:
        return 1

    if not prepare_pipeline():
        return 1

    if not check_dependencies(ACTION):
        return 1

    if MODE_INTERACTIVE and ACTION == "pipeline":
        ok = run_interactive_flow()
    else:
        ok = run_action()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
