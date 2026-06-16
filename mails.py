from dotenv import load_dotenv
load_dotenv()

import os 
import smtplib
from email.message import EmailMessage
#from itsdangerous import URLSafeTimedSerializerimport
import smtplib
from email.message import EmailMessage
from itsdangerous import URLSafeTimedSerializer


# il faut définir ces variables d'environnement dans le fichier .env 
SECRET_KEY = os.environ["SECRET_KEY"]        # une longue chaîne aléatoire, a generer une seul fois
GMAIL_ADDR = os.environ["GMAIL_ADDR"]        # noreply.certif@gmail.com
GMAIL_PASS = os.environ["GMAIL_APP_PASS"]    # code 16 lettres a 

serializer = URLSafeTimedSerializer(SECRET_KEY)

def generer_token(email):
    return serializer.dumps(email, salt="confirmation-email")

def verifier_token(token, expiration=3600):
    try:
        return serializer.loads(token, salt="confirmation-email", max_age=expiration)
    except Exception:
        return None

def envoyer_mail_confirmation(destinataire, lien):
    msg = EmailMessage()
    msg["Subject"] = "Confirmez votre compte"
    msg["From"] = GMAIL_ADDR          # doit être la même adresse que le login
    msg["To"] = destinataire
    msg.set_content(f"Confirmez votre compte {lien}")
    msg.add_alternative(f"""
        <html><body>
            <h2> Gros texte !</h2>
            <p><a href="{lien}">click here</a></p>
        </body></html>
    """, subtype="html")

    with smtplib.SMTP("smtp.gmail.com", 587) as serveur:
        serveur.starttls()
        serveur.login(GMAIL_ADDR, GMAIL_PASS)
        serveur.send_message(msg)

#test
"""if __name__ == "__main__":
    # envoie un mail de test à toi-même
    for mail in ["mail@example.com", "mail2@example.com"]: 
        mon_email = mail
        lien_test = "https://cer-tif.com/confirmer/test123"
        envoyer_mail_confirmation(mon_email, lien_test)
        print("Mail envoyé ! Va vérifier ta boîte de réception.")"""