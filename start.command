#!/bin/bash
# Lanceur macOS / Linux — double-clic (macOS) ou ./start.command
cd "$(dirname "$0")" || exit 1
echo "============================================================"
echo "  TikTok Money Printer - démarrage"
echo "============================================================"

command -v python3 >/dev/null 2>&1 || { echo "[ERREUR] Python 3 manquant : https://www.python.org/downloads/"; read -r; exit 1; }

[ -d .venv ] || { echo "Création de l'environnement Python (une seule fois)..."; python3 -m venv .venv; }
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installation / mise à jour des dépendances..."
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q -U --pre "yt-dlp[default]"

if [ ! -f cloudflared ]; then
  echo "Téléchargement de l'outil de tunnel (une seule fois)..."
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  ARCH=$(uname -m | sed -e 's/x86_64/amd64/' -e 's/aarch64/arm64/' -e 's/arm64/arm64/')
  curl -L -s -o cloudflared "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-${OS}-${ARCH}"
  chmod +x cloudflared
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo
  echo "============================================================"
  echo "  PREMIÈRE UTILISATION : ouvre le fichier .env, mets ta clé"
  echo "  ANTHROPIC_API_KEY et un APP_PASSWORD, enregistre, relance."
  echo "============================================================"
  read -r
  exit 0
fi

echo "Démarrage de l'application..."
.venv/bin/python run.py &
APP_PID=$!
trap 'kill $APP_PID 2>/dev/null' EXIT
sleep 5

echo
echo "============================================================"
echo "  TON LIEN VA S'AFFICHER CI-DESSOUS (https://...trycloudflare.com)"
echo "  Ouvre-le sur ton téléphone. Laisse ce terminal ouvert."
echo "============================================================"
echo
./cloudflared tunnel --url http://localhost:5000 --no-autoupdate
