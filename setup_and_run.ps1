# =========================================================
# Script de setup et lancement du projet
# =========================================================

# Autoriser l'execution de scripts pour ce processus uniquement
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Creer l'environnement virtuel seulement s'il n'existe pas deja
if (-Not (Test-Path ".\.venv")) {
    Write-Host "[INFO] Creation de l'environnement virtuel..." -ForegroundColor Cyan
    py -m venv .venv
} else {
    Write-Host "[INFO] Environnement virtuel deja present, etape ignoree." -ForegroundColor Yellow
}

# Activer l'environnement virtuel
Write-Host "[INFO] Activation de l'environnement virtuel..." -ForegroundColor Cyan
.\.venv\Scripts\Activate.ps1

# Verifier que l'activation a reussi (le prompt VIRTUAL_ENV doit etre defini)
if (-Not $env:VIRTUAL_ENV) {
    Write-Host "[ERREUR] L'environnement virtuel n'a pas pu etre active." -ForegroundColor Red
    exit 1
}

# Installer les dependances
Write-Host "[INFO] Installation des dependances..." -ForegroundColor Cyan
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERREUR] Echec de l'installation des dependances." -ForegroundColor Red
    exit 1
}

# Initialiser la base de donnees
Write-Host "[INFO] Initialisation de la base de donnees..." -ForegroundColor Cyan
py DB\init_DB.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERREUR] Echec de l'initialisation de la base de donnees." -ForegroundColor Red
    exit 1
}

# Lancer l'application
Write-Host "[INFO] Lancement de l'application..." -ForegroundColor Cyan
py app.py
