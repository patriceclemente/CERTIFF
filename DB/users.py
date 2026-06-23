import sqlite3
import hashlib
import os
import re
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "DB.db")   

def create_users_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # username et email unique
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            mdp_hash TEXT NOT NULL,
            sel TEXT NOT NULL,
            confirmed INTEGER DEFAULT 0,
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def confirm_user(email):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET confirmed = 1 WHERE email = ?", (email,))
    conn.commit()
    modifie = cursor.rowcount > 0
    conn.close()
    return modifie


def get_user_id(identifiant):
    """Retourne l'user_id à partir de l'email ou du username, ou None."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id FROM users WHERE email = ? OR username = ?",
        (identifiant, identifiant)
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_username(user_id):
    """Retourne le username à partir de l'user_id, ou None."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def create_user(username, email, mot_de_passe):
    #precheck si l'email ou le username existe déjà
    if check_user_exists(email):
        return "email_pris"
    if username_exists(username):
        return "username_pris"
    if len(mot_de_passe) < 8:
        return "mdp_trop_court"
    if not re.search(r"\d", mot_de_passe):          # au moins un chiffre
        return "mdp_pas_chiffre"
    if not re.search(r"[^A-Za-z0-9]", mot_de_passe): # au moins un caractère spécial
        return "mdp_pas_special"
    # générer un sel aléatoire unique
    sel = os.urandom(16).hex()          # 16 octets aléatoires, en texte hexa
    # hasher le mot de passe
    mdp_hash = hashlib.pbkdf2_hmac(
        "sha256",                        # algo interne
        mot_de_passe.encode("utf-8"),    # le mdp en octets
        bytes.fromhex(sel),              # le sel en octets
        100000                           # nombre d'itérations (= lenteur voulue)
    ).hex()
    # insérer en base
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, email, mdp_hash, sel) VALUES (?, ?, ?, ?)",
            (username, email, mdp_hash, sel)
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        if "email" in str(e):
            return "email_pris"
        elif "username" in str(e):
            return "username_pris"
        return None
    finally:
        conn.close()
    return "user_created"

def create_test_user():
    """Crée un utilisateur de test si la table est vide."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    if count == 0:
        print("Création d'un utilisateur de test : testuser / testp@ss1")
        return create_user("testuser", "test@fakemailbox.com", "testp@ss1") and confirm_user("test@fakemailbox.com")

    return None

def verif_id(identifiant, mot_de_passe):
    """Vérifie un couple (identifiant, mot de passe).
    'identifiant' peut être l'email OU le username.
    Retourne : 'ok', 'non_confirme' ou 'invalide'."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT mdp_hash, sel, confirmed FROM users WHERE email = ? OR username = ?",
        (identifiant, identifiant)
    )
    result = cursor.fetchone()
    conn.close()
    if result is None:
        return "invalide"  # utilisateur non trouvé
    mdp_hash_stored, sel, confirmed = result
    # hasher le mot de passe fourni avec le même sel
    mdp_hash_provided = hashlib.pbkdf2_hmac(
        "sha256",
        mot_de_passe.encode("utf-8"),
        bytes.fromhex(sel),
        100000
    ).hex()
    if mdp_hash_provided != mdp_hash_stored:
        return "invalide"  # mauvais mot de passe
    if not confirmed:
        return "non_confirme"  # compte pas encore confirmé par mail
    return "ok"

def get_user_id(identifiant):
    """Retourne l'user_id à partir de l'email ou du username, ou None."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id FROM users WHERE email = ? OR username = ?",
        (identifiant, identifiant)
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def modif_pw(email, nouveau_mdp):
    # générer un nouveau sel
    sel = os.urandom(16).hex()
    # hasher le nouveau mot de passe
    mdp_hash = hashlib.pbkdf2_hmac(
        "sha256",
        nouveau_mdp.encode("utf-8"),
        bytes.fromhex(sel),
        100000
    ).hex()
    # mettre à jour en base
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET mdp_hash = ?, sel = ? WHERE email = ?",
        (mdp_hash, sel, email)
    )
    conn.commit()
    conn.close()

def modif_username(email, nouveau_username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET username = ? WHERE email = ?",
        (nouveau_username, email)
    )
    conn.commit()
    conn.close()

def delete_user(email):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE email = ?", (email,))
    conn.commit()
    conn.close()

def check_user_exists(email):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE email = ?", (email,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def username_exists(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    existe = cursor.fetchone() is not None
    conn.close()
    return existe
