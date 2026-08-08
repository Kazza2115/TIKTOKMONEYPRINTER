@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TikTok Money Printer

echo ============================================================
echo   TikTok Money Printer - demarrage
echo ============================================================
echo.

if exist ".git" call :update

where python >nul 2>nul
if errorlevel 1 goto no_python

if not exist .venv call :make_venv
call .venv\Scripts\activate

echo Installation / mise a jour des dependances...
echo Patiente, la premiere fois cela prend 3 a 5 minutes...
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q -U --pre "yt-dlp[default]"

if not exist cloudflared.exe call :get_cloudflared
if not exist .env goto make_env

echo.
echo Demarrage de l'application...
start "TMP-serveur" /min cmd /c ".venv\Scripts\python run.py"
timeout /t 5 >nul

echo.
echo ============================================================
echo   TON LIEN VA S'AFFICHER CI-DESSOUS
echo   Cherche la ligne https://xxxxx.trycloudflare.com
echo   Ouvre-la sur ton telephone. Laisse cette fenetre ouverte.
echo ============================================================
echo.
cloudflared.exe tunnel --url http://localhost:5000 --no-autoupdate
echo.
echo Le tunnel s'est arrete. Appuie sur une touche pour fermer.
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

:get_cloudflared
echo Telechargement de l'outil de tunnel, premiere fois...
curl -L -s -o cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
goto :eof

:no_python
echo [ERREUR] Python n'est pas installe, ou pas ajoute au PATH.
echo Reinstalle Python depuis https://www.python.org/downloads/
echo et coche bien la case "Add Python to PATH" au debut de l'installation.
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
echo   4. Enregistre, ferme, puis relance start.bat
echo ============================================================
echo.
echo Appuie sur une touche pour fermer.
pause >nul
goto end

:end
