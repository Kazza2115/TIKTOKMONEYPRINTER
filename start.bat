@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TikTok Money Printer

echo ============================================================
echo   TikTok Money Printer - demarrage
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERREUR] Python n'est pas installe.
  echo Installe-le depuis https://www.python.org/downloads/
  echo    -^> coche bien "Add Python to PATH" pendant l'installation.
  pause
  exit /b 1
)

if not exist .venv (
  echo Creation de l'environnement Python (une seule fois)...
  python -m venv .venv
)
call .venv\Scripts\activate

echo Installation / mise a jour des dependances...
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q -U --pre "yt-dlp[default]"

if not exist cloudflared.exe (
  echo Telechargement de l'outil de tunnel (une seule fois)...
  curl -L -s -o cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
)

if not exist .env (
  copy .env.example .env >nul
  echo.
  echo ============================================================
  echo   PREMIERE UTILISATION : configure ta cle et ton mot de passe
  echo ------------------------------------------------------------
  echo   1. Ouvre le fichier .env (dans ce dossier) avec le Bloc-notes
  echo   2. Mets ta cle sur la ligne ANTHROPIC_API_KEY=sk-ant-...
  echo   3. Choisis un mot de passe sur la ligne APP_PASSWORD=...
  echo   4. Enregistre, ferme, et relance ce fichier start.bat
  echo ============================================================
  pause
  exit /b 0
)

echo Demarrage de l'application...
start "TMP-serveur" /min cmd /c ".venv\Scripts\python run.py"

echo Ouverture du tunnel public...
echo.
echo ============================================================
echo   TON LIEN VA S'AFFICHER CI-DESSOUS (https://...trycloudflare.com)
echo   Ouvre-le sur ton telephone. Laisse cette fenetre ouverte.
echo ============================================================
echo.
timeout /t 5 >nul
cloudflared.exe tunnel --url http://localhost:5000 --no-autoupdate
