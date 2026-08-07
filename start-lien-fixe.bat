@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TikTok Money Printer - lien fixe

echo ============================================================
echo   TikTok Money Printer - demarrage avec lien FIXE
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERREUR] Python n'est pas installe.
  echo Installe-le depuis https://www.python.org/downloads/ (coche "Add Python to PATH").
  pause
  exit /b 1
)

where tailscale >nul 2>nul
if errorlevel 1 (
  echo [ERREUR] Tailscale n'est pas installe.
  echo 1. Installe-le depuis https://tailscale.com/download/windows
  echo 2. Connecte-toi (icone Tailscale dans la barre des taches)
  echo 3. Active Funnel : voir le README, section "lien fixe"
  echo 4. Relance ce fichier.
  pause
  exit /b 1
)

if not exist .venv ( echo Creation de l'environnement Python... & python -m venv .venv )
call .venv\Scripts\activate
echo Installation / mise a jour des dependances...
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q -U --pre "yt-dlp[default]"

if not exist .env (
  copy .env.example .env >nul
  echo.
  echo PREMIERE UTILISATION : ouvre .env, mets ANTHROPIC_API_KEY et APP_PASSWORD,
  echo enregistre, puis relance ce fichier.
  pause
  exit /b 0
)

echo Demarrage de l'application...
start "TMP-serveur" /min cmd /c ".venv\Scripts\python run.py"
timeout /t 5 >nul

echo Ouverture du lien fixe (Tailscale Funnel)...
tailscale funnel --bg 5000

echo.
echo ============================================================
echo   TON LIEN FIXE (le meme a chaque fois) :
echo ------------------------------------------------------------
tailscale funnel status
echo ============================================================
echo.
echo   Ouvre ce lien https://....ts.net depuis n'importe quel navigateur
echo   (PC du travail, telephone...). Laisse ce PC allume et cette fenetre ouverte.
echo.
echo   Pour arreter : ferme cette fenetre, puis (optionnel) tape :
echo      tailscale funnel --https=443 off
echo.
pause
