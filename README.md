---
title: TikTok Money Printer
emoji: 🎬
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# 🎬 TikTok Money Printer

Transforme n'importe quelle vidéo longue (YouTube, Twitch, Vimeo…) en clips TikTok prêts à poster :

- 🤖 **Analyse IA (Claude)** — repère les moments à fort potentiel viral en suivant les codes actuels : hook dans les 3 premières secondes, curiosity gap, émotion, rétention, payoff.
- 🆓 **Mode automatique gratuit (sans API)** — sélection heuristique locale des moments forts (mots d'accroche, questions, énergie), avec découpage en parties et cliffhanger. Aucune clé, aucun compte, aucun coût. Moins fin que l'IA mais suffisant pour démarrer.
- 🧩 **Parties 1/2/3 automatiques** — quand un moment fort est trop long, l'IA le découpe en série avec **cliffhanger** à la fin de chaque partie (coupe en pleine tension, juste avant la révélation).
- 🎙️ **Sous-titres karaoké** — transcription locale (faster-whisper), mots incrustés en gros, mot actif surligné en jaune, style TikTok.
- 📐 **Format 9:16** — recadrage centré + 1080×1920, hook incrusté en haut, badge « PARTIE X/N ».
- ✍️ **Légendes générées** — description + hashtags prêts à copier, score viral estimé pour chaque clip.
- ✂️ **Mode manuel** — tu peux aussi donner tes propres timestamps si tu veux zapper l'IA.

## Prérequis

- **Python 3.10+**
- **ffmpeg** dans le PATH
  - Windows : `winget install ffmpeg` ou `scoop install ffmpeg`
  - Debian/Ubuntu : `sudo apt install ffmpeg`
  - macOS : `brew install ffmpeg`
- Une **clé API Anthropic** (pour le mode IA) : https://platform.claude.com/

## Installation

```bash
git clone https://github.com/Kazza2115/TIKTOKMONEYPRINTER.git
cd TIKTOKMONEYPRINTER

python -m venv .venv
# Windows :
.venv\Scripts\activate
# Linux/macOS :
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env   # puis renseigne ANTHROPIC_API_KEY dans .env
```

## Lancement

```bash
python run.py
```

Ouvre http://127.0.0.1:5000 — colle une URL, choisis le mode, et laisse tourner.

Le pipeline : **téléchargement → transcription → analyse IA → montage**. La première transcription télécharge le modèle Whisper (quelques centaines de Mo), c'est normal.

## Mode manuel

Une ligne par clip, format :

```
1:23-1:55 | HOOK OPTIONNEL EN HAUT DU CLIP | légende optionnelle #hashtag
0:10-0:42
```

Les sous-titres karaoké sont générés dans tous les cas (la transcription tourne aussi en mode manuel).

## Configuration (`.env`)

| Variable | Défaut | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Clé API pour l'analyse IA |
| `CLAUDE_MODEL` | `claude-opus-5` | Modèle utilisé pour l'analyse |
| `WHISPER_MODEL` | `small` | `tiny`/`base`/`small`/`medium`/`large-v3` — plus gros = plus précis mais plus lent |
| `WHISPER_DEVICE` | `auto` | `cpu` ou `cuda` (GPU NVIDIA, beaucoup plus rapide) |
| `MAX_CLIPS` | `5` | Nombre max de clips proposés par vidéo |
| `DATA_DIR` | `./data` | Dossier des téléchargements et clips générés |

## ⚡ Tester tout de suite (Google Colab, gratuit)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Kazza2115/TIKTOKMONEYPRINTER/blob/claude/tiktok-clip-generator-31rslv/colab_demo.ipynb)

Sans rien installer : ouvre le notebook, exécute les 3 cellules, et tu obtiens une URL publique temporaire vers l'app (protégée par mot de passe). Il te faut juste un compte Google et ta clé API Claude. Active le GPU (*Exécution → Modifier le type d'exécution → T4*) pour une transcription rapide.

## 🌐 Site permanent gratuit (Hugging Face Spaces) — recommandé

URL fixe, gratuit, et **mise à jour automatique à chaque modification du code sur GitHub**. Configuration en ~10 minutes, une seule fois :

**1. Crée le Space (hébergement gratuit)**
- Compte gratuit sur [huggingface.co](https://huggingface.co) (pas de carte bancaire)
- [Créer un Space](https://huggingface.co/new-space) : nom `tiktokmoneyprinter`, licence au choix, SDK **Docker** (Blank), visibilité **Private** (recommandé : toi seul y accèdes)

**2. Crée un token d'accès**
- [Settings → Access Tokens](https://huggingface.co/settings/tokens) → **Create new token** → type **Write** → copie le token (`hf_...`)

**3. Branche GitHub sur le Space** (dans ton repo GitHub → **Settings → Secrets and variables → Actions**)
- Onglet **Secrets** → New repository secret : nom `HF_TOKEN`, valeur = ton token
- Onglet **Variables** → New repository variable : nom `HF_SPACE`, valeur = `ton-pseudo/tiktokmoneyprinter`

**4. Configure le Space** (page du Space → **Settings → Variables and secrets**)
- Secret `ANTHROPIC_API_KEY` (optionnel — pour le mode IA)
- Secret `APP_PASSWORD` (optionnel si le Space est privé)
- Secret `YTDLP_COOKIES` (contenu de ton export cookies.txt — pour débloquer YouTube)
- Variable `WHISPER_MODEL` = `small` (les Spaces ont 16 Go de RAM, autant en profiter)

C'est tout. Le prochain push GitHub déclenche le déploiement (~5 min de build), et ensuite **chaque modification du code met le site à jour automatiquement**. Ton app est sur la page du Space, ou en direct : `https://ton-pseudo-tiktokmoneyprinter.hf.space`.

À savoir : le Space s'endort après ~48 h sans visite (il se réveille en ~1 min à la première visite), les fichiers générés sont effacés au redémarrage (télécharge tes clips), et YouTube bloque aussi ces serveurs (d'où le secret `YTDLP_COOKIES`).

## 🌐 Alternative : Render (payant, plus robuste)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Kazza2115/TIKTOKMONEYPRINTER)

Le repo contient un `Dockerfile` et un `render.yaml` : la page se met en ligne en quelques clics et se redéploie automatiquement à chaque push GitHub.

1. Crée un compte sur [render.com](https://render.com) et connecte ton GitHub.
2. Clique le bouton ci-dessus (ou **New → Blueprint** et choisis ce repo).
3. Renseigne les variables d'environnement demandées :
   - `ANTHROPIC_API_KEY` — ta clé API Claude
   - `APP_PASSWORD` — mot de passe d'accès à la page (**obligatoire** : sans lui, n'importe qui peut consommer ta clé API)
4. Déploie. Ton URL sera du type `https://tiktokmoneyprinter.onrender.com`.

**À savoir pour le cloud :**

- **Plan Starter (~7 $/mois) recommandé** — le plan gratuit (512 Mo de RAM) est trop juste pour Whisper + ffmpeg. Le `render.yaml` force `WHISPER_MODEL=tiny` pour rester léger ; en local tu peux garder `small` ou mieux.
- **YouTube bloque souvent les IP de datacenter.** Si les téléchargements échouent avec « Sign in to confirm you're not a bot », exporte tes cookies YouTube (extension navigateur « Get cookies.txt LOCALLY ») et colle le contenu du fichier dans la variable d'environnement `YTDLP_COOKIES` sur Render.
- Les fichiers générés sont stockés en `/tmp` : ils disparaissent à chaque redéploiement. Télécharge tes clips au fur et à mesure.
- Le même `Dockerfile` fonctionne aussi sur Railway, Fly.io ou Hugging Face Spaces si tu préfères.

## ⚠️ Note légale

Télécharger du contenu YouTube tiers viole les CGU de la plateforme. Utilise cet outil sur **ton propre contenu** (ou du contenu dont tu as les droits) : tes vidéos, tes lives, tes sessions studio, les vidéos de tes artistes.

## Architecture

```
app/
├── config.py            # variables d'env, chemins, contraintes de durée
├── jobs.py              # orchestrateur : pipeline en thread + persistance JSON
├── routes.py            # API Flask + pages
├── pipeline/
│   ├── downloader.py    # yt-dlp
│   ├── transcriber.py   # faster-whisper (timestamps par mot)
│   ├── analyzer.py      # Claude : moments viraux + séries partie 1/2 + cliffhangers
│   ├── subtitles.py     # génération .ass (karaoké, hook, badge partie)
│   └── cutter.py        # ffmpeg : découpe + crop 9:16 + burn des sous-titres
├── templates/           # UI (Jinja2)
└── static/              # CSS + JS (polling du job)
```
