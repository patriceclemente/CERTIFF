import os
import sys
import io
import base64
import importlib
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


# =========================================================
#  PAGES
# =========================================================
@app.route("/")
def accueil():
    # page d'accueil = login
    return app.send_static_file("login.html")


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
#  API — CERTIFICATION D'IMAGE
#  + enregistrement du dépôt rattaché à l'utilisateur connecté
# =========================================================
@app.route("/api", methods=["POST"])
def handle_api():
    # --- on identifie l'utilisateur via la session ---
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify({"status": "error",
                        "message": "Non connecté. Connecte-toi avant de traiter une image."}), 401

    try:
        # récupération de l'image brute et de l'action
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

        # on capture les print() pour qu'ils s'affichent à l'écran
        old_stdout = sys.stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output

        # lancement du main avec les arguments récupérés de l'IHM
        return_code = cli_module.main(argv)

        # on restaure le terminal normal et on récupère les logs
        sys.stdout = old_stdout
        terminal_logs = captured_output.getvalue().splitlines()

        if return_code != 0:
            return jsonify({
                "status": "error",
                "message": "Le traitement des filigranes a échoué.",
                "terminal_output": terminal_logs
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
        for path in possible_outputs:
            if path.is_file():
                final_image_path = path
                break

        # encodage en Base64 de la nouvelle image
        base64_image = None
        if final_image_path and final_image_path.is_file():
            with open(final_image_path, "rb") as img_file:
                encoded_string = base64.b64encode(img_file.read()).decode("utf-8")
            base64_image = f"data:image/png;base64,{encoded_string}"
            os.remove(final_image_path)

        return jsonify({
            "status": "success",
            "action_executed": action,
            "depot_id": depot_id,
            "image_base64": base64_image,
            "terminal_output": terminal_logs
        })

    except Exception as e:
        if "old_stdout" in locals():
            sys.stdout = old_stdout
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    print("Serveur Flask (auth + certification) sur http://localhost:5001")
    app.run(debug=True, port=5001)