
"""fonctions de gestion de l'historique des utilisateurs"""

import sqlite3
import hashlib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))    # dossier du script
DB_PATH = os.path.join(BASE_DIR, "DB.db")                # chemin de la base
STOCKAGE_DIR = os.path.join(BASE_DIR, "stockage")        # dossier des fichiers
STOCKAGE_BRUT_DIR = os.path.join(STOCKAGE_DIR, "brut")  # dossier des images bruts
#CHEMIN=     # chemin vers les fichier deposer


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

def enregistrer_depot(user_id, nom_fichier, contenu):
    """Enregistre un dépôt à partir du contenu (octets) et du nom d'origine.
    Retourne (depot_id, chemin_stockage)."""
    hash_fichier = hashlib.sha256(contenu).hexdigest()
    taille = len(contenu)
    # écrire le fichier dans le dossier de stockage, nommé par son hash
    os.makedirs(STOCKAGE_DIR, exist_ok=True)
    os.makedirs(STOCKAGE_BRUT_DIR, exist_ok=True)
    chemin_stockage = os.path.join(STOCKAGE_BRUT_DIR, hash_fichier)
    with open(chemin_stockage, "wb") as f:
        f.write(contenu)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO depots (user_id, nom_fichier, hash_fichier, taille)
        VALUES (?, ?, ?, ?)
    """, (user_id, nom_fichier, hash_fichier, taille))
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
    chemin_stockage = os.path.join(STOCKAGE_DIR, hash_fichier)
    if os.path.exists(chemin_stockage):
        os.remove(chemin_stockage)
    # supprimer la ligne en base
    cursor.execute("DELETE FROM depots WHERE depot_id = ?", (depot_id,))
    conn.commit()
    conn.close()

def enregistrer_traitement(depot_id, traitement, status):
    """Enregistre le statut d'un traitement sur un dépôt"""
    if status not in ("en cours", "terminé", "échoué", "non traité"):
        raise ValueError("Status invalide")
    if traitement not in ("signature", "blockchain", "meta-data", "watermarking_v", "steganographie", "watermarking_i"):
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE statuts
        SET status = ?
        WHERE depot_id = ? AND traitement = ?
    """, (nouveau_status, depot_id, traitement))
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
