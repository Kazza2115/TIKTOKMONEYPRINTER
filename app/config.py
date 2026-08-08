import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data")).resolve()
DOWNLOADS_DIR = DATA_DIR / "downloads"
CLIPS_DIR = DATA_DIR / "clips"
JOBS_DIR = DATA_DIR / "jobs"

for d in (DOWNLOADS_DIR, CLIPS_DIR, JOBS_DIR):
    d.mkdir(parents=True, exist_ok=True)

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5")
YT_API_KEY = os.getenv("YT_API_KEY", "")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")
MAX_CLIPS = int(os.getenv("MAX_CLIPS", "5"))

def _find_ffmpeg() -> str:
    """Chemin vers ffmpeg : celui du système s'il existe, sinon le binaire
    fourni par imageio-ffmpeg (installé via requirements) — évite toute
    installation manuelle de ffmpeg en local."""
    import shutil

    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"  # laissera remonter une erreur claire au moment de l'appel


FFMPEG = _find_ffmpeg()

# Contraintes de durée des clips par défaut (secondes) — modifiables par job
# dans l'interface. Min 60 s par défaut : TikTok ne monétise qu'à partir d'1 min.
CLIP_MIN_DURATION = int(os.getenv("CLIP_MIN_DURATION", "60"))
CLIP_MAX_DURATION = int(os.getenv("CLIP_MAX_DURATION", "180"))  # au-delà : Partie 1/2/...
