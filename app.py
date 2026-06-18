import os
import sys
import io
import base64
import importlib
import re
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

from flask import Flask, request, jsonify, url_for, session
from dotenv import load_dotenv

load_dotenv()   # charge SECRET_KEY, GMAIL_ADDR, GMAIL_APP_PASS depuis .env

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


def run_report_with_saved_artifacts(chemin_stockage):
    state_module = importlib.import_module("certifier_image.state")
    pipeline_module = importlib.import_module("certifier_image.pipeline")
    paths_module = importlib.import_module("certifier_image.paths")
    utils_module = importlib.import_module("certifier_image.utils")

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

@app.route("/api/historique")
def historique():
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify({"ok": False, "message": "Connect toi petit malin"}), 401

    depots_bruts = depots.lister_depots(user_id)   # liste de tuples

    # on transforme chaque tuple en dictionnaire (plus clair côté JS)
    depots_liste = []
    for d in depots_bruts:
        depots_liste.append({
            "nom_fichier": d[0],
            "hash_fichier": d[1],
            "date_depot": d[2],
            "taille": d[3]
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
    if user_id is None:
        return jsonify({"status": "error", "message": "Non connecté."}), 401

    if "file" not in request.files:
        return jsonify({"status": "error", "message": "Aucun fichier fourni."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "Nom de fichier vide."}), 400

    contenu = file.read()
    try:
        depot_id, chemin_stockage = depots.enregistrer_depot(user_id, file.filename, contenu)
        print(f"Dépôt enregistré au dépôt : depot_id={depot_id}, user_id={user_id}")
    except Exception as e:
        print("Échec enregistrement dépôt :", e)
        return jsonify({"status": "error", "message": "Échec de l'enregistrement du dépôt."}), 500

    return jsonify({"status": "success", "depot_id": depot_id})
# =========================================================
#  API — CERTIFICATION D'IMAGE
# =========================================================
@app.route("/api", methods=["POST"])
def handle_api():
    try:
        # récupération de l'image brute et de l'action
        user_id = session.get("user_id")
        if user_id is None:
            return jsonify({"status": "error", "message": "Non connecte."}), 401

        action = request.form.get("action", "pipeline")
        if "file" not in request.files:
            return jsonify({"status": "error", "message": "Aucun fichier fourni."}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"status": "error", "message": "Nom de fichier vide."}), 400
        contenu = file.read()
        depot_id = None
        chemin_stockage = None
        try:
            depot_id, chemin_stockage = depots.enregistrer_depot(user_id, file.filename, contenu)
            print(f"Dépôt enregistré : depot_id={depot_id}, user_id={user_id}")
        except Exception as e:
            print("Avertissement : échec enregistrement dépôt :", e)
            return jsonify({"status": "error", "message": "Échec de l'enregistrement du dépôt."}), 500

        # récupération des paramètres de l'interface JS
        wm_text = request.form.get("wm_text", "© Cert-Art.fr")
        wm_size = request.form.get("wm_size", "35")
        wm_color = request.form.get("wm_color", "128,128,128")
        wm_opacity = request.form.get("wm_opacity", "0.2")
        wm_angle = request.form.get("wm_angle", "-45")
        wm_spacing = request.form.get("wm_spacing", "300")
        stegano_message = request.form.get("stegano_message", "defaut")

        # préparation de la liste d'arguments requise par cli.py
        argv = [
            "--no-interactive",
            "--wm-text", str(wm_text),
            "--wm-size", str(wm_size),
            "--wm-opacity", str(wm_opacity),
            "--wm-color", str(wm_color),
            "--wm-angle", str(wm_angle),
            "--wm-spacing", str(wm_spacing),
            "--stegano-message", str(stegano_message),
            action,
            chemin_stockage  # chemin du fichier déposé par l'utilisateur,
        ]

        print(f"Transmission des paramètres au moteur : {argv}")

        # appelle du module cli.py dynamiquement
        cli_module = importlib.import_module("certifier_image.cli")
        state_module = importlib.import_module("certifier_image.state")

        if action == "report":
            terminal_logs = run_report_with_saved_artifacts(chemin_stockage)
            public_terminal_logs = sanitize_terminal_logs(terminal_logs)
            return jsonify({
                "status": "success",
                "action_executed": action,
                "depot_id": depot_id,
                "image_base64": None,
                "terminal_output": public_terminal_logs
            })

        # on capture les print() pour qu'ils s'affichent à l'écran
        old_stdout = sys.stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output

        # lancement du main avec les arguments récupérés de l'IHM
        return_code = cli_module.main(argv)

        # on restaure le terminal normal et on récupère les logs
        sys.stdout = old_stdout
        terminal_logs = captured_output.getvalue().splitlines()
        public_terminal_logs = sanitize_terminal_logs(terminal_logs)

        if return_code == 0:
            store_certification_artifacts(state_module)
            if action in {"blockchain", "pipeline"}:
                register_blockchain_job(user_id, depot_id, state_module)

        if return_code != 0 and action != "report":
            return jsonify({
                "status": "error",
                "message": "Le traitement de l'image a échoué",
                "terminal_output": public_terminal_logs
            }), 500

        # localisation de l'image créée par le python
        img_base = Path(chemin_stockage).stem
        possible_outputs = [
            Path(f"watermark-signature_numérique/{img_base}/{img_base}-watermarked_exif-openstego-num_signed.png"),
            Path(f"watermark-filigrane-invisible/{img_base}/{img_base}-watermarked_exif-openstego.png"),
            Path(f"watermark-filigrane-visible/{img_base}/{img_base}-watermarked_exif.png"),
            Path(f"watermark-filigrane-visible/{img_base}/{img_base}-watermarked.png"),
            Path(f"images_brutes/{img_base}/{img_base}.png"),
        ]

        final_image_path = None
        state_module = importlib.import_module("certifier_image.state")
        possible_outputs = [
            state_module.FILE_NUM_SIGNED,
            state_module.FILE_WM_INVISIBLE,
            state_module.FILE_WM_EXIF,
            state_module.FILE_WM_VISIBLE,
            state_module.INPUT_IMG_PATH,
        ]
        for path in possible_outputs:
            if path and Path(path).is_file():
                final_image_path = Path(path)
                break

        # encodage en Base64 de la nouvelle image
        base64_image = None
        if final_image_path and final_image_path.is_file():
            with open(final_image_path, "rb") as img_file:
                encoded_string = base64.b64encode(img_file.read()).decode("utf-8")
            base64_image = f"data:image/png;base64,{encoded_string}"

        return jsonify({
            "status": "success",
            "action_executed": action,
            "depot_id": depot_id,
            "image_base64": base64_image,
            "terminal_output": public_terminal_logs
        })

    except Exception as e:
        if "old_stdout" in locals():
            sys.stdout = old_stdout
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    print("Serveur Flask (auth + certification) sur http://localhost:5001")
    start_blockchain_worker()
    app.run(debug=True, port=5001, use_reloader=False)
