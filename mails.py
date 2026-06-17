import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer

# charge les variables du fichier .env (SECRET_KEY, GMAIL_ADDR, GMAIL_APP_PASS)
load_dotenv()

SECRET_KEY = os.environ["SECRET_KEY"]
GMAIL_ADDR = os.environ["GMAIL_ADDR"] 
GMAIL_PASS = os.environ["GMAIL_APP_PASS"] 

serializer = URLSafeTimedSerializer(SECRET_KEY)

#  TOKENS
def generer_token(email):
    """Fabrique un token signé qui contient l'email."""
    return serializer.dumps(email, salt="confirmation-email")


def verifier_token(token, expiration=3600):
    """Vérifie le token. Retourne l'email si valide et non expiré, sinon None.
    expiration = durée de validité en secondes (3600 = 1h)."""
    try:
        return serializer.loads(token, salt="confirmation-email", max_age=expiration)
    except Exception:
        return None



#  ENVOI DU MAIL
def envoyer_mail_confirmation(destinataire, lien):
    msg = EmailMessage()
    msg["Subject"] = "Confirmez votre compte Cert.tif"
    msg["From"] = GMAIL_ADDR          # doit être la même adresse que le login
    msg["To"] = destinataire
    msg.set_content(
        "Bienvenue sur Cert.tif !\n\n"
        f"Confirmez votre compte en cliquant ici : {lien}\n\n"
        "Ce lien expire dans 1 heure."
    )
    msg.add_alternative(f"""
        <html><body style="font-family:monospace;background:#050505;color:#ff9900;padding:20px;">
            <h2>CЄЯ.TΨF // REGISTER</h2>
            <p>Bienvenue ! Cliquez pour confirmer votre compte :</p>
            <p><a href="{lien}" style="color:#ff9900;">&gt; CONFIRMER MON COMPTE</a></p>
            <p style="opacity:0.6;">Ce lien expire dans 1 heure.</p>
        </body></html>
    """, subtype="html")

    with smtplib.SMTP("smtp.gmail.com", 587) as serveur:
        serveur.starttls()
        serveur.login(GMAIL_ADDR, GMAIL_PASS)
        serveur.send_message(msg)
