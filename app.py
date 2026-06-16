from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
import importlib
import io
import sys
from pathlib import Path

app = Flask(__name__)
# sécurité CORS pour pouvoir parler au naviguateur 
CORS(app)

UPLOAD_FOLDER = 'uploads/'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# nom du dossier python avec les fonctions à exécuter 
PACKAGE_NAME = "certifier_image"

@app.route('/api', methods=['POST'])
def handle_api():
    try:
        # récupération de l'image brute et de l'action
        action = request.form.get('action', 'pipeline')
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "Aucun fichier fourni."}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({"status": "error", "message": "Nom de fichier vide."}), 400

        input_img_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(input_img_path)

        # récupération des paramètres de l'interface JS
        wm_text = request.form.get('wm_text', '© Cert-Art.fr')
        wm_size = request.form.get('wm_size', '35')
        wm_color = request.form.get('wm_color', '128,128,128')
        wm_opacity = request.form.get('wm_opacity', '0.2')
        wm_angle = request.form.get('wm_angle', '-45')
        wm_spacing = request.form.get('wm_spacing', '300')
        stegano_message = request.form.get('stegano_message', 'defaut')

        # préparation de la liste d'arguments requise par cli.py
        argv = [
            "--no-interactive",
            "--wm-text", str(wm_text),
            "--wm-size", str(wm_size),
            "--wm-opacity", str(wm_opacity),
            "--wm-color", str(wm_color),
            "--wm-angle", str(wm_angle),
            "--wm-spacing", str(wm_spacing),
            "--stegano-message", str(stegano_message),
            action,
            input_img_path
        ]

        print(f"📡 Transmission des paramètres au moteur : {argv}")

        # appelle du module cli.py dynamiquement
        cli_module = importlib.import_module("certifier_image.cli")
        
        # on capture les print() pour qu'ils s'affichent à l'écran 
        old_stdout = sys.stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # lancement du main avec les arguments récupérés de l'IHM 
        return_code = cli_module.main(argv)
        
        # on restaure le terminal normal et on récupère les logs
        sys.stdout = old_stdout
        terminal_logs = captured_output.getvalue().splitlines()

        if return_code != 0:
            return jsonify({
                "status": "error",
                "message": "Le traitement des filigranes a échoué.",
                "terminal_output": terminal_logs
            }), 500

        # localisation de l'image créée par le python 
        img_base = Path(file.filename).stem
        possible_outputs = [
            Path(f"watermark-signature_numérique/{img_base}/{img_base}-watermarked_exif-openstego-num_signed.png"),
            Path(f"watermark-filigrane-invisible/{img_base}/{img_base}-watermarked_exif-openstego.png"),
            Path(f"watermark-filigrane-visible/{img_base}/{img_base}-watermarked_exif.png"),
            Path(f"watermark-filigrane-visible/{img_base}/{img_base}-watermarked.png"),
            Path(f"images_brutes/{img_base}/{img_base}.png")
        ]

        final_image_path = None
        for path in possible_outputs:
            if path.is_file():
                final_image_path = path
                break

        # encodage en Base64 de la nouvelle image
        base64_image = None
        if final_image_path and final_image_path.is_file():
            with open(final_image_path, "rb") as img_file:
                encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
            base64_image = f"data:image/png;base64,{encoded_string}"
            
            # on supprime l'image générée pour forcer le renouvellement au prochain test
            os.remove(final_image_path)

        return jsonify({
            "status": "success",
            "action_executed": action,
            "image_base64": base64_image,
            "terminal_output": terminal_logs
        })

    except Exception as e:
        # en cas de crash, on remet le terminal en état
        if 'old_stdout' in locals():
            sys.stdout = old_stdout
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    print(f" Serveur Flask connecté aux scripts Python sur http://localhost:8000")
    app.run(port=8000, debug=True)