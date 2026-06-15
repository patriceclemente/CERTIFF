import sqlite3
import hashlib
import os

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
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def creer_utilisateur(username, email, mot_de_passe):
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
    cursor.execute(
        "INSERT INTO users (username, email, mdp_hash, sel) VALUES (?, ?, ?, ?)",
        (username, email, mdp_hash, sel)
    )
    conn.commit()
    conn.close()

def verifier_identifiants(username ,email, mot_de_passe):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT mdp_hash, sel FROM users WHERE email = ? OR username = ?", (email, username))
    result = cursor.fetchone()
    conn.close()
    if result is None:
        return False  # utilisateur non trouvé
    mdp_hash_stored, sel = result
    # hasher le mot de passe fourni avec le même sel
    mdp_hash_provided = hashlib.pbkdf2_hmac(
        "sha256",
        mot_de_passe.encode("utf-8"),
        bytes.fromhex(sel),
        100000
    ).hex()
    return mdp_hash_provided == mdp_hash_stored

def modifie_mdp(email, nouveau_mdp):
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

def modifie_username(email, nouveau_username):
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

