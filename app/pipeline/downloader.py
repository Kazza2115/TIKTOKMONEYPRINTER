"""Téléchargement de la vidéo source via yt-dlp (YouTube, Twitch, Vimeo, ...)."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class SourceVideo:
    path: Path
    title: str
    duration: float  # secondes
    width: int
    height: int


def download(url: str, dest_dir: Path, progress_cb=None) -> SourceVideo:
    """Télécharge la meilleure qualité <=1080p et retourne les métadonnées."""
    try:
        import yt_dlp
    except ImportError as e:
        raise RuntimeError("yt-dlp n'est pas installé. Lance : pip install yt-dlp") from e

    def hook(d):
        if progress_cb and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                progress_cb(d.get("downloaded_bytes", 0) / total)

    opts = {
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "merge_output_format": "mp4",
        "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info))
        # après merge, l'extension finale est mp4
        if not path.exists():
            path = path.with_suffix(".mp4")
        if not path.exists():
            raise FileNotFoundError(f"Fichier téléchargé introuvable pour {url}")

    return SourceVideo(
        path=path,
        title=info.get("title") or "video",
        duration=float(info.get("duration") or 0),
        width=int(info.get("width") or 0),
        height=int(info.get("height") or 0),
    )
