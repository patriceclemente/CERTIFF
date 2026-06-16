#!/bin/bash
# -----------------------------------------------
# Script de lancement automatique du serveur PHP 
# -----------------------------------------------

echo "🚀 Démarrage de l'API Cert.tif..."
echo "⚙️  Configuration : upload_max_filesize = 50M"

# Lancement du serveur avec les flags de taille intégrés
php -d upload_max_filesize=50M -d post_max_size=50M -S 0.0.0.0:8000