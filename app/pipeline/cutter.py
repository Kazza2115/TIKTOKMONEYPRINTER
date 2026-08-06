"""Découpe et montage ffmpeg : extraction du segment, recadrage 9:16 (1080x1920),
incrustation des sous-titres/hook/badge depuis le fichier .ass.
"""

import shutil
import subprocess
from pathlib import Path

# recadrage centré vers 9:16 quel que soit le format source, puis mise à l'échelle
CROP_916 = (
    "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',"
    "scale=1080:1920:force_original_aspect_ratio=increase,"
    "crop=1080:1920"
)


def ensure_ffmpeg():
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg introuvable. Installe-le d'abord (Windows : winget install ffmpeg / "
            "scoop install ffmpeg ; Debian/Ubuntu : sudo apt install ffmpeg)."
        )


def _ass_filter_path(ass_path: Path) -> str:
    """Échappe le chemin pour le filtre ass= de ffmpeg (Windows inclus)."""
    p = str(ass_path).replace("\\", "/")
    p = p.replace(":", "\\:").replace("'", "\\'")
    return p


def cut_clip(
    source: Path,
    start: float,
    end: float,
    ass_path: Path | None,
    out_path: Path,
) -> Path:
    ensure_ffmpeg()

    vf = CROP_916
    if ass_path is not None:
        vf += f",ass='{_ass_filter_path(ass_path)}'"

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", f"{start:.3f}",
        "-to", f"{end:.3f}",
        "-i", str(source),
        "-vf", vf,
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
