@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TikTok Money Printer - lien fixe

echo ============================================================
echo   TikTok Money Printer - demarrage avec lien FIXE
echo ============================================================
echo.

if exist ".git" call :update

where python >nul 2>nul
if errorlevel 1 goto no_python

where tailscale >nul 2>nul
if errorlevel 1 goto no_tailscale

if not exist .venv call :make_venv
call .venv\Scripts\activate

echo Installation / mise a jour des dependances...
echo Patiente, la premiere fois cela prend 3 a 5 minutes...
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q -U --pre "yt-dlp[default]"

if not exist .env goto make_env

echo.
echo Demarrage de l'application...
start "TMP-serveur" /min cmd /c ".venv\Scripts\python run.py"
timeout /t 5 >nul

echo Ouverture du lien fixe via Tailscale Funnel...
tailscale funnel --bg 5000

echo.
echo ============================================================
echo   TON LIEN FIXE, le meme a chaque fois :
echo ------------------------------------------------------------
tailscale funnel status
echo ============================================================
echo.
echo   Ouvre ce lien https://....ts.net depuis n'importe quel navigateur.
echo   Laisse ce PC allume et cette fenetre ouverte quand tu bosses.
echo.
pause >nul
goto end

:update
where git >nul 2>nul
if errorlevel 1 goto :eof
echo Mise a jour de l'application vers la derniere version...
git pull --ff-only
echo.
goto :eof

:make_venv
echo Creation de l'environnement Python, premiere fois...
python -m venv .venv
goto :eof

:no_python
echo [ERREUR] Python n'est pas installe, ou pas ajoute au PATH.
echo Reinstalle Python depuis https://www.python.org/downloads/
echo et coche bien la case "Add Python to PATH".
echo.
pause >nul
goto end

:no_tailscale
echo [ERREUR] Tailscale n'est pas installe.
echo 1. Installe-le depuis https://tailscale.com/download/windows
echo 2. Connecte-toi via l'icone Tailscale dans la barre des taches
echo 3. Active Funnel, voir le README section "lien fixe"
echo 4. Relance ce fichier.
echo.
pause >nul
goto end

:make_env
copy .env.example .env >nul
echo.
echo ============================================================
echo   PREMIERE UTILISATION - configure ta cle et ton mot de passe
echo ------------------------------------------------------------
echo   1. Ouvre le fichier .env avec le Bloc-notes
echo   2. Ligne ANTHROPIC_API_KEY=  colle ta cle sk-ant-...
echo   3. Ligne APP_PASSWORD=  choisis un mot de passe
echo   4. Enregistre, ferme, puis relance ce fichier
echo ============================================================
echo.
pause >nul
goto end

:end
