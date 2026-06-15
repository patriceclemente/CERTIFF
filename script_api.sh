#!/bin/bash
# =======================================================
# protect_image.sh
# Pipeline complet de protection d'image :
# filigrane visible/invisible, EXIF, signature, blockchain
# auteur : Patrice Clemente
# création : 19/09/2025
# révision : 15/10/2025
# =======================================================

set -e

# -------------------------------------------------------
# Paramètres par défaut
# -------------------------------------------------------
MODE_INTERACTIVE=false
WM_MODE="auto"

# Watermark visible par défaut
PLACE_MODE="all"
WM_TEXT="© Cert-Art.fr"
WM_TEXT_COLOR="128,128,128"
WM_SPACING=300
WM_POINTSIZE=35
WM_OPACITY=0.2
WM_COLOR="128,128,128"
WM_ANGLE=-45
WM_FONT="Arial-Bold"
WM_STROKE_COLOR="0,0,0"
WM_STROKE_WIDTH=0.2

# Stéganographie
MESSAGE="defaut"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENSTEGO_JAR="$SCRIPT_DIR/openstego.jar"
OTS_BIN="ots"

# Mot de passe par défaut
DEFAULT_PW="defaut"

# -------------------------------------------------------
# Fonctions utilitaires
# -------------------------------------------------------
usage() {
  echo "Usage: $0 [options] base_dir image.png [exif_date]"
  echo "Options :"
  echo "  -i, --interactive            : mode interactif"
  echo "  -h, --help                   : afficher cette aide"
  echo "  --wm-mode skip|manual|auto   : mode watermark (défaut: auto)"
  echo "  --wm-text \"texte\"           : texte watermark"
  echo "  --wm-spacing N               : espacement (px)"
  echo "  --wm-size N                  : taille police"
  echo "  --wm-opacity 0.x             : opacité"
  echo "  --wm-color \"R,G,B\"          : couleur texte"
  echo "  --wm-angle N                 : angle"
  echo "  --wm-font \"NomPolice\"       : police"
  echo "  --stegano-message \"texte\"   : message à cacher (défaut: psychepsyche)"
  echo "  --check                      : vérifier dépendances"
  echo
  echo "Options stéganographie :"
  echo "   --stegano-message \"texte\"   : message à cacher (défaut: psychepsyche)"
  echo
  echo "Autres options :"
  echo "   -i, --interactive            : mode interactif"
  echo "   -h, --help                   : afficher cette aide"
  echo "   --check                      : vérifier dépendances"
  echo
  echo "Exemples pratiques :"
  echo "  1. Pipeline complet avec watermark auto par défaut :"
  echo "     $0 /Users/admin/Pictures image.png"
  echo
  echo "  2. Ajouter watermark personnalisé rouge et opaque :"
  echo "      $0 /Users/admin/Pictures image.png --wm-text \"Confidentiel\" --wm-color \"255,0,0\" --wm-opacity 0.7 --wm-size 24 --wm-angle -30"
  echo
  echo "  3. Filigrane dense en diagonale serrée :"
  echo "     $0 /path image.png --wm-spacing 100 --wm-angle -30"
  echo
  echo "  4. Utiliser une police spécifique (ex. Arial-Bold) :"
  echo "     $0 /path image.png --wm-font \"Arial-Bold\""
  echo
  echo "  5. Mode interactif avec choix manuel à chaque étape :"
  echo "     $0 -i /path image.png"
  echo
  echo "  6. Sauter totalement l'étape watermark (filigrane visible) :"
  echo "     $0 /path image.png --wm-mode skip"
  echo
  echo "  7. Vérifier uniquement les dépendances :"
  echo "     $0 --check"
  echo
  echo "  8. Créer un nouveau message stegano :"
  echo "   $0 ... --stegano-message \"SecretProject42\""
  exit 0
}

detect_os() { [[ "$OSTYPE" == "darwin"* ]] && echo "macOS" || ([[ -f /etc/debian_version ]] && echo "debian" || echo "other"); }
install_package() { local pkg="$1"; local os="$2"; [[ "$os" == "macOS" ]] && brew install "$pkg" || ([[ "$os" == "debian" ]] && sudo apt update && sudo apt install -y "$pkg") || echo "Installer $pkg manuellement"; }
check_command() { local cmd="$1"; local pkg="$2"; local os="$3"; command -v "$cmd" >/dev/null 2>&1 || install_package "$pkg" "$os"; }

check_dependencies() {
  echo "[INFO] Vérification des dépendances..."
  local os=$(detect_os)
  check_command "bash" "bash" "$os"
  check_command "exiftool" "exiftool" "$os"
  check_command "java" "openjdk" "$os"
  check_command "$OTS_BIN" "opentimestamps-client" "$os"
  check_command "magick" "imagemagick" "$os"
  [ ! -f "$OPENSTEGO_JAR" ] && echo "❌ OpenStego JAR introuvable" && exit 1
  echo "[OK] Dépendances prêtes"
}

#ensure_dir() { [ ! -d "$1" ] && mkdir -p "$1"; }

# ensure_dir() {
#     [ -n "$1" ] || return 0
#     [ ! -d "$1" ] && mkdir -p "$1"
# }

ensure_dir() {
    if [ -z "$1" ]; then
        echo "[WARN] ensure_dir: chemin vide"
        return 1
    fi

    if [ ! -d "$1" ]; then
        mkdir -p "$1" 2>/dev/null || {
            echo "[ERROR] Impossible de créer le dossier : '$1'"
            return 1  # n'arrête pas tout le script si set -e est actif
        }
    fi
}


# -------------------------------------------------------
# Parsing options
# -------------------------------------------------------
POSITIONAL_ARGS=()
while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help) usage ;;
    -i|--interactive) MODE_INTERACTIVE=true ;;
    --wm-mode) shift; WM_MODE="$1" ;;
    --wm-text) shift; WM_TEXT="$1" ;;
    --wm-spacing) shift; WM_SPACING="$1" ;;
    --wm-size) shift; WM_POINTSIZE="$1" ;;
    --wm-opacity) shift; WM_OPACITY="$1" ;;
    --wm-color) shift; WM_COLOR="$1" ;;
    --wm-angle) shift; WM_ANGLE="$1" ;;
    --wm-font) shift; WM_FONT="$1" ;;
    --stegano-message) shift; MESSAGE="$1" ;;
    --check) check_dependencies; exit 0 ;;
    *) POSITIONAL_ARGS+=("$1") ;;
  esac
  shift
done
set -- "${POSITIONAL_ARGS[@]}"

# -------------------------------------------------------
# Mode API CLI / action dispatcher
# Exemples :
#   bash protect_image_api.sh visible ./projet image.png
#   bash protect_image_api.sh exif ./projet image.png
#   bash protect_image_api.sh pipeline ./projet image.png
#
# Compatibilité avec l'ancien usage :
#   bash protect_image_api.sh ./projet image.png
# lance le pipeline complet.
# -------------------------------------------------------
KNOWN_ACTIONS=" visible exif stegano signature blockchain check_stegano check_signature check_blockchain show_exif report pipeline "

if [[ " $KNOWN_ACTIONS " == *" ${1:-} "* ]]; then
  ACTION="$1"
  shift || true
else
  ACTION="pipeline"
fi

# Si on donne seulement l'image après l'action, BASE_DIR vaut "."
if [[ $# -eq 1 ]]; then
  BASE_DIR="."
  INPUT_IMG="$1"
  EXIF_CUSTOM_DATE=""
else
  BASE_DIR="${1:-.}"
  INPUT_IMG="$2"
  EXIF_CUSTOM_DATE="$3"
fi

STATE_FILE="${STATE_FILE:-/tmp/last_img.txt}"

# =======================================================
# Mode interactif : 
# =======================================================
# -------------------------------------------------------
# sélection dossier puis image
# -------------------------------------------------------
if $MODE_INTERACTIVE && [[ -z "$INPUT_IMG" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  ROOT_DIR="$SCRIPT_DIR/images_brutes"

  echo "=== Sélection du dossier contenant l'image ==="
  echo "Dossier racine par défaut : $ROOT_DIR"
  read -p "Voulez-vous choisir un autre dossier ? (y/n) [n] : " choice
  [[ "$choice" == "y" ]] && read -p "Indiquez le chemin du dossier : " custom_dir && [[ -n "$custom_dir" ]] && ROOT_DIR="$custom_dir"
  echo "Sous-dossiers disponibles :"

  DIR_LIST=()
  while IFS= read -r line; do DIR_LIST+=("$line"); done < <(find "$ROOT_DIR" -type d 2>/dev/null)
  for i in "${!DIR_LIST[@]}"; do echo "  [$((i+1))] ${DIR_LIST[$i]}"; done
  read -p "Choisissez un dossier [1-${#DIR_LIST[@]}] (défaut: 1) : " dir_choice
  dir_choice=${dir_choice:-1}
  SELECTED_DIR="${DIR_LIST[$((dir_choice-1))]}"
  echo "[OK] Dossier sélectionné : $SELECTED_DIR"

  IMAGE_LIST=()
  while IFS= read -r line; do IMAGE_LIST+=("$line"); done < <(find "$SELECTED_DIR" -maxdepth 1 -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" \) 2>/dev/null)
  if [[ ${#IMAGE_LIST[@]} -eq 0 ]]; then echo "❌ Aucune image trouvée dans $SELECTED_DIR"; exit 1; fi

  echo "Images disponibles :"
  for i in "${!IMAGE_LIST[@]}"; do echo "  [$((i+1))] ${IMAGE_LIST[$i]}"; done
  read -p "Choisissez une image [1-${#IMAGE_LIST[@]}] (défaut: 1) : " img_choice
  img_choice=${img_choice:-1}
  INPUT_IMG="${IMAGE_LIST[$((img_choice-1))]}"
  echo "[OK] Image sélectionnée : $INPUT_IMG"
fi

echo "Debug"

[[ -z "$INPUT_IMG" ]] && { echo "❌ Image non spécifiée."; usage; }
echo "Debug2"

# -------------------------------------------------------
# Préparer sous-dossier image et conversion PNG
# -------------------------------------------------------
IMG_NAME=$(basename "$INPUT_IMG")
IMG_BASE="${IMG_NAME%.*}"
IMG_EXT="${IMG_NAME##*.}"
INPUT_DIR="$BASE_DIR/images_brutes"
INPUT_IMG_SUBDIR="$INPUT_DIR/$IMG_BASE"
IMG_NAME_RAW=$(basename "$INPUT_IMG")
RAW_BASE="${IMG_NAME_RAW%.*}"

#INPUT_IMG_SUBDIR="$BASE_DIR/images_brutes/$RAW_BASE"

echo "Debug3"
echo "DEBUG: INPUT_IMG_SUBDIR='$INPUT_IMG_SUBDIR'"
ensure_dir "$INPUT_IMG_SUBDIR"
echo "Debug4"

src_ext="${IMG_NAME_RAW##*.}"
src_ext_lc=$(echo "$src_ext" | tr '[:upper:]' '[:lower:]')

# Destination du fichier de travail : toujours en PNG
DEST_PNG="$INPUT_IMG_SUBDIR/${RAW_BASE}.png"

# Cas 1 : déjà un PNG
echo "Debug5"

if [[ "$src_ext_lc" == "png" ]]; then
  if [[ "$(cd "$(dirname "$INPUT_IMG")" && pwd)" == "$(cd "$INPUT_IMG_SUBDIR" 2>/dev/null || pwd)" && "$(basename "$INPUT_IMG")" == "${RAW_BASE}.png" ]]; then
    # PNG déjà dans le bon dossier
    INPUT_IMG_PATH="$INPUT_IMG"
  else
    # Copie le PNG (n’écrase pas si déjà existant)
    if [ ! -f "$DEST_PNG" ]; then
      cp -p "$INPUT_IMG" "$DEST_PNG"
    fi
    INPUT_IMG_PATH="$DEST_PNG"
  fi

# Cas 2 : pas un PNG → conversion obligatoire
else
  if [ -f "$DEST_PNG" ]; then
    echo "[INFO] Fichier PNG déjà présent : $DEST_PNG (conversion sautée)"
    INPUT_IMG_PATH="$DEST_PNG"
  else
    echo "[INFO] Conversion en PNG :"
    echo "       source : $INPUT_IMG"
    echo "       dest   : $DEST_PNG"

    # Vérifie la présence de ImageMagick
    if ! command -v magick >/dev/null 2>&1; then
      echo "❌ 'magick' (ImageMagick) introuvable — installation requise pour la conversion."
      exit 1
    fi

    # Conversion avec strip + sRGB
    if ! magick "$INPUT_IMG" -strip -colorspace sRGB "$DEST_PNG"; then
      echo "❌ Erreur : la conversion de $INPUT_IMG vers PNG a échoué."
      echo "    Vérifie que le fichier est lisible et que ImageMagick supporte ce format."
      exit 1
    fi

    # Vérifie que le fichier PNG existe bien
    if [ ! -f "$DEST_PNG" ]; then
      echo "❌ Erreur : fichier PNG non créé ($DEST_PNG)."
      exit 1
    fi

    INPUT_IMG_PATH="$DEST_PNG"
    echo "[OK] Conversion terminée : $INPUT_IMG_PATH"
  fi
fi

#INPUT_IMG_PATH="${DEST_PNG:-$INPUT_IMG}"
echo
echo "INPUT_IMG_PATH = $INPUT_IMG_PATH"
echo


IMG_NAME=$(basename "$INPUT_IMG_PATH")
IMG_BASE="${IMG_NAME%.*}"
IMG_EXT="${IMG_NAME##*.}"

# -------------------------------------------------------
# Création des sous-dossiers pipeline
# -------------------------------------------------------
WATERMARK_VISIBLE_DIR="$BASE_DIR/watermark-filigrane-visible"
WATERMARK_INVISIBLE_DIR="$BASE_DIR/watermark-filigrane-invisible"
SIGNATURES_DIR="$BASE_DIR/watermark-signatures"
NUM_SIGNATURE_DIR="$BASE_DIR/watermark-signature_numérique"

WM_VISIBLE_SUBDIR="$WATERMARK_VISIBLE_DIR/$IMG_BASE"
WM_INVISIBLE_SUBDIR="$WATERMARK_INVISIBLE_DIR/$IMG_BASE"
WM_SIGNATURE_SUBDIR="$SIGNATURES_DIR/$IMG_BASE"
WM_NUM_SIGNATURE_SUBDIR="$NUM_SIGNATURE_DIR/$IMG_BASE"

# Crée les sous-dossiers si nécessaire
ensure_dir "$WM_VISIBLE_SUBDIR"
ensure_dir "$WM_INVISIBLE_SUBDIR"
ensure_dir "$WM_SIGNATURE_SUBDIR"
ensure_dir "$WM_NUM_SIGNATURE_SUBDIR"

FILE_WM_VISIBLE="$WM_VISIBLE_SUBDIR/${IMG_BASE}-watermarked.${IMG_EXT}"
FILE_WM_EXIF="$WM_VISIBLE_SUBDIR/${IMG_BASE}-watermarked_exif.${IMG_EXT}"
FILE_WM_INVISIBLE="$WM_INVISIBLE_SUBDIR/${IMG_BASE}-watermarked_exif-openstego.${IMG_EXT}"
FILE_NUM_SIGNED="$WM_NUM_SIGNATURE_SUBDIR/${IMG_BASE}-watermarked_exif-openstego-num_signed.${IMG_EXT}"
SIG_FILE="$WM_SIGNATURE_SUBDIR/bleu-pastel.sig"

EXIF_DATE=${EXIF_CUSTOM_DATE:-$(date +"%Y:%m:%d %H:%M:%S")}

# =======================================================
# Fonctions pipeline (filigrane, EXIF, stegano, signature, blockchain)
# =======================================================
# -------------------------------------------------------
# run_filigrane_visible_manual (avec watermarkly par exemple)
# -------------------------------------------------------
run_filigrane_visible_manual() {
  ensure_dir "$WM_VISIBLE_SUBDIR"
  echo "=== Filigrane visible (manuel) ==="
  cp "$INPUT_IMG_PATH" "$FILE_WM_VISIBLE"
  read -p "Créer filigrane visible avec Watermarkly sur $FILE_WM_VISIBLE, puis Entrée..."
}

# -------------------------------------------------------
# run_filigrane_visible_auto
# -------------------------------------------------------
run_filigrane_visible_auto() {
  ensure_dir "$WM_VISIBLE_SUBDIR"
  echo "=== Filigrane visible (IMv7 compatible) ==="

  if $MODE_INTERACTIVE; then
    read -p "Texte du watermark [défaut: $WM_TEXT] : " TMP
    WM_TEXT=${TMP:-$WM_TEXT}

    read -p "Taille police (pt) [défaut: $WM_POINTSIZE] : " TMP
    WM_POINTSIZE=${TMP:-$WM_POINTSIZE}

    read -p "Couleur texte R,G,B [défaut: $WM_TEXT_COLOR] : " TMP
    WM_TEXT_COLOR=${TMP:-$WM_TEXT_COLOR}

    read -p "Couleur contour R,G,B [défaut: $WM_STROKE_COLOR] : " TMP
    WM_STROKE_COLOR=${TMP:-$WM_STROKE_COLOR}

    read -p "Épaisseur contour (px) [défaut: $WM_STROKE_WIDTH] : " TMP
    WM_STROKE_WIDTH=${TMP:-$WM_STROKE_WIDTH}

    read -p "Opacité (0-1) [défaut: $WM_OPACITY] : " TMP
    WM_OPACITY=${TMP:-$WM_OPACITY}

    read -p "Angle (°) [défaut: $WM_ANGLE] : " TMP
    WM_ANGLE=${TMP:-$WM_ANGLE}

    read -p "Espacement entre watermarks (px) [défaut: $WM_SPACING] : " TMP
    WM_SPACING=${TMP:-$WM_SPACING}

    read -p "Placement : coins (c) / partout (p) [défaut: partout] : " TMP
    [[ "$TMP" =~ ^[Cc]$ ]] && PLACE_MODE="corners" || PLACE_MODE="all"
  fi

  # Génération du watermark comme avant
  local font_option=()
  [ -n "$WM_FONT" ] && font_option=(-font "$WM_FONT")

  local TMP_TEXT="$WM_VISIBLE_SUBDIR/wm_text.txt"
  local TMP_WM="$WM_VISIBLE_SUBDIR/wm_label.png"
  printf "%s" "$WM_TEXT" > "$TMP_TEXT"

  local angle=$WM_ANGLE
  [[ "$PLACE_MODE" == "corners" ]] && angle=0

  local FILL_COLOR="rgba(${WM_TEXT_COLOR},${WM_OPACITY})"
  local STROKE_COLOR="rgb(${WM_STROKE_COLOR})"

  magick -size ${WM_SPACING}x${WM_SPACING} \
         -background none \
         -fill "$FILL_COLOR" \
         -stroke "$STROKE_COLOR" \
         -strokewidth $WM_STROKE_WIDTH \
         -pointsize $WM_POINTSIZE \
         -gravity center \
         label:"$WM_TEXT" \
         -rotate $angle \
         "${font_option[@]}" \
         "$TMP_WM"

  # 2. On l'applique sur l'image source
  if [[ "$PLACE_MODE" == "all" ]]; then
    # Version corrigée pour éviter le bug de dimension vide
    local IMG_DIM=$(identify -format "%wx%h" "$INPUT_IMG_PATH")
    magick "$INPUT_IMG_PATH" \
           -size "$IMG_DIM" tile:"$TMP_WM" \
           -compose over -composite "$FILE_WM_VISIBLE"
  else
    magick "$INPUT_IMG_PATH" \
           \( "$TMP_WM" -geometry +10+10 \) -gravity northwest -composite \
           \( "$TMP_WM" -geometry +10+10 \) -gravity northeast -composite \
           \( "$TMP_WM" -geometry +10+10 \) -gravity southwest -composite \
           \( "$TMP_WM" -geometry +10+10 \) -gravity southeast -composite \
           "$FILE_WM_VISIBLE"
  fi

  rm -f "$TMP_TEXT" "$TMP_WM"
  echo "[OK] Filigrane appliqué sur $FILE_WM_VISIBLE"
}

# -------------------------------------------------------
# run_exif
# -------------------------------------------------------
run_exif() {
  ensure_dir "$WM_VISIBLE_SUBDIR"
  echo "=== Ajout des métadonnées EXIF ==="
  [ ! -f "$FILE_WM_VISIBLE" ] && echo "[WARN] Filigrane visible introuvable, saut EXIF" && return

  if $MODE_INTERACTIVE; then
    read -p "Date/heure EXIF (YYYY:mm:dd HH:MM:SS) [défaut: $(date +"%Y:%m:%d %H:%M:%S")] : " TMP
    EXIF_DATE=${TMP:-$(date +"%Y:%m:%d %H:%M:%S")}
  else
    EXIF_DATE=${EXIF_CUSTOM_DATE:-$(date +"%Y:%m:%d %H:%M:%S")}
  fi

  cp "$FILE_WM_VISIBLE" "$FILE_WM_EXIF"
  exiftool -overwrite_original \
    -DateTimeOriginal="$EXIF_DATE" \
    -CreateDate="$EXIF_DATE" \
    -ImageUniqueID="${EXIF_DATE}:001" \
    -Creator="© Cert-Art.fr" \
    -Artist="© Cert-Art.fr" \
    -Copyright="© Cert-Art.fr" \
    "$FILE_WM_EXIF"
}


# -------------------------------------------------------
# run_stegano : filigrane invisible avec mot de passe optionnel - 30-09 - 01:59
# -------------------------------------------------------
run_stegano() {
  ensure_dir "$WM_INVISIBLE_SUBDIR"
  ensure_dir "$WM_SIGNATURE_SUBDIR"

  echo "=== Filigrane invisible (stéganographie) ==="
  [ ! -f "$FILE_WM_EXIF" ] && echo "[WARN] EXIF introuvable, saut stéganographie" && return

  if $MODE_INTERACTIVE; then
    read -p "Message à cacher [défaut: $MESSAGE] : " TMP
    MESSAGE=${TMP:-$MESSAGE}

    read -p "Voulez-vous saisir un mot de passe pour le filigrane invisible ? (y/n) [n] : " TMP
    if [[ "$TMP" =~ ^[Yy]$ ]]; then
      read -s -p "Mot de passe : " PASSWORD
      echo
    else
      PASSWORD="$MESSAGE"  # mot de passe par défaut = message
    fi
  else
    PASSWORD="$MESSAGE"  # mot de passe par défaut
  fi

  MSG_FILE="$WM_SIGNATURE_SUBDIR/signature.txt"
  PW_FILE="$WM_SIGNATURE_SUBDIR/pw.txt"
  printf "%s" "$MESSAGE" > "$MSG_FILE"
  printf "%s" "$PASSWORD" > "$PW_FILE"
  echo "[DEBUG] Mot de passe utilisé : $PASSWORD"
  echo "[INFO] Fichier message créé dans : $MSG_FILE"
  echo "[DEBUG] Mot de passe sauvegardé dans : $PW_FILE"

  java -jar "$OPENSTEGO_JAR" embed -mf "$MSG_FILE" -cf "$FILE_WM_EXIF" -sf "$FILE_WM_INVISIBLE" -p "$PASSWORD"
  echo "[OK] Filigrane invisible appliqué : $FILE_WM_INVISIBLE"
}

# -------------------------------------------------------
# run_signature
# -------------------------------------------------------
run_signature() {
    ensure_dir "$WM_NUM_SIGNATURE_SUBDIR"
    ensure_dir "$WM_SIGNATURE_SUBDIR"
    echo "=== Signature numérique ==="

    [ ! -f "$FILE_WM_INVISIBLE" ] && echo "[WARN] Filigrane invisible introuvable, saut signature" && return

    SIG_FILE="$WM_SIGNATURE_SUBDIR/bleu-pastel.sig"
    ensure_dir "$(dirname "$SIG_FILE")"

    if [ ! -f "$SIG_FILE" ]; then
        # Mot de passe généré automatiquement
        SIG_PWD="${IMG_BASE}_$(date +%Y%m%d%H%M%S)"
        echo "[INFO] Mot de passe généré automatiquement : $SIG_PWD"

        # Mode interactif : possibilité de saisir un mot de passe
        if $MODE_INTERACTIVE; then
            read -p "Voulez-vous saisir un mot de passe personnalisé ? (y/n) [n] : " WANT_PWD
            WANT_PWD=${WANT_PWD:-n}
            if [[ "$WANT_PWD" =~ ^[Yy]$ ]]; then
                read -s -p "Entrer mot de passe : " SIG_PWD; echo
                read -s -p "Confirmer mot de passe : " SIG_PWD2; echo
                [[ "$SIG_PWD" != "$SIG_PWD2" ]] && { echo "[ERROR] Les mots de passe ne correspondent pas"; return 1; }
            fi
        fi

        # Génération de la signature via stdin pour éviter blocage
        printf "%s\n%s\n" "$SIG_PWD" "$SIG_PWD" | java -jar "$OPENSTEGO_JAR" gensig -gf "$SIG_FILE"
        [ ! -f "$SIG_FILE" ] && { echo "[ERROR] La signature n'a pas été créée : $SIG_FILE"; return 1; }
        echo "[OK] Fichier de signature créé : $SIG_FILE"
    else
        echo "[INFO] Fichier de signature déjà présent : $SIG_FILE"
    fi

    # Appliquer le tatouage sur le fichier invisible
    java -jar "$OPENSTEGO_JAR" embedmark -gf "$SIG_FILE" -cf "$FILE_WM_INVISIBLE" -sf "$FILE_NUM_SIGNED"
    echo "[OK] Signature appliquée sur $FILE_NUM_SIGNED"
}

# -------------------------------------------------------
# run_blockchain
# -------------------------------------------------------
run_blockchain() {
  echo "=== Enregistrement sur la blockchain ==="
  [ ! -f "$FILE_NUM_SIGNED" ] && echo "[WARN] Fichier signé introuvable, saut blockchain" && return
  $OTS_BIN stamp "$FILE_NUM_SIGNED"
  echo "[OK] Blockchain : $FILE_NUM_SIGNED"
}

# =======================================================
# Fonctions vérification
# =======================================================

# -------------------------------------------------------
# check_stegano : extraction avec mot de passe exact utilisé - 30-09 - 01:59
# -------------------------------------------------------
check_stegano() {
  echo "=== Vérification du filigrane invisible ==="
  [ ! -f "$FILE_WM_INVISIBLE" ] && echo "[INFO] Filigrane invisible : aucune info" && return

  PW_FILE="$WM_SIGNATURE_SUBDIR/pw.txt"
  if [ ! -f "$PW_FILE" ]; then
    echo "[WARN] Mot de passe introuvable ($PW_FILE), impossible de vérifier"
    return 1
  fi

  PASSWORD=$(cat "$PW_FILE")
  MSG_FILE="$WM_SIGNATURE_SUBDIR/signature.txt"
  echo "[INFO] Extraction avec -p \"$PASSWORD\" ..."
  java -jar "$OPENSTEGO_JAR" extract -sf "$FILE_WM_INVISIBLE" -p "$PASSWORD"
  echo "[OK] Message extrait : $(cat "$MSG_FILE")"
}

# -------------------------------------------------------
# check_signature
# -------------------------------------------------------
check_signature() {
  echo "=== Vérification de la signature numérique ==="
  [ -f "$FILE_NUM_SIGNED" ] && java -jar "$OPENSTEGO_JAR" checkmark -gf "$SIG_FILE" -sf "$FILE_NUM_SIGNED" || echo "[INFO] Tatouage numérique : aucune info"
}

# -------------------------------------------------------------
# check_blockchain (vérification + upgrade automatique) - v1.4
# -------------------------------------------------------
check_blockchain() {
  local OTS_FILE="$1"
  local BASE_CMD="ots"

  echo "=== Vérification sur la blockchain (mode distant) ==="

  # Si aucun fichier fourni en argument, on prend celui par défaut
  if [[ -z "$OTS_FILE" ]]; then
    OTS_FILE="$FILE_NUM_SIGNED.ots"
  fi

  # Vérifie que le fichier existe
  if [[ ! -f "$OTS_FILE" ]]; then
    echo "[ERREUR] Fichier .ots introuvable : $OTS_FILE"
    echo "         Vérifiez le chemin ou générez d'abord le timestamp avec :"
    echo "         ots stamp \"$FILE_NUM_SIGNED\""
    return 1
  fi

  echo "[OPTIONS Vérif Blockchain]"
  echo "  Fichier OTS : $OTS_FILE"
  echo "  Commande : $BASE_CMD"
  echo
  echo "[INFO] Vérification du timestamp distant pour :"
  echo "       $OTS_FILE"
  echo

  # --- Vérification initiale ---
  echo "[INFO] Vérification initiale..."
  local VERIFY_OUT
  VERIFY_OUT=$($BASE_CMD verify "$OTS_FILE" 2>&1 || true)

  if echo "$VERIFY_OUT" | grep -q "Timestamped by transaction"; then
    echo "$VERIFY_OUT"
    echo "[OK] Timestamp complètement confirmé sur la blockchain."
    return 0
  fi

  if echo "$VERIFY_OUT" | grep -q "PendingAttestation"; then
    echo "[WARN] Vérification initiale non confirmée."
    echo "[INFO] Détails :"
    echo "$VERIFY_OUT" | sed -n '1,200p'
  else
    echo "[WARN] Vérification initiale non confirmée."
    echo "[INFO] Détails :"
    echo "$VERIFY_OUT" | sed -n '1,200p'
  fi

  # --- Proposition de mise à jour (upgrade) ---
  echo
  if $MODE_INTERACTIVE; then
    read -p "Souhaitez-vous mettre à jour la preuve OTS maintenant ? (y/n) [y] : " choice
    choice=${choice:-y}
  else
    choice="y"
  fi

  if [[ "$choice" =~ ^[Yy]$ ]]; then
    echo "[INFO] Tentative de mise à jour de la preuve (upgrade)..."
    if $BASE_CMD upgrade "$OTS_FILE" >/tmp/ots_upgrade.log 2>&1; then
      echo "[OK] Mise à jour effectuée avec succès."
    else
      echo "[ERREUR] Échec de la mise à jour du fichier .ots"
      echo "         Consultez /tmp/ots_upgrade.log pour le détail."
      return 1
    fi
  else
    echo "[INFO] Mise à jour ignorée à la demande de l'utilisateur."
  fi

  # --- Vérification après mise à jour ---
  echo
  echo "[INFO] Vérification après mise à jour..."
  local VERIFY_AFTER
  VERIFY_AFTER=$($BASE_CMD verify "$OTS_FILE" 2>&1 \
    | grep -v "Could not connect to Bitcoin node" \
    | grep -v "Cookie file unusable" \
    | grep -v "rpcpassword" \
    || true)

  echo "$VERIFY_AFTER"

  if echo "$VERIFY_AFTER" | grep -q "Timestamped by transaction"; then
    echo "[OK] Timestamp complètement confirmé sur la blockchain."
  elif echo "$VERIFY_AFTER" | grep -q "PendingAttestation"; then
    echo "[WARN] Timestamp encore en attente de confirmation sur un ou plusieurs serveurs calendrier."
    echo "[INFO] Réessayez plus tard avec :"
    echo "       ots upgrade \"$OTS_FILE\""
    echo "       ots verify \"$OTS_FILE\""
  elif echo "$VERIFY_AFTER" | grep -q "Assuming target filename"; then
    echo "[INFO] Le fichier est reconnu par ots mais aucune attestation n’est encore disponible."
    echo "[INFO] Cela signifie probablement que la preuve a été créée récemment et n’a pas encore été propagée."
    echo "[INFO] Réessayez dans quelques heures avec :"
    echo "       ots upgrade \"$OTS_FILE\""
  else
    echo "[WARN] Impossible de déterminer le statut exact."
    echo "[INFO] Consultez le contenu brut avec :"
    echo "       ots info \"$OTS_FILE\""
  fi

  echo
  return 0
}
# -------------------------------------------------------
# show_exif
# -------------------------------------------------------
show_exif() {
  echo "=== Affichage des métadonnées EXIF ==="
  [ -f "$FILE_WM_EXIF" ] && exiftool "$FILE_WM_EXIF" || echo "[INFO] EXIF : aucune info"
}

# -------------------------------------------------------
# report_final
# -------------------------------------------------------
report_final() {
  echo "=== Rapport final (mode auto) ==="
  check_stegano
  check_signature
  check_blockchain
  show_exif
}

# =======================================================
# Exécution via dispatcher API CLI
# =======================================================
check_dependencies

ensure_dir "$WATERMARK_VISIBLE_DIR"
ensure_dir "$WATERMARK_INVISIBLE_DIR"
ensure_dir "$SIGNATURES_DIR"
ensure_dir "$NUM_SIGNATURE_DIR"

write_state() {
  local file="$1"
  if [[ -n "$file" && -f "$file" ]]; then
    echo "$file" > "$STATE_FILE"
    echo "[STATE] Dernière image : $file"
  fi
}

run_action() {
  case "$ACTION" in
    visible)
      echo "[ACTION] Watermark visible"
      case $WM_MODE in
        skip) echo "[INFO] Étape filigrane visible sautée" ;;
        manual) run_filigrane_visible_manual ;;
        auto) run_filigrane_visible_auto ;;
        *) echo "[ERROR] WM_MODE inconnu : $WM_MODE"; exit 1 ;;
      esac
      write_state "$FILE_WM_VISIBLE"
      ;;

    exif)
      echo "[ACTION] EXIF"
      run_exif
      write_state "$FILE_WM_EXIF"
      ;;

    stegano)
      echo "[ACTION] Stéganographie"
      run_stegano
      write_state "$FILE_WM_INVISIBLE"
      ;;

    signature)
      echo "[ACTION] Signature numérique"
      run_signature
      write_state "$FILE_NUM_SIGNED"
      ;;

    blockchain)
      echo "[ACTION] Blockchain"
      run_blockchain
      write_state "$FILE_NUM_SIGNED"
      ;;

    check_stegano)
      echo "[ACTION] Vérification stéganographie"
      check_stegano
      ;;

    check_signature)
      echo "[ACTION] Vérification signature"
      check_signature
      ;;

    check_blockchain)
      echo "[ACTION] Vérification blockchain"
      check_blockchain
      ;;

    show_exif)
      echo "[ACTION] Affichage EXIF"
      show_exif
      ;;

    report)
      echo "[ACTION] Rapport final"
      report_final
      ;;

    pipeline)
      echo "[ACTION] Pipeline complet pour $INPUT_IMG"
      case $WM_MODE in
        skip) echo "[INFO] Étape filigrane visible sautée" ;;
        manual) run_filigrane_visible_manual ;;
        auto) run_filigrane_visible_auto ;;
        *) echo "[ERROR] WM_MODE inconnu : $WM_MODE"; exit 1 ;;
      esac
      write_state "$FILE_WM_VISIBLE"

      run_exif
      write_state "$FILE_WM_EXIF"

      run_stegano
      write_state "$FILE_WM_INVISIBLE"

      run_signature
      write_state "$FILE_NUM_SIGNED"

      run_blockchain
      write_state "$FILE_NUM_SIGNED"
      ;;

    *)
      echo "Action inconnue : $ACTION"
      echo "Actions disponibles : visible, exif, stegano, signature, blockchain, check_stegano, check_signature, check_blockchain, show_exif, report, pipeline"
      exit 1
      ;;
  esac
}

if $MODE_INTERACTIVE; then
  echo "=== Mode interactif ==="
  echo "[INFO] Le mode interactif garde le comportement guidé."
  read -p "Voulez-vous appliquer le filigrane visible ? (y/n) [n] : " choice
  [[ "$choice" == "y" ]] && { run_filigrane_visible_auto; write_state "$FILE_WM_VISIBLE"; }

  read -p "Voulez-vous ajouter les métadonnées EXIF ? (y/n) [n] : " choice
  [[ "$choice" == "y" ]] && { run_exif; write_state "$FILE_WM_EXIF"; }

  read -p "Voulez-vous appliquer le filigrane invisible (stéganographie) ? (y/n) [n] : " choice
  [[ "$choice" == "y" ]] && { run_stegano; write_state "$FILE_WM_INVISIBLE"; }

  read -p "Voulez-vous signer numériquement l'image ? (y/n) [n] : " choice
  [[ "$choice" == "y" ]] && { run_signature; write_state "$FILE_NUM_SIGNED"; }

  read -p "Voulez-vous enregistrer sur la blockchain ? (y/n) [n] : " choice
  [[ "$choice" == "y" ]] && { run_blockchain; write_state "$FILE_NUM_SIGNED"; }

  echo "=== Vérifications interactives ==="

  read -p "Voulez-vous afficher les métadonnées EXIF ? (y/n) [n] : " choice
  [[ "$choice" == "y" ]] && { echo "[OPTIONS Vérif EXIF]"; echo "  Fichier : $FILE_WM_EXIF"; show_exif; }

  read -p "Voulez-vous vérifier le filigrane invisible ? (y/n) [n] : " choice
  [[ "$choice" == "y" ]] && { echo "[OPTIONS Vérif Stéganographie]"; echo "  Fichier : $FILE_WM_INVISIBLE"; echo "  Message attendu : $MESSAGE"; check_stegano; }

  read -p "Voulez-vous vérifier la signature numérique ? (y/n) [n] : " choice
  [[ "$choice" == "y" ]] && { echo "[OPTIONS Vérif Signature]"; echo "  Fichier : $FILE_NUM_SIGNED"; echo "  Signature attendue : $SIG_FILE"; check_signature; }

  read -p "Voulez-vous vérifier l'enregistrement sur la blockchain ? (y/n) [n] : " choice
  [[ "$choice" == "y" ]] && { echo "[OPTIONS Vérif Blockchain]"; echo "  Fichier OTS : ${FILE_NUM_SIGNED}.ots"; echo "  Commande : $OTS_BIN"; check_blockchain; }
else
  run_action
fi