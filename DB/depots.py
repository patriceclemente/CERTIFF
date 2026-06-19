"""fonctions de gestion de l'historique des utilisateurs"""

import sqlite3
import hashlib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))       # dossier du script
DB_PATH = os.path.join(BASE_DIR, "DB.db")                   # chemin de la base
STOCKAGE_DIR = os.path.join(BASE_DIR, "stockage")           # dossier stockage
RAW_UPLOAD_DIR = os.path.join(STOCKAGE_DIR, "raw_uploads")  # images d'origine
COOKED_UPLOAD_DIR = os.path.join(STOCKAGE_DIR, "cooked_uploads")  # images traitées


#################################
######CREATION DES TABLES########
#################################

def create_history_table():
    """Crée la table de tous les fichiers déposés si elle n'existe pas."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS depots (
            depot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            nom_fichier TEXT NOT NULL,
            hash_fichier TEXT NOT NULL,
            extension TEXT NOT NULL,
            date_depot TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            taille INTEGER NOT NULL,
            mdp_stgno TEXT DEFAULT 'password',
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    # une même image (même hash) ne peut exister qu'une fois par utilisateur.
    # try/except : si des doublons existent encore (migration pas lancée),
    # on ne crée pas l'index plutôt que de planter au démarrage.
    try:
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_depots_user_hash
            ON depots(user_id, hash_fichier)
        """)
    except sqlite3.IntegrityError:
        print("[depots] doublons présents : lancez migrate_storage.py (index user/hash non créé)")
    conn.commit()
    conn.close()


def create_status_table():
    """Crée la table des statuts de dépôts si elle n'existe pas."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS statuts (
            depot_id INTEGER NOT NULL,
            traitement TEXT NOT NULL,
            status TEXT NOT NULL,
            date_application TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (depot_id) REFERENCES depots(depot_id)
        )
    """)
    # un seul statut par (depot, traitement) -> nécessaire pour l'upsert.
    try:
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_statuts_depot_traitement
            ON statuts(depot_id, traitement)
        """)
    except sqlite3.IntegrityError:
        print("[statuts] doublons présents : lancez migrate_storage.py (index depot/traitement non créé)")
    conn.commit()
    conn.close()


#################################
######GESTION DES DEPOTS#########
#################################

def enregistrer_mdp_img(user_id, nom_fichier, mdp):
    """Enregistre le mot de passe d'une image déposée (stéganographie)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE depots
        SET mdp_stgno = ?
        WHERE user_id = ? AND nom_fichier = ?
    """, (mdp, user_id, nom_fichier))
    conn.commit()
    conn.close()


def enregistrer_depot(user_id, file_name, file_content):
    """Enregistre un dépôt : écrit l'original dans raw_uploads (nommé par son
    hash) et ajoute une ligne en base. REPRISE PAR HASH : si une image de même
    hash existe déjà pour cet utilisateur, on réutilise son depot_id sans créer
    de doublon. Retourne (depot_id, chemin_stockage)."""

    print(f"Enregistrement du dépôt pour l'utilisateur {user_id} : {file_name}")

    hash_fichier = hashlib.sha256(file_content).hexdigest()
    taille = len(file_content)

    # écrire le fichier original (idempotent : même hash = même contenu)
    os.makedirs(RAW_UPLOAD_DIR, exist_ok=True)
    chemin_stockage = os.path.join(RAW_UPLOAD_DIR, hash_fichier)
    if not os.path.exists(chemin_stockage):
        with open(chemin_stockage, "wb") as f:
            f.write(file_content)

    extension = os.path.splitext(file_name)[1].lower()  # ex: ".png"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # reprise : ce hash existe-t-il déjà pour cet utilisateur ?
        cursor.execute(
            "SELECT depot_id FROM depots WHERE user_id = ? AND hash_fichier = ?",
            (user_id, hash_fichier),
        )
        existant = cursor.fetchone()
        if existant:
            return existant[0], chemin_stockage

        # sinon, nouveau dépôt
        try:
            cursor.execute("""
                INSERT INTO depots (user_id, nom_fichier, hash_fichier, taille, extension)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, file_name, hash_fichier, taille, extension))
            conn.commit()
            return cursor.lastrowid, chemin_stockage
        except sqlite3.IntegrityError:
            # course possible avec l'index unique : on relit l'existant
            cursor.execute(
                "SELECT depot_id FROM depots WHERE user_id = ? AND hash_fichier = ?",
                (user_id, hash_fichier),
            )
            ligne = cursor.fetchone()
            return (ligne[0] if ligne else None), chemin_stockage
    finally:
        conn.close()


def supprimer_depot(depot_id):
    """Supprime un dépôt : efface le fichier raw, le cooked, et la ligne en base."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT hash_fichier FROM depots WHERE depot_id = ?", (depot_id,))
    ligne = cursor.fetchone()
    if not ligne:
        conn.close()
        raise ValueError("Depot non trouvé")
    hash_fichier = ligne[0]

    raw = os.path.join(RAW_UPLOAD_DIR, hash_fichier)
    if os.path.exists(raw):
        os.remove(raw)
    cooked = os.path.join(COOKED_UPLOAD_DIR, f"{depot_id}.png")
    if os.path.exists(cooked):
        os.remove(cooked)

    cursor.execute("DELETE FROM depots WHERE depot_id = ?", (depot_id,))
    cursor.execute("DELETE FROM statuts WHERE depot_id = ?", (depot_id,))
    conn.commit()
    conn.close()


def enregistrer_traitement(depot_id, traitement, status):
    """Enregistre/MET À JOUR le statut d'un traitement sur un dépôt.
    UPSERT : un seul statut par (depot_id, traitement), pas de doublon."""
    if status not in ("en_cours", "termine", "echec"):
        raise ValueError("Status invalide")
    if traitement not in ("signature", "blockchain", "meta-data", "watermarking", "steganographie"):
        raise ValueError("Traitement invalide")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO statuts (depot_id, traitement, status, date_application)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(depot_id, traitement) DO UPDATE SET
            status = excluded.status,
            date_application = excluded.date_application
    """, (depot_id, traitement, status))
    conn.commit()
    conn.close()


def supprimer_traitement(depot_id, traitement):
    """Supprime le statut d'un traitement sur un dépôt."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM statuts
        WHERE depot_id = ? AND traitement = ?
    """, (depot_id, traitement))
    conn.commit()
    conn.close()


def modifier_status_traitement(depot_id, traitement, nouveau_status):
    """Modifie le statut d'un traitement sur un dépôt."""
    if nouveau_status not in ("en_cours", "termine", "echec"):
        raise ValueError("Status invalide")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE statuts
        SET status = ?
        WHERE depot_id = ? AND traitement = ?
    """, (nouveau_status, depot_id, traitement))
    conn.commit()
    conn.close()


def modifier_mdp_stgno_depot(depot_id, mdp_stgno):
    """Modifie/Ajoute le mot de passe de signature/steganographie d'un dépôt."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE depots
        SET mdp_stgno = ?
        WHERE depot_id = ?
    """, (mdp_stgno, depot_id))
    conn.commit()
    conn.close()


#################################
#######EXTRACTIONS INFO##########
#################################

def compter_traitements_termines(depot_id):
    """Nombre de traitements terminés (status 'termine') pour un dépôt."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM statuts WHERE depot_id = ? AND status = 'termine'",
        (depot_id,),
    )
    n = cursor.fetchone()[0]
    conn.close()
    return n


def chemin_image_courante(depot_id, hash_fichier):
    """Retourne le chemin de l'image la PLUS TRAITÉE pour ce dépôt :
    - cooked_uploads/<depot_id>.png si elle existe (version traitée),
    - sinon raw_uploads/<hash> (l'originale),
    - sinon None."""
    cooked = os.path.join(COOKED_UPLOAD_DIR, f"{depot_id}.png")
    if os.path.isfile(cooked):
        return cooked
    raw = os.path.join(RAW_UPLOAD_DIR, hash_fichier)
    if os.path.isfile(raw):
        return raw
    return None


def lister_depots(user_id):
    """Retourne la liste des dépôts pour un utilisateur donné (1 ligne par image)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nom_fichier, hash_fichier, date_depot, taille
        FROM depots
        WHERE user_id = ?
        ORDER BY date_depot DESC
    """, (user_id,))
    depots = cursor.fetchall()
    conn.close()
    return depots


def lister_statuts(depot_id):
    """Retourne la liste des statuts pour un dépôt donné."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT traitement, status, date_application
        FROM statuts
        WHERE depot_id = ?
        ORDER BY date_application DESC
    """, (depot_id,))
    statuts = cursor.fetchall()
    conn.close()
    return statuts