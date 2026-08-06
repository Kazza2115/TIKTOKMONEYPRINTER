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
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")
MAX_CLIPS = int(os.getenv("MAX_CLIPS", "5"))

# Contraintes de durée des clips (secondes)
CLIP_MIN_DURATION = 12
CLIP_MAX_DURATION = 62  # au-delà, l'IA doit découper en Partie 1/2/...
