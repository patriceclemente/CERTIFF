from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import state


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
    if shutil.which(state.EXIFTOOL_BIN):
        return state.EXIFTOOL_BIN

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        installed_exiftool = Path(local_appdata) / "Programs" / "ExifTool" / "ExifTool.exe"
        if installed_exiftool.is_file():
            return str(installed_exiftool)

    return state.EXIFTOOL_BIN


def dependencies_for_action(action: str | None = None) -> tuple[list[tuple[str, str]], bool]:
    if action is None or action == "pipeline":
        return (
            [
                (resolve_exiftool_bin(), "exiftool"),
                ("java", "openjdk"),
                (state.OTS_BIN, "opentimestamps-client"),
                ("magick", "imagemagick"),
            ],
            True,
        )

    if action == "report":
        return (
            [
                (resolve_exiftool_bin(), "exiftool"),
                ("java", "openjdk"),
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
    elif action in {"stegano", "check_stegano"}:
        commands.append(("java", "openjdk"))
        needs_openstego = True
    elif action in {"blockchain", "check_blockchain"}:
        commands.append((state.OTS_BIN, "opentimestamps-client"))

    if state.INPUT_IMG and Path(state.INPUT_IMG).suffix.lower() != ".png":
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

    if needs_openstego and not Path(state.OPENSTEGO_JAR).is_file():
        print(f"[WARN] OpenStego JAR introuvable : {state.OPENSTEGO_JAR}")
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
    if not state.WM_FONT:
        return []

    if imagemagick_has_font(state.WM_FONT):
        return ["-font", state.WM_FONT]

    print(f"[WARN] Police ImageMagick introuvable : {state.WM_FONT}. Police par defaut utilisee.")
    return []


def first_existing(paths: list[str | Path | None]) -> Path | None:
    for path in paths:
        if path and Path(path).is_file():
            return Path(path)
    return None


def latest_pipeline_file() -> Path | None:
    return first_existing(
        [
            state.FILE_NUM_SIGNED,
            state.FILE_WM_INVISIBLE,
            state.FILE_WM_EXIF,
            state.FILE_WM_VISIBLE,
            state.INPUT_IMG_PATH,
        ]
    )


def explain_source_fallback(step_name: str, source: Path, preferred: str | Path | None) -> None:
    if preferred and source == Path(preferred):
        return
    print(f"[INFO] {step_name}: utilisation de {source} comme entree")

