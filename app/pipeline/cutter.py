"""Découpe et montage ffmpeg : extraction du segment, mise au format 9:16
(1080x1920) et incrustation des sous-titres/hook/badge depuis le fichier .ass.

Deux cadrages :
- "fit"  (défaut) : la vidéo entière est visible, centrée, sur un fond flouté
  (style TikTok classique — rien n'est coupé)
- "crop" : plein écran zoomé, recadrage centré (coupe les côtés)

Un facteur `zoom` (>= 1.0) agrandit progressivement l'image dans les deux
modes : à 1.0 on garde le cadrage de base, plus on monte plus l'image remplit
le cadre (en mode "fit" le fond flou disparaît peu à peu). Ça permet de régler
finement le zoom au lieu du recadrage brutal tout ou rien.
"""

import os
import subprocess
from pathlib import Path

from .. import config

ZOOM_MIN = 0.5
ZOOM_MAX = 3.0


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


def _clamp_zoom(zoom: float) -> float:
    try:
        z = float(zoom)
    except (TypeError, ValueError):
        return 1.0
    return max(ZOOM_MIN, min(z, ZOOM_MAX))


def build_filter_args(framing: str, ass_path: Path | None,
                      zoom: float = 1.0) -> list[str]:
    """Compose toujours la vidéo sur un fond flouté qui remplit le cadre 9:16,
    donc jamais de bandes noires quel que soit le zoom.

    - framing "crop" (défaut) : à zoom=1 la vidéo REMPLIT l'écran (plein écran,
      les côtés sont rognés). zoom>1 = zoom avant (plus serré). zoom<1 = zoom
      arrière (on voit plus de la vidéo, le fond flou apparaît autour).
    - framing "fit" : à zoom=1 la vidéo entière est visible (rien coupé) sur le
      fond flou ; zoom règle sa taille.
    """
    ass = f",ass='{_ass_filter_path(ass_path)}'" if ass_path else ""
    z = _clamp_zoom(zoom)
    zw, zh = f"{1080 * z:.1f}", f"{1920 * z:.1f}"

    # "increase" = la vidéo COUVRE le cadre (plein écran) ; "decrease" = elle
    # tient ENTIÈREMENT dedans (rien coupé). Le zoom multiplie la cible.
    ar = "decrease" if framing == "fit" else "increase"

    fc = (
        "[0:v]split=2[bg][fg];"
        "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=24:4[bgb];"
        f"[fg]scale={zw}:{zh}:force_original_aspect_ratio={ar}[fgs];"
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
    zoom: float = 1.0,
) -> Path:
    ensure_ffmpeg()

    cmd = [
        config.FFMPEG,
        "-y",
        "-ss", f"{start:.3f}",
        "-to", f"{end:.3f}",
        "-i", str(source),
        *build_filter_args(framing, ass_path, zoom),
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
