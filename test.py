from pathlib import Path
from datetime import datetime
import shutil
import subprocess



#paramètres globaux

MODE_INTERACTIVE = False

PLACE_MODE = "all"

WM_TEXT="© Cert-Art.fr"
WM_TEXT_COLOR="128,128,128"
WM_SPACING=300
WM_POINTSIZE=35
WM_OPACITY=0.2
WM_COLOR="128,128,128"
WM_ANGLE=-45
WM_FONT="Arial-Bold"
WM_STROKE_COLOR="0,0,0"
WM_STROKE_WIDTH=0.2

EXIF_CUSTOM_DATE = None
EXIF_DATE = None


def ensure_dir(directory):
    if not directory:
        print("[WARN] ensure_dir: chemin vide")
        return False

    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        print(f"[ERROR] Impossible de créer le dossier : '{directory}'")
        return False


def run_filigrane_visible_manual(wm_visible_subdir, input_img_path, file_wm_visible):
    if not ensure_dir(wm_visible_subdir):
        return False
    
    print( "=== Filigrane visible (manuel) ===")

    try: 
        shutil.copy(input_img_path, file_wm_visible)
    except OSError as error:
        print(f"[ERROR] Impossible de copier l'image : {error}")
        return False
    
    input("Créer filigrane visible avec Watermarkly sur" f"{file_wm_visible}, puis appuyer sur Entrée...")

    return True

def run_filigrane_visible_auto( wm_visible_subdir, input_img_path, file_wm_visible):
    global PLACE_MODE
    global WM_TEXT
    global WM_TEXT_COLOR
    global WM_SPACING
    global WM_POINTSIZE
    global WM_OPACITY
    global WM_ANGLE
    global WM_STROKE_COLOR
    global WM_STROKE_WIDTH

    if not ensure_dir(wm_visible_subdir):
        return False

    print("=== Filigrane visible (IMv7 compatible) ===")

    if MODE_INTERACTIVE:
        value = input(f"Texte du watermark [{WM_TEXT}] : ")
        WM_TEXT = value or WM_TEXT

        value = input(f"Taille de la police [{WM_POINTSIZE}] : ")
        WM_POINTSIZE = int(value or WM_POINTSIZE)

        value = input(f"Couleur texte R,G,B [{WM_TEXT_COLOR}] : ")
        WM_TEXT_COLOR = value or WM_TEXT_COLOR

        value = input(f"Couleur contour R,G,B [{WM_STROKE_COLOR}] : ")
        WM_STROKE_COLOR = value or WM_STROKE_COLOR

        value = input(f"Épaisseur contour [{WM_STROKE_WIDTH}] : ")
        WM_STROKE_WIDTH = float(value or WM_STROKE_WIDTH)

        value = input(f"Opacité entre 0 et 1 [{WM_OPACITY}] : ")
        WM_OPACITY = float(value or WM_OPACITY)

        value = input(f"Angle [{WM_ANGLE}] : ")
        WM_ANGLE = float(value or WM_ANGLE)

        value = input(f"Espacement [{WM_SPACING}] : ")
        WM_SPACING = int(value or WM_SPACING)

        value = input("Placement : coins (c) / partout (p) [p] : ")
        PLACE_MODE = "corners" if value.lower() == "c" else "all"

    input_image = Path(input_img_path)
    output_image = Path(file_wm_visible)
    subdirectory = Path(wm_visible_subdir)

    if not input_image.is_file():
        print(f"[ERROR] Image introuvable : {input_image}")
        return False

    text_file = subdirectory / "wm_text.txt"
    watermark_file = subdirectory / "wm_label.png"

    text_file.write_text(WM_TEXT, encoding="utf-8")

    angle = 0 if PLACE_MODE == "corners" else WM_ANGLE
    fill_color = f"rgba({WM_TEXT_COLOR},{WM_OPACITY})"
    stroke_color = f"rgb({WM_STROKE_COLOR})"

    command = [
        "magick"
        "-size", f"{WM_SPACING}x{WM_SPACING}",
        "-background", "none",
        "-fill", fill_color,
        "-stroke", stroke_color,
        "-strokewidth", str(WM_STROKE_WIDTH),
        "-pointsize", str(WM_POINTSIZE),
        "-gravity", "center",
    ]

    if WM_FONT:
        command.extend(["-font", WM_FONT])

    command.extend([
        f"label:@{text_file}",
        "-rotate", str(angle),
        str(watermark_file),
    ])

    try:
        subprocess.run(command, check=True)

        if PLACE_MODE == "all":
            dimensions = subprocess.run(
                [
                    "magick", "identify",
                    "-format", "%wx%h",
                    str(input_image),
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout

            subprocess.run(
                [
                    "magick",
                    str(input_image),
                    "-size", dimensions,
                    f"tile:{watermark_file}",
                    "-compose", "over",
                    "-composite",
                    str(output_image),
                ],
                check=True,
            )

        else:
            command = ["magick", str(input_image)]

            for gravity in (
                "northwest",
                "northeast",
                "southwest",
                "southeast",
            ):
                command.extend([
                    "(",
                    str(watermark_file),
                    "-geometry", "+10+10",
                    ")",
                    "-gravity", gravity,
                    "-composite",
                ])

            command.append(str(output_image))
            subprocess.run(command, check=True)

    except FileNotFoundError:
        print("[ERROR] ImageMagick est introuvable")
        return False

    except subprocess.CalledProcessError as error:
        print(f"[ERROR] Échec d'ImageMagick : {error}")
        return False

    finally:
        text_file.unlink(missing_ok=True)
        watermark_file.unlink(missing_ok=True)

    print(f"[OK] Filigrane appliqué sur {file_wm_visible}")
    return True


def run_exif(wm_visible_subdir, file_wm_visible, file_wm_exif):

    if not ensure_dir(wm_visible_subdir):
        return False
    
    print("=== Ajout des métadonnées EXIF ===")

    if not Path(file_wm_visible).is_file():
        print("[WARN] Filigrane visible introuvable, saut EXIF")
        return False

    current_date = datetime.now().strftime("%Y:%m:%d %H:%M:%S")

    if MODE_INTERACTIVE:
        value = input(
            f"Date/heure EXIF (YYYY:mm:dd HH:MM:SS) "
            f"[défaut: {current_date}] : "
        )
        EXIF_DATE = value or current_date
    else:
        EXIF_DATE = EXIF_CUSTOM_DATE or current_date

    try:
        shutil.copy(file_wm_visible, file_wm_exif)

        subprocess.run(
            [
                "exiftool",
                "-overwrite_original",
                f"-DateTimeOriginal={EXIF_DATE}",
                f"-CreateDate={EXIF_DATE}",
                f"-ImageUniqueID={EXIF_DATE}:001",
                "-Creator=© Cert-Art.fr",
                "-Artist=© Cert-Art.fr",
                "-Copyright=© Cert-Art.fr",
                file_wm_exif,
            ],
            check=True,
        )

    except FileNotFoundError:
        print("[ERROR] exiftool est introuvable")
        return False

    except (OSError, subprocess.CalledProcessError) as error:
        print(f"[ERROR] Impossible d'ajouter les métadonnées EXIF : {error}")
        return False

    print(f"[OK] Métadonnées EXIF ajoutées sur {file_wm_exif}")
    return True   