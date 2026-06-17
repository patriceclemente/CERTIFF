import sqlite3
import os

DB_PATH = os.path.join("DB", "DB.db")   # adapte si besoin

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# récupère le nom de toutes les tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [ligne[0] for ligne in cursor.fetchall()]

for table in tables:
    print(f"\n========== TABLE : {table} ==========")
    # noms des colonnes
    cursor.execute(f"PRAGMA table_info({table})")
    colonnes = [col[1] for col in cursor.fetchall()]
    print(" | ".join(colonnes))
    print("-" * 50)
    # contenu
    cursor.execute(f"SELECT * FROM {table}")
    lignes = cursor.fetchall()
    if not lignes:
        print("(vide)")
    for ligne in lignes:
        print(" | ".join(str(valeur) for valeur in ligne))

conn.close()