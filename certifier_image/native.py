from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path


def convertir_en_png(chemin_entree: str, chemin_sortie: str | None = None) -> None:
    from PIL import Image

    input_path = Path(chemin_entree)
    if input_path.suffix.lower() == ".png":
        print("L'image est deja au format PNG.")
        return

    output_path = Path(chemin_sortie) if chemin_sortie else input_path.with_suffix(".png")
    with Image.open(input_path) as img:
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        img.save(output_path, format="PNG")
    print(f"Image sauvegardee : {output_path}")


def derive_key(password: str, salt: bytes) -> bytes:
    from Crypto.Protocol.KDF import PBKDF2

    return PBKDF2(password.encode(), salt, dkLen=32, count=100_000)


def chiffrer(message: str, password: str) -> bytes:
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes

    salt = get_random_bytes(16)
    nonce = get_random_bytes(12)
    key = derive_key(password, salt)

    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(message.encode("utf-8"))
    return salt + nonce + tag + ciphertext


def dechiffrer(data: bytes, password: str) -> str:
    from Crypto.Cipher import AES

    salt = data[:16]
    nonce = data[16:28]
    tag = data[28:44]
    ciphertext = data[44:]

    key = derive_key(password, salt)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    try:
        return cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8")
    except ValueError as error:
        raise ValueError("Mot de passe incorrect ou donnees corrompues.") from error


def bytes_en_bits(data: bytes):
    for byte in data:
        for i in range(7, -1, -1):
            yield (byte >> i) & 1


def cacher_message(image_path: str, message: str, password: str, output_path: str) -> None:
    from PIL import Image

    img = Image.open(image_path).convert("RGBA")
    pixels = list(img.getdata())
    payload = chiffrer(message, password)
    header = struct.pack(">I", len(payload))
    bits = list(bytes_en_bits(header + payload))

    capacite = len(pixels) * 3
    if len(bits) > capacite:
        raise ValueError(f"Image trop petite : capacite {capacite} bits, message necessite {len(bits)} bits.")

    nouveaux_pixels = []
    bit_idx = 0
    for r, g, b, a in pixels:
        canaux = [r, g, b]
        for i in range(3):
            if bit_idx < len(bits):
                canaux[i] = (canaux[i] & 0xFE) | bits[bit_idx]
                bit_idx += 1
        nouveaux_pixels.append((*canaux, a))

    img.putdata(nouveaux_pixels)
    img.save(output_path, format="PNG")
    print(f"[OK] Message cache dans '{output_path}' ({len(payload)} octets chiffres).")


def extraire_message(image_path: str, password: str) -> str:
    from PIL import Image

    img = Image.open(image_path).convert("RGBA")
    pixels = list(img.getdata())

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

    taille = struct.unpack(">I", bits_en_bytes(bits, 4))[0]
    payload = bits_en_bytes(bits[32:], taille)
    return dechiffrer(payload, password)


def hash_image(image_path: str) -> bytes:
    from PIL import Image

    img = Image.open(image_path).convert("RGBA")
    return hashlib.sha256(bytes(img.tobytes())).digest()


def verif_sign(image_path: str, signature: bytes) -> bool:
    return hash_image(image_path) == signature


def parse_legacy_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Commandes Python natives historiques.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    convert_parser = subparsers.add_parser("convert", help="Convertir l'image en PNG")
    convert_parser.add_argument("--input", required=True)
    convert_parser.add_argument("--output")

    steg_parser = subparsers.add_parser("filigrane_invisible", help="Cacher un message chiffre dans une image")
    steg_parser.add_argument("--input", required=True)
    steg_parser.add_argument("--msg", required=True)
    steg_parser.add_argument("--password", required=True)
    steg_parser.add_argument("--output", required=True)

    signature_parser = subparsers.add_parser("signature_hash", help="Creer un hash de l'image")
    signature_parser.add_argument("--image", required=True)

    verif_parser = subparsers.add_parser("signature_verif", help="Verifier une signature hash")
    verif_parser.add_argument("--image", required=True)
    verif_parser.add_argument("--signature", required=True)

    read_parser = subparsers.add_parser("lecture_filigrane_invisible", help="Lire le filigrane invisible natif")
    read_parser.add_argument("--input", required=True)
    read_parser.add_argument("--password", required=True)

    return parser.parse_args(argv)


def run_legacy_command(argv: list[str]) -> bool:
    args = parse_legacy_args(argv)
    try:
        if args.command == "convert":
            convertir_en_png(args.input, args.output)
        elif args.command == "filigrane_invisible":
            cacher_message(args.input, args.msg, args.password, args.output)
        elif args.command == "signature_hash":
            print(hash_image(args.image).hex())
        elif args.command == "signature_verif":
            print(verif_sign(args.image, bytes.fromhex(args.signature)))
        elif args.command == "lecture_filigrane_invisible":
            print(extraire_message(args.input, args.password))
        else:
            return False
    except Exception as error:
        print(f"[ERROR] {error}")
        return False
    return True

