from PIL import Image
import os

def convertir_en_png(chemin_entree, chemin_sortie=None):

    if(os.path.splitext(chemin_entree)[1]==".png"):
        print("L'image est déjà au format PNG.")
        return
    
    # Générer le nom de sortie automatiquement si non fourni
    if chemin_sortie is None:
        base = os.path.splitext(chemin_entree)[0]
        chemin_sortie = base + ".png"
    
    with Image.open(chemin_entree) as img:
        # Convertir en RGBA si nécessaire (pour transparence)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        
        img.save(chemin_sortie, format="PNG")
        print(f"Image sauvegardée : {chemin_sortie}")

# Utilisation
convertir_en_png("/home/manu/Documents/INSA/projet_application/Projet-Application-3A/python/JPEG_example_flower.png")