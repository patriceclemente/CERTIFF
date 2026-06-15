from PIL import Image
import os
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
import struct
import hashlib

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
# convertir_en_png("/home/manu/Documents/INSA/projet_application/Projet-Application-3A/python/JPEG_example_flower.png")

# chiffrement / clef 

def derive_key(password: str, salt: bytes) -> bytes:
    """Dérive une clé AES-256 depuis le mot de passe + sel."""
    return PBKDF2(password.encode(), salt, dkLen=32, count=100_000)

def chiffrer(message: str, password: str) -> bytes:
    """Chiffre le message avec AES-GCM. Retourne salt+nonce+tag+ciphertext."""
    salt  = get_random_bytes(16)
    nonce = get_random_bytes(12)
    key   = derive_key(password, salt)

    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(message.encode("utf-8"))

    return salt + nonce + tag + ciphertext

def dechiffrer(data: bytes, password: str) -> str:
    """Déchiffre les données. Lève ValueError si le mot de passe est faux."""
    salt       = data[:16]
    nonce      = data[16:28]
    tag        = data[28:44]
    ciphertext = data[44:]

    key    = derive_key(password, salt)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)

    try:
        return cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8")
    except ValueError:
        raise ValueError("Mot de passe incorrect ou données corrompues.")


# stegano 

def bytes_en_bits(data: bytes):
    """Convertit des bytes en liste de bits (0/1)."""
    for byte in data:
        for i in range(7, -1, -1):
            yield (byte >> i) & 1

def cacher_message(image_path: str, message: str, password: str, output_path: str):
    """
    Cache un message chiffré dans les LSB des pixels de l'image.
    
    - image_path  : chemin de l'image PNG source
    - message     : texte à cacher
    - password    : mot de passe pour chiffrer
    - output_path : chemin de l'image de sortie
    """
    img = Image.open(image_path).convert("RGBA")
    pixels = list(img.getdata())

    # Chiffrement du message
    payload = chiffrer(message, password)

    # En-tête : 4 octets pour la taille du payload
    header = struct.pack(">I", len(payload))
    bits   = list(bytes_en_bits(header + payload))

    # Vérification de la capacité (1 bit par canal R,G,B → 3 bits/pixel)
    capacite = len(pixels) * 3
    if len(bits) > capacite:
        raise ValueError(
            f"Image trop petite : capacité {capacite} bits, "
            f"message nécessite {len(bits)} bits."
        )

    # Injection des bits dans les LSB des canaux R, G, B
    nouveaux_pixels = []
    bit_idx = 0

    for r, g, b, a in pixels:
        canaux = [r, g, b]
        for i in range(3):
            if bit_idx < len(bits):
                canaux[i] = (canaux[i] & 0xFE) | bits[bit_idx]
                bit_idx += 1
        nouveaux_pixels.append((*canaux, a))

    # Sauvegarde
    img.putdata(nouveaux_pixels)
    img.save(output_path, format="PNG")
    print(f"✅ Message caché dans '{output_path}' ({len(payload)} octets chiffrés).")

def extraire_message(image_path: str, password: str) -> str:
    """
    Extrait et déchiffre le message caché dans l'image.
    
    - image_path : chemin de l'image PNG stéganographiée
    - password   : mot de passe pour déchiffrer
    """
    img    = Image.open(image_path).convert("RGBA")
    pixels = list(img.getdata())

    # Extraction des LSB (canaux R, G, B uniquement)
    bits = []
    for r, g, b, _ in pixels:
        bits += [(r & 1), (g & 1), (b & 1)]

    def bits_en_bytes(bits_list, n_bytes):
        result = bytearray()
        for i in range(n_bytes):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | bits_list[i * 8 + j]
            result.append(byte)
        return bytes(result)

    # Lecture de l'en-tête (32 premiers bits = taille du payload)
    taille = struct.unpack(">I", bits_en_bytes(bits, 4))[0]

    # Lecture du payload
    payload = bits_en_bytes(bits[32:], taille)

    return dechiffrer(payload, password)

# signature

def hash_image(image_path: str) -> bytes:
    """Calcule le SHA-256 des pixels bruts de l'image (sans métadonnées)."""
    img = Image.open(image_path).convert("RGBA")
    pixels_bytes = bytes(img.tobytes())  # pixels bruts uniquement
    return hashlib.sha256(pixels_bytes).digest()  # 32 octets

if __name__ == "__main__":
    # Cacher un message
    # Trouve le dossier où se trouve le script actuel (le sous-dossier 'python')
    dossier_script = os.path.dirname(os.path.abspath(__file__))
    chemin_brut = os.path.join(dossier_script, "..", "image", "JPEG_example_flower.jpg")
    print(f"[DEBUG] Le chemin nettoyé est : {chemin_brut}")
    cacher_message(
        image_path = chemin_brut,
        message     = "message steg cache",
        password    = "azerty",
        output_path = "image_steg.png"
    )

    # Extraire le message
    texte = extraire_message("image_steg.png", "azerty")
    print(f"Message extrait : {texte}")
