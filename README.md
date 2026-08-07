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

## ⭐ Sur ton PC, accessible partout depuis ton téléphone — LE plus fiable

C'est **la** solution recommandée pour YouTube : ton PC télécharge avec ton adresse IP maison (jamais bloquée par YouTube, contrairement aux serveurs cloud), et un tunnel te donne un **lien public** ouvrable depuis ton téléphone n'importe où. Seule condition : le PC allumé quand tu bosses.

**Prérequis (une seule fois) :** installe [Python](https://www.python.org/downloads/) en cochant **« Add Python to PATH »**. (Pas besoin d'installer ffmpeg : il est fourni automatiquement.)

**Mise en route :**
1. Télécharge le projet : sur la page GitHub → bouton vert **Code → Download ZIP** → décompresse le dossier
2. Double-clique **`start.bat`** (Windows) ou **`start.command`** (Mac)
3. Au tout premier lancement, il crée un fichier `.env` : ouvre-le avec le Bloc-notes, mets ta clé `ANTHROPIC_API_KEY=sk-ant-...` et un `APP_PASSWORD=tonmotdepasse`, enregistre, puis relance `start.bat`
4. Une adresse **`https://....trycloudflare.com`** s'affiche → ouvre-la sur ton téléphone, entre le mot de passe → tu as l'appli, où que tu sois

Sur téléphone : menu du navigateur → **« Ajouter à l'écran d'accueil »** pour l'avoir comme une vraie appli.

> ℹ️ Le lien change à chaque redémarrage du PC (tunnel gratuit). Pour un **lien fixe permanent** — idéal si tu bosses depuis un PC verrouillé (travail) où tu ne peux rien installer — voir la section ci-dessous.

## 🔒 Lien fixe permanent (bosser depuis un PC verrouillé / le travail)

Idée : ton **PC perso à la maison** est le moteur (il télécharge avec ton IP maison, YouTube marche), et il expose un **lien fixe** que tu ouvres depuis **n'importe quel navigateur** (PC du travail, téléphone) — **rien à installer côté client**. Le PC maison doit rester allumé.

On utilise **Tailscale Funnel** (gratuit, lien permanent `https://...ts.net`, sans nom de domaine).

**Configuration sur ton PC maison (une seule fois) :**
1. Crée un compte gratuit sur [tailscale.com](https://tailscale.com) et installe [Tailscale pour Windows](https://tailscale.com/download/windows), puis connecte-toi (icône dans la barre des tâches)
2. Active Funnel dans la console d'admin :
   - Va sur [login.tailscale.com/admin/dns](https://login.tailscale.com/admin/dns) → active **MagicDNS** et **HTTPS Certificates**
   - Va sur [login.tailscale.com/admin/acls](https://login.tailscale.com/admin/acls) → dans les `nodeAttrs`, ajoute l'attribut `funnel` à ton appareil (Tailscale documente le bloc exact à coller ; en cas de doute, demande-moi et je te donne les lignes précises)
3. Double-clique **`start-lien-fixe.bat`** — il démarre l'app et affiche ton lien fixe `https://<ton-pc>.<...>.ts.net`

**Ensuite, depuis le PC du travail ou ton téléphone :** ouvre simplement ce lien dans le navigateur, entre ton `APP_PASSWORD`, et travaille. Le lien ne change jamais — mets-le en favori ou sur l'écran d'accueil.

## 📱 L'application web (GitHub Pages) — pour piloter depuis le cloud

Une page avec un lien fixe, utilisable depuis ton téléphone ou n'importe où, qui pilote la génération sur GitHub. Configuration une seule fois :

**1. Active GitHub Pages** : repo → **Settings → Pages** → Source : **Deploy from a branch** → Branch : `claude/tiktok-clip-generator-31rslv`, dossier **/docs** → Save. Ton lien : `https://kazza2115.github.io/TIKTOKMONEYPRINTER/` (actif après ~2 min).

**2. Crée un token d'accès** (c'est la « clé » qui autorise la page à lancer les générations) : [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new) → Repository access : **Only select repositories → TIKTOKMONEYPRINTER** → Permissions → Repository permissions → **Actions : Read and write** → Generate token → copie le `github_pat_...`

**3. Ouvre ton lien** et colle le token (mémorisé sur l'appareil). Sur téléphone : menu du navigateur → **« Ajouter à l'écran d'accueil »** pour l'utiliser comme une vraie appli.

Ensuite : colle une URL → 🚀 Générer → la page suit la progression → à la fin, ouvre le run pour lire le résumé (hooks, légendes) et télécharger le **zip « clips »** (section Artifacts en bas de page).

## ⚙️ Générer des clips directement depuis l'onglet Actions (sans la page)

Aucun hébergement à configurer : le pipeline tourne sur les serveurs de GitHub Actions, gratuitement.

1. Onglet **Actions** du repo → workflow **« 🎬 Générer des clips »** → **Run workflow**
2. Remplis le formulaire (URL, mode, cadrage, durées...) → **Run workflow**
3. Attends ~5-10 min → ouvre le run → les clips sont dans le **zip « clips »** en bas de page (section *Artifacts*), et le résumé (hooks, légendes, scores) s'affiche directement sur la page du run

Secrets optionnels (**Settings → Secrets and variables → Actions → Secrets**) :
- `ANTHROPIC_API_KEY` — pour le mode IA
- `YTDLP_COOKIES` — contenu d'un export cookies.txt pour débloquer YouTube (les serveurs GitHub sont aussi des IP datacenter)

Limites : pas d'aperçu vidéo dans le navigateur (on télécharge le zip), et les artifacts sont gardés 7 jours. Pour une vraie page web permanente, voir Hugging Face Spaces ci-dessous.

## 🌐 Site permanent gratuit (Hugging Face Spaces)

> 💡 Au moment de créer le Space, choisis SDK **Docker → Blank** puis hardware **« CPU basic · 2 vCPU · 16 GB · FREE »** — c'est bien gratuit ; les prix affichés concernent les machines plus puissantes optionnelles.

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
