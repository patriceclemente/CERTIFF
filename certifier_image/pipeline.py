from __future__ import annotations

import getpass
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from . import state
from .native import hash_image
from .utils import (
    ensure_dir,
    explain_source_fallback,
    first_existing,
    get_imagemagick_font_option,
    latest_pipeline_file,
    resolve_exiftool_bin,
    run_command,
)


def run_filigrane_visible_manual() -> bool:
    if not ensure_dir(state.WM_VISIBLE_SUBDIR):
        return False

    print("=== Filigrane visible (manuel) ===")
    try:
        shutil.copy2(state.INPUT_IMG_PATH, state.FILE_WM_VISIBLE)
    except OSError as error:
        print(f"[ERROR] Impossible de copier l'image : {error}")
        return False

    input(f"Creer filigrane visible avec Watermarkly sur {state.FILE_WM_VISIBLE}, puis Entree...")
    return True


def run_filigrane_visible_auto() -> bool:

    if not ensure_dir(state.WM_VISIBLE_SUBDIR):
        return False

    print("=== Filigrane visible (IMv7 compatible) ===")

    if state.MODE_INTERACTIVE:
        value = input(f"Texte du watermark [defaut: {state.WM_TEXT}] : ")
        state.WM_TEXT = value or state.WM_TEXT

        value = input(f"Taille police (pt) [defaut: {state.WM_POINTSIZE}] : ")
        state.WM_POINTSIZE = int(value or state.WM_POINTSIZE)

        value = input(f"Couleur texte R,G,B [defaut: {state.WM_TEXT_COLOR}] : ")
        state.WM_TEXT_COLOR = value or state.WM_TEXT_COLOR

        value = input(f"Couleur contour R,G,B [defaut: {state.WM_STROKE_COLOR}] : ")
        state.WM_STROKE_COLOR = value or state.WM_STROKE_COLOR

        value = input(f"Epaisseur contour (px) [defaut: {state.WM_STROKE_WIDTH}] : ")
        state.WM_STROKE_WIDTH = float(value or state.WM_STROKE_WIDTH)

        value = input(f"Opacite (0-1) [defaut: {state.WM_OPACITY}] : ")
        state.WM_OPACITY = float(value or state.WM_OPACITY)

        value = input(f"Angle [defaut: {state.WM_ANGLE}] : ")
        state.WM_ANGLE = float(value or state.WM_ANGLE)

        value = input(f"Espacement entre watermarks (px) [defaut: {state.WM_SPACING}] : ")
        state.WM_SPACING = int(value or state.WM_SPACING)

        value = input("Placement : coins (c) / partout (p) [defaut: partout] : ")
        state.PLACE_MODE = "corners" if value.lower() == "c" else "all"

    tmp_text = state.WM_VISIBLE_SUBDIR / "wm_text.txt"
    tmp_wm = state.WM_VISIBLE_SUBDIR / "wm_label.png"
    tmp_text.write_text(state.WM_TEXT, encoding="utf-8")

    angle = 0 if state.PLACE_MODE == "corners" else state.WM_ANGLE
    fill_color = f"rgba({state.WM_TEXT_COLOR},{state.WM_OPACITY})"
    stroke_color = f"rgb({state.WM_STROKE_COLOR})"

    command = [
        "magick",
        "-size",
        f"{state.WM_SPACING}x{state.WM_SPACING}",
        "-background",
        "none",
        "-fill",
        fill_color,
        "-stroke",
        stroke_color,
        "-strokewidth",
        str(state.WM_STROKE_WIDTH),
        "-pointsize",
        str(state.WM_POINTSIZE),
        "-gravity",
        "center",
    ]
    command.extend(get_imagemagick_font_option())
    command.extend([f"label:@{tmp_text}", "-rotate", str(angle), str(tmp_wm)])

    try:
        run_command(command)

        if state.PLACE_MODE == "all":
            dimensions = run_command(
                ["magick", "identify", "-format", "%wx%h", str(state.INPUT_IMG_PATH)],
                capture_output=True,
                text=True,
            ).stdout
            run_command(
                [
                    "magick",
                    str(state.INPUT_IMG_PATH),
                    "-size",
                    dimensions,
                    f"tile:{tmp_wm}",
                    "-compose",
                    "over",
                    "-composite",
                    str(state.FILE_WM_VISIBLE),
                ]
            )
        else:
            command = ["magick", str(state.INPUT_IMG_PATH)]
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
            command.append(str(state.FILE_WM_VISIBLE))
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

    print(f"[OK] Filigrane applique sur {state.FILE_WM_VISIBLE}")
    return True


def run_exif() -> bool:

    if not ensure_dir(state.WM_VISIBLE_SUBDIR):
        return False

    print("=== Ajout des metadonnees EXIF ===")
    source_file = first_existing([state.FILE_WM_VISIBLE, state.INPUT_IMG_PATH])
    if not source_file:
        print("[WARN] Image source introuvable, saut EXIF")
        return False
    explain_source_fallback("EXIF", source_file, state.FILE_WM_VISIBLE)

    current_date = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
    if state.MODE_INTERACTIVE:
        value = input(
            f"Date/heure EXIF (YYYY:mm:dd HH:MM:SS) [defaut: {current_date}] : "
        )
        state.EXIF_DATE = value or current_date

        value = input(f"Nom de l'artiste [defaut: {state.EXIF_ARTIST}] : ")
        state.EXIF_ARTIST = value or state.EXIF_ARTIST

        value = input(f"Copyright [defaut: {state.EXIF_COPYRIGHT}] : ")
        state.EXIF_COPYRIGHT = value or state.EXIF_COPYRIGHT
    else:
        state.EXIF_DATE = state.EXIF_CUSTOM_DATE or current_date

    try:
        shutil.copy2(source_file, state.FILE_WM_EXIF)
        run_command(
            [
                resolve_exiftool_bin(),
                "-overwrite_original",
                f"-DateTimeOriginal={state.EXIF_DATE}",
                f"-CreateDate={state.EXIF_DATE}",
                f"-ImageUniqueID={state.EXIF_DATE}:001",
                f"-Creator={state.EXIF_ARTIST}",
                f"-Artist={state.EXIF_ARTIST}",
                f"-Copyright={state.EXIF_COPYRIGHT}",
                str(state.FILE_WM_EXIF),
            ]
        )
    except FileNotFoundError:
        print("[ERROR] exiftool est introuvable")
        return False
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"[ERROR] Impossible d'ajouter les metadonnees EXIF : {error}")
        return False

    print(f"[OK] Metadonnees EXIF ajoutees sur {state.FILE_WM_EXIF}")
    return True


def run_stegano() -> bool:

    ensure_dir(state.WM_INVISIBLE_SUBDIR)
    ensure_dir(state.WM_SIGNATURE_SUBDIR)

    print("=== Filigrane invisible (steganographie) ===")
    carrier_file = first_existing([state.FILE_WM_EXIF, state.FILE_WM_VISIBLE, state.INPUT_IMG_PATH])
    if not carrier_file:
        print("[WARN] Image source introuvable, saut steganographie")
        return False
    explain_source_fallback("Steganographie", carrier_file, state.FILE_WM_EXIF)

    if state.MODE_INTERACTIVE:
        value = input(f"Message a cacher [defaut: {state.MESSAGE}] : ")
        state.MESSAGE = value or state.MESSAGE

        value = input("Voulez-vous saisir un mot de passe pour le filigrane invisible ? (y/n) [n] : ")
        if value.lower() == "y":
            password = getpass.getpass("Mot de passe : ")
        else:
            password = state.MESSAGE
    else:
        password = state.MESSAGE

    msg_file = state.WM_SIGNATURE_SUBDIR / "signature.txt"
    pw_file = state.WM_SIGNATURE_SUBDIR / "pw.txt"
    msg_file.write_text(state.MESSAGE, encoding="utf-8")
    pw_file.write_text(password, encoding="utf-8")

    print(f"[DEBUG] Mot de passe utilise : {password}")
    print(f"[INFO] Fichier message cree dans : {msg_file}")
    print(f"[DEBUG] Mot de passe sauvegarde dans : {pw_file}")

    try:
        run_command(
            [
                "java",
                "-jar",
                str(state.OPENSTEGO_JAR),
                "embed",
                "-mf",
                str(msg_file),
                "-cf",
                str(carrier_file),
                "-sf",
                str(state.FILE_WM_INVISIBLE),
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

    print(f"[OK] Filigrane invisible applique : {state.FILE_WM_INVISIBLE}")
    return True


def run_signature() -> bool:
    ensure_dir(state.WM_NUM_SIGNATURE_SUBDIR)
    ensure_dir(state.WM_SIGNATURE_SUBDIR)
    print("=== Signature numerique ===")

    if check_stegano()==False:
        print("[WARN] Echec de verification du filigrane invisible, la signature ne peut pas se faire")
        return False 

    carrier_file = first_existing([state.FILE_WM_INVISIBLE, state.FILE_WM_EXIF, state.FILE_WM_VISIBLE, state.INPUT_IMG_PATH])
    # if not carrier_file:
    #     print("[WARN] Image source introuvable, saut signature")
    #     return False
    # explain_source_fallback("Signature", carrier_file, state.FILE_WM_INVISIBLE)

    ensure_dir(state.SIG_FILE.parent)
    try:
        signature = hash_image(str(carrier_file)).hex()
        Path(state.SIG_FILE).write_text(signature, encoding="utf-8")
        shutil.copy2(carrier_file, state.FILE_NUM_SIGNED)
    except OSError as error:
        print(f"[ERROR] Impossible de creer la signature : {error}")
        return False
    except Exception as error:
        print(f"[ERROR] Echec du hash de signature : {error}")
        return False

    print(f"[OK] Signature SHA-256 creee : {state.SIG_FILE}")
    print(f"[OK] Image reference pour blockchain : {state.FILE_NUM_SIGNED}")
    return True


def run_blockchain() -> bool:
    print("=== Enregistrement sur la blockchain ===")
    target_file = first_existing([state.FILE_NUM_SIGNED, state.FILE_WM_INVISIBLE, state.FILE_WM_EXIF, state.FILE_WM_VISIBLE, state.INPUT_IMG_PATH])
    if not target_file:
        print("[WARN] Aucun fichier image disponible, saut blockchain")
        return False
    explain_source_fallback("Blockchain", target_file, state.FILE_NUM_SIGNED)

    try:
        run_command([state.OTS_BIN, "stamp", str(target_file)])
    except FileNotFoundError:
        print(f"[ERROR] Commande '{state.OTS_BIN}' introuvable")
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
    if not Path(state.FILE_WM_INVISIBLE).is_file():
        print("[INFO] Filigrane invisible : aucune info")
        return False

    pw_file = state.WM_SIGNATURE_SUBDIR / "pw.txt"
    if not pw_file.is_file():
        print(f"[WARN] Mot de passe introuvable ({pw_file}), impossible de verifier")
        return False

    password = pw_file.read_text(encoding="utf-8")
    msg_file = state.WM_SIGNATURE_SUBDIR / "signature.txt"
    print(f'[INFO] Extraction avec -p "{password}" ...')

    try:
        run_command(
            [
                "java",
                "-jar",
                str(state.OPENSTEGO_JAR),
                "extract",
                "-sf",
                str(state.FILE_WM_INVISIBLE),
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
    if not Path(state.FILE_NUM_SIGNED).is_file():
        print("[INFO] Image signee introuvable")
        return False
    if not Path(state.SIG_FILE).is_file():
        print("[INFO] Fichier de signature introuvable")
        return False

    try:
        expected_signature = Path(state.SIG_FILE).read_text(encoding="utf-8").strip()
        actual_signature = hash_image(str(state.FILE_NUM_SIGNED)).hex()
    except OSError as error:
        print(f"[ERROR] Impossible de lire la signature : {error}")
        return False
    except Exception as error:
        print(f"[ERROR] Verification de signature impossible : {error}")
        return False

    if actual_signature != expected_signature:
        print("[ERROR] Signature invalide")
        print(f"  attendu : {expected_signature}")
        print(f"  obtenu  : {actual_signature}")
        return False

    print("[OK] Signature valide")
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
    print(f"  Commande : {state.OTS_BIN}")
    print()
    print("[INFO] Verification du timestamp distant pour :")
    print(f"       {target}")
    print()

    print("[INFO] Verification initiale...")
    verify_out = subprocess.run(
        [state.OTS_BIN, "verify", str(target)],
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

    if state.MODE_INTERACTIVE:
        choice = input("Souhaitez-vous mettre a jour la preuve OTS maintenant ? (y/n) [y] : ") or "y"
    else:
        choice = "y"

    if choice.lower() == "y":
        print("[INFO] Tentative de mise a jour de la preuve (upgrade)...")
        log_file = Path(tempfile.gettempdir()) / "ots_upgrade.log"
        with log_file.open("w", encoding="utf-8") as log:
            upgraded = subprocess.run(
                [state.OTS_BIN, "upgrade", str(target)],
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
        [state.OTS_BIN, "verify", str(target)],
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
    target_file = first_existing([state.FILE_WM_EXIF, state.FILE_WM_VISIBLE, state.INPUT_IMG_PATH])
    if not target_file:
        print("[INFO] EXIF : aucun fichier disponible")
        return False
    explain_source_fallback("Affichage EXIF", target_file, state.FILE_WM_EXIF)

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
        ensure_dir(state.STATE_FILE.parent)
        state.STATE_FILE.write_text(str(file_path), encoding="utf-8")
        print(f"[STATE] Derniere image : {file_path}")


def run_visible_action() -> bool:
    if state.WM_MODE == "skip":
        print("[INFO] Etape filigrane visible sautee")
        return True
    if state.WM_MODE == "manual":
        return run_filigrane_visible_manual()
    if state.WM_MODE == "auto":
        return run_filigrane_visible_auto()

    print(f"[ERROR] WM_MODE inconnu : {state.WM_MODE}")
    return False


def run_action() -> bool:
    if state.ACTION == "visible":
        print("[ACTION] Watermark visible")
        ok = run_visible_action()
        if ok:
            write_state(state.FILE_WM_VISIBLE)
        return ok

    if state.ACTION == "exif":
        print("[ACTION] EXIF")
        ok = run_exif()
        if ok:
            write_state(state.FILE_WM_EXIF)
        return ok

    if state.ACTION == "stegano":
        print("[ACTION] Steganographie")
        ok = run_stegano()
        if ok:
            write_state(state.FILE_WM_INVISIBLE)
        return ok

    if state.ACTION == "signature":
        print("[ACTION] Signature numerique")
        ok = run_signature()
        if ok:
            write_state(state.FILE_NUM_SIGNED)
        return ok

    if state.ACTION == "blockchain":
        print("[ACTION] Blockchain")
        ok = run_blockchain()
        if ok:
            write_state(latest_pipeline_file())
        return ok

    if state.ACTION == "check_stegano":
        print("[ACTION] Verification steganographie")
        return check_stegano()

    if state.ACTION == "check_signature":
        print("[ACTION] Verification signature")
        return check_signature()

    if state.ACTION == "check_blockchain":
        print("[ACTION] Verification blockchain")
        return check_blockchain()

    if state.ACTION == "show_exif":
        print("[ACTION] Affichage EXIF")
        return show_exif()

    if state.ACTION == "report":
        print("[ACTION] Rapport final")
        return report_final()

    if state.ACTION == "pipeline":
        print(f"[ACTION] Pipeline complet pour {state.INPUT_IMG}")
        ok = run_visible_action()
        if ok:
            write_state(state.FILE_WM_VISIBLE)

        step_ok = run_exif()
        if step_ok:
            write_state(state.FILE_WM_EXIF)
        ok = step_ok and ok

        step_ok = run_stegano()
        if step_ok:
            write_state(state.FILE_WM_INVISIBLE)
        ok = step_ok and ok

        step_ok = run_signature()
        if step_ok:
            write_state(state.FILE_NUM_SIGNED)
        ok = step_ok and ok

        step_ok = run_blockchain()
        if step_ok:
            write_state(latest_pipeline_file())
        ok = step_ok and ok
        return ok

    print(f"Action inconnue : {state.ACTION}")
    print("Actions disponibles : " + ", ".join(sorted(state.KNOWN_ACTIONS)))
    return False


def run_interactive_flow() -> bool:
    print("=== Mode interactif ===")
    print("[INFO] Le mode interactif garde le comportement guide.")
    ok = True

    choice = input("Voulez-vous appliquer le filigrane visible ? (y/n) [n] : ")
    if choice.lower() == "y":
        step_ok = run_filigrane_visible_auto()
        if step_ok:
            write_state(state.FILE_WM_VISIBLE)
        ok = step_ok and ok

    choice = input("Voulez-vous ajouter les metadonnees EXIF ? (y/n) [n] : ")
    if choice.lower() == "y":
        step_ok = run_exif()
        if step_ok:
            write_state(state.FILE_WM_EXIF)
        ok = step_ok and ok

    choice = input("Voulez-vous appliquer le filigrane invisible (steganographie) ? (y/n) [n] : ")
    if choice.lower() == "y":
        step_ok = run_stegano()
        if step_ok:
            write_state(state.FILE_WM_INVISIBLE)
        ok = step_ok and ok

    choice = input("Voulez-vous signer numeriquement l'image ? (y/n) [n] : ")
    if choice.lower() == "y":
        step_ok = run_signature()
        if step_ok:
            write_state(state.FILE_NUM_SIGNED)
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
        print(f"  Fichier : {state.FILE_WM_EXIF}")
        ok = show_exif() and ok

    choice = input("Voulez-vous verifier le filigrane invisible ? (y/n) [n] : ")
    if choice.lower() == "y":
        print("[OPTIONS Verif Steganographie]")
        print(f"  Fichier : {state.FILE_WM_INVISIBLE}")
        print(f"  Message attendu : {state.MESSAGE}")
        ok = check_stegano() and ok

    choice = input("Voulez-vous verifier la signature numerique ? (y/n) [n] : ")
    if choice.lower() == "y":
        print("[OPTIONS Verif Signature]")
        print(f"  Fichier : {state.FILE_NUM_SIGNED}")
        print(f"  Signature attendue : {state.SIG_FILE}")
        ok = check_signature() and ok

    choice = input("Voulez-vous verifier l'enregistrement sur la blockchain ? (y/n) [n] : ")
    if choice.lower() == "y":
        print("[OPTIONS Verif Blockchain]")
        print(f"  Fichier OTS : {state.FILE_NUM_SIGNED}.ots")
        print(f"  Commande : {state.OTS_BIN}")
        ok = check_blockchain() and ok

    return ok

