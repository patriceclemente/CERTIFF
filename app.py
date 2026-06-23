import os
import shutil
import sys
import io
import base64
import importlib
import re
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from DB import init_DB
from flask import Flask, request, jsonify, url_for, session, send_file
from dotenv import load_dotenv

load_dotenv()   # charge SECRET_KEY, GMAIL_ADDR, GMAIL_APP_PASS depuis .env
init_DB.init()  # initialise DB
# =========================================================
#  CHEMINS & IMPORTS PROJET
# =========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "DB"))   # pour "import users" / "import depots"
sys.path.append(BASE_DIR)                        # pour "import certifier_image"

import users    # DB/users.py
import depots   # DB/depots.py
import mails    # mails.py (à la racine)

# static_folder = cer-tif  -> Flask sert tout le dossier frontend
# static_url_path = ""      -> fichiers accessibles à la racine (/style.css, /index.html, ...)
app = Flask(__name__, static_folder="cer-tif", static_url_path="")

# clé secrète nécessaire pour signer les cookies de session (réutilise celle du .env)
app.secret_key = os.environ["SECRET_KEY"]

ACTION_VERS_TRAITEMENT = {
    "visible": "watermarking",
    "exif": "meta-data",
    "stegano": "steganographie",
    "signature": "signature",
    "blockchain": "blockchain",
}

# --- config pour la partie certification d'image ---

PACKAGE_NAME = "certifier_image"
ARTIFACT_FIELDS = (
    "INPUT_IMG_PATH",
    "FILE_WM_VISIBLE",
    "FILE_WM_EXIF",
    "FILE_WM_INVISIBLE",
    "FILE_NUM_SIGNED",
    "SIG_FILE",
    "WM_SIGNATURE_SUBDIR",
)


def sanitize_terminal_logs(lines):
    """Remove internal filesystem paths before sending logs to the browser."""
    sanitized = []
    path_pattern = re.compile(
        r'([A-Za-z]:\\[^\s"]+|(?:DB\\stockage|images_brutes|watermark-[^\s\\]+|raw_uploads|uploads)[^\s"]*)'
    )
    long_hash_pattern = re.compile(r"\b[a-fA-F0-9]{32,}\b")

    for line in lines:
        public_line = path_pattern.sub("[fichier]", line)
        public_line = long_hash_pattern.sub("[id-fichier]", public_line)
        public_line = public_line.replace(" comme entree", "")

        if public_line.strip().startswith("DEBUG:"):
            continue
        if "INPUT_IMG_PATH" in public_line:
            continue
        if public_line.startswith("Extracted file:"):
            continue
        if "source :" in public_line or "dest   :" in public_line:
            continue
        if public_line.startswith("       "):
            continue

        sanitized.append(public_line)

    return sanitized


def project_relative_path(path):
    if not path:
        return None

    base_path = Path(BASE_DIR).resolve()
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(base_path))
    except ValueError:
        return None


def project_path(relative_path):
    if not relative_path:
        return None

    base_path = Path(BASE_DIR).resolve()
    resolved = (base_path / relative_path).resolve()
    try:
        resolved.relative_to(base_path)
    except ValueError:
        return None
    return resolved


def certification_workspace(depot_id):
    return Path(depots.STOCKAGE_DIR) / "certifications" / str(depot_id)


def newest_file(paths):
    files = [Path(path) for path in paths if Path(path).is_file()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def configure_state_from_storage(state_module, storage_root, img_base, input_path):
    root = Path(storage_root)
    img_base = str(img_base)
    input_path = Path(input_path)

    state_module.INPUT_IMG_PATH = newest_file(
        (root / "images_brutes" / img_base).glob("*.png")
    ) or input_path
    state_module.IMG_BASE = img_base
    state_module.IMG_EXT = "png"

    state_module.WATERMARK_VISIBLE_DIR = root / "watermark-filigrane-visible"
    state_module.WATERMARK_INVISIBLE_DIR = root / "watermark-filigrane-invisible"
    state_module.SIGNATURES_DIR = root / "watermark-signatures"
    state_module.NUM_SIGNATURE_DIR = root / "watermark-signature_numérique"

    state_module.WM_VISIBLE_SUBDIR = state_module.WATERMARK_VISIBLE_DIR / img_base
    state_module.WM_INVISIBLE_SUBDIR = state_module.WATERMARK_INVISIBLE_DIR / img_base
    state_module.WM_SIGNATURE_SUBDIR = state_module.SIGNATURES_DIR / img_base
    state_module.WM_NUM_SIGNATURE_SUBDIR = state_module.NUM_SIGNATURE_DIR / img_base

    visible_files = list(state_module.WM_VISIBLE_SUBDIR.glob("*.png"))
    exif_files = [path for path in visible_files if "exif" in path.stem.lower()]
    state_module.FILE_WM_VISIBLE = newest_file(
        [path for path in visible_files if "exif" not in path.stem.lower()]
    ) or newest_file(visible_files)
    state_module.FILE_WM_EXIF = newest_file(exif_files)
    state_module.FILE_WM_INVISIBLE = newest_file(state_module.WM_INVISIBLE_SUBDIR.glob("*.png"))
    state_module.FILE_NUM_SIGNED = newest_file(state_module.WM_NUM_SIGNATURE_SUBDIR.glob("*.png"))
    state_module.SIG_FILE = state_module.WM_SIGNATURE_SUBDIR / "bleu-pastel.sig"

    return any(
        path and Path(path).is_file()
        for path in (
            state_module.FILE_WM_VISIBLE,
            state_module.FILE_WM_EXIF,
            state_module.FILE_WM_INVISIBLE,
            state_module.FILE_NUM_SIGNED,
            state_module.SIG_FILE,
        )
    )


def store_certification_artifacts(state_module):
    artifacts = {}
    for field in ARTIFACT_FIELDS:
        value = getattr(state_module, field, None)
        if not value or not Path(value).exists():
            continue
        relative = project_relative_path(value)
        if relative:
            artifacts[field] = relative

    if artifacts:
        session["certification_artifacts"] = artifacts


def restore_certification_artifacts(state_module):
    artifacts = session.get("certification_artifacts") or {}
    restored = False

    for field, relative in artifacts.items():
        if field not in ARTIFACT_FIELDS:
            continue
        path = project_path(relative)
        if path:
            setattr(state_module, field, path)
            restored = True

    return restored


def run_report_with_saved_artifacts(chemin_stockage, work_base=None, legacy_img_base=None):
    state_module = importlib.import_module("certifier_image.state")
    pipeline_module = importlib.import_module("certifier_image.pipeline")
    paths_module = importlib.import_module("certifier_image.paths")
    utils_module = importlib.import_module("certifier_image.utils")

    restored = False
    if work_base:
        workspace_storage = Path(work_base) / "DB" / "stockage"
        restored = configure_state_from_storage(state_module, workspace_storage, Path(chemin_stockage).stem, chemin_stockage)

    if not restored and legacy_img_base:
        restored = configure_state_from_storage(state_module, depots.STOCKAGE_DIR, legacy_img_base, chemin_stockage)

    if not restored:
        restored = restore_certification_artifacts(state_module)

    if not restored:
        state_module.ACTION = "report"
        state_module.BASE_DIR = Path(".")
        state_module.INPUT_IMG = Path(chemin_stockage)
        paths_module.prepare_pipeline()

    old_stdout = sys.stdout
    captured_output = io.StringIO()
    sys.stdout = captured_output
    try:
        deps_ok = utils_module.check_dependencies("report")
        if deps_ok:
            pipeline_module.report_final()
    finally:
        sys.stdout = old_stdout

    return captured_output.getvalue().splitlines()


# =========================================================
#  BACKGROUND BLOCKCHAIN CHECKER
# =========================================================
BLOCKCHAIN_CHECK_INTERVAL_SECONDS = int(os.environ.get("BLOCKCHAIN_CHECK_INTERVAL_SECONDS", "300"))
BLOCKCHAIN_WORKER_STARTED = False
BLOCKCHAIN_WORKER_LOCK = threading.Lock()


def database_path():
    return Path(BASE_DIR) / "DB" / "DB.db"


def init_blockchain_jobs_table():
    conn = sqlite3.connect(database_path())
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS blockchain_jobs (
                job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                depot_id INTEGER,
                image_path TEXT NOT NULL,
                ots_path TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending',
                notified INTEGER NOT NULL DEFAULT 0,
                last_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def get_user_email(user_id):
    conn = sqlite3.connect(database_path())
    try:
        row = conn.execute(
            "SELECT email FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_depot_filename(depot_id):
    if depot_id is None:
        return None

    conn = sqlite3.connect(database_path())
    try:
        row = conn.execute(
            "SELECT nom_fichier FROM depots WHERE depot_id = ?",
            (depot_id,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()

def get_depot_hash(depot_id):
    if depot_id is None:
        return None
    conn = sqlite3.connect(database_path())
    try:
        row = conn.execute(
            "SELECT hash_fichier FROM depots WHERE depot_id = ?",
            (depot_id,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()

def resolve_ots_bin():
    configured = os.environ.get("OTS_BIN")
    if configured:
        return configured

    local_ots = Path(BASE_DIR) / ".venv" / "Scripts" / "ots.exe"
    if local_ots.is_file():
        return str(local_ots)

    return "ots"


def latest_blockchain_target(state_module):
    for field in (
        "FILE_NUM_SIGNED",
        "FILE_WM_INVISIBLE",
        "FILE_WM_EXIF",
        "FILE_WM_VISIBLE",
        "INPUT_IMG_PATH",
    ):
        value = getattr(state_module, field, None)
        if value and Path(value).is_file():
            return Path(value)
    return None


def register_blockchain_job(user_id, depot_id, state_module):
    target = latest_blockchain_target(state_module)
    if not target:
        print("[WARN] Blockchain worker: aucune image cible a suivre")
        return

    ots_path = Path(f"{target}.ots")
    if not ots_path.is_file():
        print(f"[WARN] Blockchain worker: preuve OTS introuvable pour {target}")
        return

    image_relative = project_relative_path(target)
    ots_relative = project_relative_path(ots_path)
    if not image_relative or not ots_relative:
        print("[WARN] Blockchain worker: chemin hors projet, job ignore")
        return

    init_blockchain_jobs_table()
    conn = sqlite3.connect(database_path())
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO blockchain_jobs
                (user_id, depot_id, image_path, ots_path, status, notified)
            VALUES (?, ?, ?, ?, 'pending', 0)
            """,
            (user_id, depot_id, image_relative, ots_relative),
        )
        conn.commit()
    finally:
        conn.close()


def list_pending_blockchain_jobs():
    init_blockchain_jobs_table()
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT job_id, user_id, depot_id, image_path, ots_path
            FROM blockchain_jobs
            WHERE status IN ('pending', 'confirmed') AND notified = 0
            ORDER BY created_at ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_blockchain_job(job_id, status, last_message, notified=False):
    conn = sqlite3.connect(database_path())
    try:
        conn.execute(
            """
            UPDATE blockchain_jobs
            SET status = ?, last_message = ?, notified = ?, updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
            """,
            (status, last_message[:1000], 1 if notified else 0, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def blockchain_output_is_confirmed(output):
    return (
        "Timestamped by transaction" in output
        or ("Success!" in output and "attests" in output)
    )


def check_one_blockchain_job(job):
    ots_path = project_path(job["ots_path"])
    if not ots_path or not ots_path.is_file():
        update_blockchain_job(job["job_id"], "error", "Fichier .ots introuvable")
        return

    ots_bin = resolve_ots_bin()
    try:
        subprocess.run(
            [ots_bin, "upgrade", str(ots_path)],
            capture_output=True,
            text=True,
            timeout=180,
        )
        verified = subprocess.run(
            [ots_bin, "verify", str(ots_path)],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except FileNotFoundError:
        update_blockchain_job(job["job_id"], "pending", f"Commande OTS introuvable : {ots_bin}")
        return
    except subprocess.TimeoutExpired:
        update_blockchain_job(job["job_id"], "pending", "Verification OTS trop longue")
        return

    output = (verified.stdout or "") + (verified.stderr or "")
    if not blockchain_output_is_confirmed(output):
        update_blockchain_job(job["job_id"], "pending", output or "Preuve encore en attente")
        return

    email = get_user_email(job["user_id"])
    if not email:
        update_blockchain_job(job["job_id"], "confirmed", "Utilisateur introuvable", notified=False)
        return

    image_name = get_depot_filename(job["depot_id"]) or Path(job["image_path"]).name
    try:
        mails.envoyer_mail_blockchain(email, image_name)
    except Exception as error:
        update_blockchain_job(job["job_id"], "confirmed", f"Mail non envoye : {error}", notified=False)
        return

    update_blockchain_job(job["job_id"], "confirmed", "Mail de confirmation envoye", notified=True)


def blockchain_worker_loop():
    while True:
        try:
            for job in list_pending_blockchain_jobs():
                check_one_blockchain_job(job)
        except Exception as error:
            print("Erreur blockchain worker :", error)
        time.sleep(BLOCKCHAIN_CHECK_INTERVAL_SECONDS)


def start_blockchain_worker():
    global BLOCKCHAIN_WORKER_STARTED
    with BLOCKCHAIN_WORKER_LOCK:
        if BLOCKCHAIN_WORKER_STARTED:
            return
        init_blockchain_jobs_table()
        thread = threading.Thread(target=blockchain_worker_loop, daemon=True)
        thread.start()
        BLOCKCHAIN_WORKER_STARTED = True


# =========================================================
#  PAGES
# =========================================================
@app.route("/")
def accueil():
    # page d'accueil = login
    return app.send_static_file("login.html")

# =========================================================
#  INFO SESSION
# =========================================================
@app.route("/api/me")
def me():
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify({"ok": False, "message": "Non connecté"}), 401

    username = users.get_username(user_id)   # voir note ci-dessous
    if username is None:
        return jsonify({"ok": False, "message": "Utilisateur introuvable"}), 404

    return jsonify({"ok": True, "username": username})

# =========================================================
#  HISTORIQUE
# =========================================================
def mimetype_from_extension(extension):
    ext = (extension or "").lower().lstrip(".")
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "tif": "image/tiff",
        "tiff": "image/tiff",
        "gif": "image/gif",
        "webp": "image/webp",
        "bmp": "image/bmp",
    }.get(ext, "application/octet-stream")


@app.route("/api/image/<hash_fichier>")
def api_image(hash_fichier):
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify({"ok": False, "message": "Non connecté"}), 401

    if not re.fullmatch(r"[a-fA-F0-9]{64}", hash_fichier or ""):
        return jsonify({"ok": False, "message": "Identifiant invalide"}), 404

    conn = sqlite3.connect(database_path())
    try:
        row = conn.execute(
            "SELECT depot_id, extension FROM depots WHERE user_id = ? AND hash_fichier = ?",
            (user_id, hash_fichier),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return jsonify({"ok": False, "message": "Image introuvable"}), 404

    depot_id, extension = row

    # priorité à la version la plus traitée (cooked), sinon l'originale (raw)
    cooked = os.path.join(depots.COOKED_UPLOAD_DIR, f"{depot_id}.png")
    if os.path.isfile(cooked):
        return send_file(cooked, mimetype="image/png")

    raw = os.path.join(depots.RAW_UPLOAD_DIR, hash_fichier)
    if os.path.isfile(raw):
        return send_file(raw, mimetype=mimetype_from_extension(extension))

    return jsonify({"ok": False, "message": "Fichier absent du stockage"}), 404

@app.route("/api/historique")
def historique():
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify({"ok": False, "message": "Non connecté"}), 401

    depots_bruts = depots.lister_depots(user_id)   # liste de tuples

    # on transforme chaque tuple en dictionnaire (plus clair côté JS)
    depots_liste = []
    for d in depots_bruts:
        depots_liste.append({
            "nom_fichier": d[0],
            "hash_fichier": d[1],
            "date_depot": d[2],
            "taille": d[3],
            "url_image": f"/api/image/{d[1]}"
        })

    return jsonify({"ok": True, "depots": depots_liste})

# =========================================================
#  API — AUTHENTIFICATION (partie login/signup)
# =========================================================
@app.route("/api/inscription", methods=["POST"])
def inscription():
    data = request.get_json()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    mdp = data.get("mot_de_passe", "")

    if not username or not email or not mdp:
        return jsonify({"ok": False, "message": "CHAMPS MANQUANTS."})

    resultat = users.create_user(username, email, mdp)

    if resultat == "user_created":
        token = mails.generer_token(email)
        lien = url_for("confirmer", token=token, _external=True)
        try:
            mails.envoyer_mail_confirmation(email, lien)
        except Exception as e:
            print("Erreur envoi mail :", e)
            return jsonify({"ok": False,
                            "message": "COMPTE CRÉÉ MAIS L'ENVOI DU MAIL A ÉCHOUÉ."})
        return jsonify({"ok": True})
    elif resultat == "email_pris":
        return jsonify({"ok": False, "message": "EMAIL DÉJÀ UTILISÉ."})
    elif resultat == "username_pris":
        return jsonify({"ok": False, "message": "NOM DÉJÀ PRIS."})
    elif resultat == "mdp_trop_court":
        return jsonify({"ok": False, "message": "mot de passe trop court (8 characteres minimum)"})
    elif resultat == "mdp_pas_special":
        return jsonify({"ok": False, "message": "au moins un charachter special"})
    elif resultat == "mdp_pas_chiffre":
        return jsonify({"ok": False, "message": "au moins un chiffre"})
    return jsonify({"ok": False, "message": "ERREUR INCONNUE."})


@app.route("/api/connexion", methods=["POST"])
def connexion():
    data = request.get_json()
    identifiant = data.get("identifiant", "").strip()   # email OU username
    mdp = data.get("mot_de_passe", "")

    statut = users.verif_id(identifiant, mdp)
    if statut == "ok":
        # on mémorise QUI est connecté dans la session (lu ensuite par /api)
        session["user_id"] = users.get_user_id(identifiant)
        return jsonify({"ok": True})
    elif statut == "non_confirme":
        return jsonify({"ok": False,
                        "message": "COMPTE NON CONFIRMÉ. VÉRIFIE TES MAILS."})
    return jsonify({"ok": False, "message": "IDENTIFIANTS INVALIDES."})


@app.route("/api/deconnexion", methods=["POST"])
def deconnexion():
    session.clear()   # vide la session : l'utilisateur n'est plus connecté
    return jsonify({"ok": True})


@app.route("/confirmer/<token>")
def confirmer(token):
    email = mails.verifier_token(token)
    if email is None:
        return "<p>Lien invalide ou expiré.</p>", 400
    users.confirm_user(email)
    return """
        <html><body style="font-family:monospace;background:#050505;color:#ff9900;padding:40px;">
            <h2>&gt; COMPTE CONFIRMÉ.</h2>
            <p><a href="/" style="color:#ff9900;">[ SE CONNECTER ]</a></p>
        </body></html>
    """
# =========================================================
#  API — FILE UPLOAD
# =========================================================
@app.route("/api/upload", methods=["POST"])
def api_depot():
    user_id = session.get("user_id")

    if "file" not in request.files:
        return jsonify({"status": "error", "message": "Aucun fichier fourni."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "Nom de fichier vide."}), 400

    # Lire le contenu AVANT tout
    contenu = file.read()

    if user_id is None:
        # Anonyme : on ne persiste pas, mais on ne plante pas non plus
        return jsonify({"status": "success", "depot_id": None, "message": "Non connecté, dépôt non sauvegardé."})

    try:
        depot_id, chemin_stockage = depots.enregistrer_depot(user_id, file.filename, contenu)
        print(f"Dépôt enregistré : depot_id={depot_id}, user_id={user_id}")
        return jsonify({"status": "success", "depot_id": depot_id})
    except Exception as e:
        print("Échec enregistrement dépôt :", e)
        return jsonify({"status": "error", "message": "Échec de l'enregistrement du dépôt."}), 500
# =========================================================
#  API — CERTIFICATION D'IMAGE
# =========================================================
@app.route("/api", methods=["POST"])
def handle_api():
    user_id = session.get("user_id")
    old_stdout = None
    work_base = None
    delete_work_base = False
 
    try:
        action = request.form.get("action", "pipeline")
        depot_id_form = request.form.get("depot_id") or None
 
        if "file" not in request.files:
            return jsonify({"status": "error", "message": "Aucun fichier fourni."}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"status": "error", "message": "Nom de fichier vide."}), 400
        contenu = file.read()
 
        persistent_depot_id = None
        if user_id is not None and depot_id_form:
            persistent_depot_id = int(depot_id_form)

        if persistent_depot_id is not None:
            work_base = str(certification_workspace(persistent_depot_id))
            os.makedirs(work_base, exist_ok=True)
        else:
            work_base = tempfile.mkdtemp(prefix="cert_")
            delete_work_base = True

        input_dir = os.path.join(work_base, "input")
        os.makedirs(input_dir, exist_ok=True)
        chemin_stockage = os.path.join(input_dir, "image.png")

        # Choix de l'image d'entrée :
        #  - connecté avec depot_id : on repart de la version la plus traitée
        #    (cooked si elle existe, sinon raw) -> les traitements s'empilent.
        #  - sinon (invité) : on prend le fichier envoyé tel quel.
        source_path = None
        if user_id is not None and depot_id_form:
            hash_fichier = get_depot_hash(int(depot_id_form))
            if hash_fichier:
                source_path = depots.chemin_image_courante(int(depot_id_form), hash_fichier)

        if source_path and os.path.isfile(source_path):
            shutil.copy2(source_path, chemin_stockage)
        else:
            with open(chemin_stockage, "wb") as f:
                f.write(contenu)
 
        # parametres watermark
        wm_text = request.form.get("wm_text", "© Cert-Art.fr")
        wm_size = request.form.get("wm_size", "35")
        wm_color = request.form.get("wm_color", "128,128,128")
        wm_opacity = request.form.get("wm_opacity", "0.2")
        wm_angle = request.form.get("wm_angle", "-45")
        wm_spacing = request.form.get("wm_spacing", "300")
        stegano_message = request.form.get("stegano_message", "defaut")
        exif_artist = request.form.get("exif_artist", "").strip() or "© Cert-Art.fr"
        exif_copyright = request.form.get("exif_copyright", "").strip() or exif_artist
        exif_date = request.form.get("exif_date", "").strip()
 
        # base_dir = work_base  ->  toutes les sorties du moteur vont dans
        # work_base/DB/stockage/... (donc supprimees a la fin)
        argv = [
            "--no-interactive",
            "--wm-text", str(wm_text),
            "--wm-size", str(wm_size),
            "--wm-opacity", str(wm_opacity),
            "--wm-color", str(wm_color),
            "--wm-angle", str(wm_angle),
            "--wm-spacing", str(wm_spacing),
            "--stegano-message", str(stegano_message),
            "--exif-artist", str(exif_artist),
            "--exif-copyright", str(exif_copyright),
            "--exif-date", str(exif_date),
            action,
            work_base,
            chemin_stockage,
        ]
 
        cli_module = importlib.import_module("certifier_image.cli")
        state_module = importlib.import_module("certifier_image.state")
 
        if action == "report":
            legacy_img_base = None
            if persistent_depot_id is not None:
                legacy_img_base = get_depot_hash(persistent_depot_id)
            terminal_logs = run_report_with_saved_artifacts(chemin_stockage, work_base, legacy_img_base)
            return jsonify({
                "status": "success",
                "action_executed": action,
                "depot_id": depot_id_form,
                "image_base64": None,
                "terminal_output": sanitize_terminal_logs(terminal_logs),
            })
 
        old_stdout = sys.stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        return_code = cli_module.main(argv)
        sys.stdout = old_stdout
        old_stdout = None
        public_terminal_logs = sanitize_terminal_logs(captured_output.getvalue().splitlines())

        if return_code == 0:
            store_certification_artifacts(state_module)
            if user_id is not None and depot_id_form and action in {"blockchain", "pipeline"}:
                register_blockchain_job(user_id, depot_id_form, state_module)
 
        # --- table statuts ---
        if depot_id_form and action in ACTION_VERS_TRAITEMENT:
            statut = "termine" if return_code == 0 else "echec"
            try:
                depots.enregistrer_traitement(int(depot_id_form), ACTION_VERS_TRAITEMENT[action], statut)
            except Exception as e:
                print("Statut non enregistre :", e)
 
        if return_code != 0:
            return jsonify({
                "status": "error",
                "message": "Le traitement de l'image a echoue",
                "terminal_output": public_terminal_logs,
            }), 500
 
        # --- image la plus traitee ---
        final_image_path = None
        for path in (
            state_module.FILE_NUM_SIGNED,
            state_module.FILE_WM_INVISIBLE,
            state_module.FILE_WM_EXIF,
            state_module.FILE_WM_VISIBLE,
            state_module.INPUT_IMG_PATH,
        ):
            if path and Path(path).is_file():
                final_image_path = Path(path)
                break
 
        base64_image = None
        if final_image_path and final_image_path.is_file():
            with open(final_image_path, "rb") as img_file:
                base64_image = "data:image/png;base64," + base64.b64encode(img_file.read()).decode("utf-8")
 
            # copie de la version la plus traitee dans cooked (persiste)
            print("DEBUG cooked -> depot_id:", depot_id_form,
              "| final:", final_image_path,
              "| cooked_dir:", depots.COOKED_UPLOAD_DIR)
            if depot_id_form:
                try:
                    os.makedirs(depots.COOKED_UPLOAD_DIR, exist_ok=True)
                    dest = os.path.join(depots.COOKED_UPLOAD_DIR, f"{depot_id_form}.png")
                    shutil.copy2(final_image_path, dest)
                except Exception as e:
                    print("Copie cooked impossible :", e)
 
        return jsonify({
            "status": "success",
            "action_executed": action,
            "depot_id": depot_id_form,
            "image_base64": base64_image,
            "terminal_output": public_terminal_logs,
        })
 
    except Exception as e:
        if old_stdout is not None:
            sys.stdout = old_stdout
        return jsonify({"status": "error", "message": str(e)}), 500
 
    finally:
        # On supprime seulement les workspaces temporaires des invites.
        # Les workspaces des depots connectes gardent les preuves de verification.
        if delete_work_base and work_base:
            shutil.rmtree(work_base, ignore_errors=True)



# if __name__ == "__main__":
#     print("Serveur Flask (auth + certification) sur http://localhost:5001")
#     start_blockchain_worker()
#     app.run(debug=True, port=5001, use_reloader=False)



if __name__ == "__main__":
    print("Serveur Flask (auth + certification) sur http://localhost:5001")
    start_blockchain_worker()
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", debug=debug_mode, port=5001, use_reloader=False)