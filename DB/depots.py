
"""fonctions de gestion de l'historique des utilisateurs"""

import sqlite3
import hashlib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))       # dossier du script
DB_PATH = os.path.join(BASE_DIR, "DB.db")                   # chemin de la base
STOCKAGE_DIR = os.path.join(BASE_DIR, "stockage")           # dossier stockage
RAW_UPLOAD_DIR = os.path.join(STOCKAGE_DIR, "raw_uploads")  # dossier stockage temporaire
COOKED_UPLOAD_DIR = os.path.join(STOCKAGE_DIR, "cooked_uploads")  # dossier stockage de fichier traités (ou en cours de traitement)



#################################
######CREATION DES TABLES########
#################################

def create_history_table():
    """Crée la table de tout les fichiers déposés si elle n'existent pas"""
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
    conn.commit()
    conn.close()

def create_status_table(): 
    """Crée la table des statuts de depots si elle n'existe pas"""
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
    conn.commit()
    conn.close()


#################################
######GESTION DES DEPOTS########
#################################
def enregistrer_mdp_img(user_id, nom_fichier, mdp):
    """Enregistre le mot de passe d'une image déposée (pour la steganographie)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE depots
        SET mdp_img = ?
        WHERE user_id = ? AND nom_fichier = ?
    """, (mdp, user_id, nom_fichier))
    conn.commit()
    conn.close()

def enregistrer_depot(user_id, file_name, file_content): #chemin doit devenir CHEMIN
    """Enregistre un dépôt : écrit le contenu dans STOCKAGE_DIR et ajoute une ligne en base.
    Retourne (depot_id, chemin_stockage)."""
     
    print(f"Enregistrement du dépôt pour l'utilisateur {user_id} : {file_name}")

    hash_fichier = hashlib.sha256(file_content).hexdigest()
    taille = len(file_content)

    # écrire le fichier dans le dossier de stockage, nommé par son hash
    os.makedirs(RAW_UPLOAD_DIR, exist_ok=True)
    chemin_stockage = os.path.join(RAW_UPLOAD_DIR, hash_fichier)
    with open(chemin_stockage, "wb") as f:
        f.write(file_content)

    # Extraire l'extension depuis le nom de fichier
    extension = os.path.splitext(file_name)[1].lower()  # ex: ".png"
    # ajouter les infos dans la base
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO depots (user_id, nom_fichier, hash_fichier, taille, extension)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, file_name, hash_fichier, taille, extension))
    conn.commit()
    depot_id = cursor.lastrowid
    conn.close()

    return depot_id, chemin_stockage 

def supprimer_depot(depot_id):
    """Supprime un dépôt : efface le fichier du stockage et la ligne en base."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # récupérer le hash du fichier pour pouvoir le supprimer
    cursor.execute("SELECT hash_fichier FROM depots WHERE depot_id = ?", (depot_id,))
    ligne = cursor.fetchone()
    if not ligne:
        conn.close()
        raise ValueError("Depot non trouvé")
    hash_fichier = ligne[0]
    # supprimer le fichier du stockage
    chemin_stockage = os.path.join(RAW_UPLOAD_DIR, hash_fichier)
    if os.path.exists(chemin_stockage):
        os.remove(chemin_stockage)
    # supprimer la ligne en base
    cursor.execute("DELETE FROM depots WHERE depot_id = ?", (depot_id,))
    conn.commit()
    conn.close()

def enregistrer_traitement(depot_id, traitement, status):
    """Enregistre le statut d'un traitement sur un dépôt (najout pas dans le dossier de stockage COOKED_UPLOAD_DIR)"""
    if status not in ("en_cours", "termine", "echec"):
        raise ValueError("Status invalide")
    if traitement not in ("signature", "blockchain", "meta-data", "watermarking", "steganographie"):
        raise ValueError("Traitement invalide")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO statuts (depot_id, traitement, status)
        VALUES (?, ?, ?)
    """, (depot_id, traitement, status))
    conn.commit()
    conn.close()

def supprimer_traitement(depot_id, traitement):
    """Supprime le statut d'un traitement sur un dépôt"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM statuts
        WHERE depot_id = ? AND traitement = ?
    """, (depot_id, traitement))
    conn.commit()
    conn.close()

def modifier_status_traitement(depot_id, traitement, nouveau_status):
    """Modifie le statut d'un traitement sur un dépôt"""
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
    """Modifie/Ajoute le mot de passe de signature/steganographie d'un dépôt"""
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

def lister_depots(user_id):
    """Retourne la liste des dépôts pour un utilisateur donné"""
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
    """Retourne la liste des statuts pour un dépôt donné"""
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
