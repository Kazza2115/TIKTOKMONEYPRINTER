"""Découpe et montage ffmpeg : extraction du segment, mise au format 9:16
(1080x1920) et incrustation des sous-titres/hook/badge depuis le fichier .ass.

Deux cadrages :
- "fit"  (défaut) : la vidéo entière est visible, centrée, sur un fond flouté
  (style TikTok classique — rien n'est coupé)
- "crop" : plein écran zoomé, recadrage centré (coupe les côtés)
"""

import os
import subprocess
from pathlib import Path

from .. import config

# recadrage centré vers 9:16 (mode "crop")
CROP_916 = (
    "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',"
    "scale=1080:1920:force_original_aspect_ratio=increase,"
    "crop=1080:1920"
)


def ensure_ffmpeg():
    exe = config.FFMPEG
    ok = os.path.isfile(exe) or (
        __import__("shutil").which(exe) is not None
    )
    if not ok:
        raise RuntimeError(
            "ffmpeg introuvable. Il est normalement fourni automatiquement par "
            "imageio-ffmpeg (pip install -r requirements.txt). En dernier recours : "
            "Windows → winget install ffmpeg ; Debian/Ubuntu → sudo apt install ffmpeg."
        )


def _ass_filter_path(ass_path: Path) -> str:
    """Échappe le chemin pour le filtre ass= de ffmpeg (Windows inclus)."""
    p = str(ass_path).replace("\\", "/")
    p = p.replace(":", "\\:").replace("'", "\\'")
    return p


def build_filter_args(framing: str, ass_path: Path | None) -> list[str]:
    ass = f",ass='{_ass_filter_path(ass_path)}'" if ass_path else ""

    if framing == "crop":
        return ["-vf", CROP_916 + ass]

    # "fit" : vidéo entière + fond flouté qui remplit le cadre
    fc = (
        "[0:v]split=2[bg][fg];"
        "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=24:4[bgb];"
        "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fgs];"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2{ass}[v]"
    )
    return ["-filter_complex", fc, "-map", "[v]", "-map", "0:a?"]


def cut_clip(
    source: Path,
    start: float,
    end: float,
    ass_path: Path | None,
    out_path: Path,
    framing: str = "fit",
) -> Path:
    ensure_ffmpeg()

    cmd = [
        config.FFMPEG,
        "-y",
        "-ss", f"{start:.3f}",
        "-to", f"{end:.3f}",
        "-i", str(source),
        *build_filter_args(framing, ass_path),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(out_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = result.stderr[-2000:] if result.stderr else "aucune sortie"
        raise RuntimeError(f"ffmpeg a échoué sur {out_path.name} :\n{tail}")
    return out_path
