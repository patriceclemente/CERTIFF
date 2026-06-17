import os
import sys
from flask import Flask, request, jsonify, url_for

# --- Permet d'importer le code de la base (dossier DB/) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "DB"))

import users   # DB/users.py
import mails    # mails.py (à la racine)

# static_folder = cer-tif  -> Flask sert tout le dossier frontend
# static_url_path = ""      -> les fichiers sont accessibles à la racine
#                              (ex: /style.css, /login.js, /index.html)
app = Flask(__name__, static_folder="cer-tif", static_url_path="")


# =========================================================
#  PAGES
# =========================================================

@app.route("/")
def accueil():
    # page d'accueil = login
    return app.send_static_file("login.html")


# =========================================================
#  API
# =========================================================

@app.route("/api/inscription", methods=["POST"])
def inscription():
    data = request.get_json()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    mdp = data.get("mot_de_passe", "")

    if not username or not email or not mdp:
        return jsonify({"ok": False, "message": "CHAMPS MANQUANTS."})

    resultat = users.creer_utilisateur(username, email, mdp)

    if resultat == "user_created":
        # génère le token et envoie le mail de confirmation
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

    statut = users.verifier_identifiants(identifiant, mdp)
    if statut == "ok":
        return jsonify({"ok": True})
    elif statut == "non_confirme":
        return jsonify({"ok": False,
                        "message": "COMPTE NON CONFIRMÉ. VÉRIFIE TES MAILS."})
    return jsonify({"ok": False, "message": "IDENTIFIANTS INVALIDES."})


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


if __name__ == "__main__":
    app.run(debug=True, port=5000)