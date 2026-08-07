"""Téléchargement de la vidéo source via yt-dlp (YouTube, Twitch, Vimeo, ...)."""

import os
from dataclasses import dataclass
from pathlib import Path


def _to_netscape(cookies_text: str) -> str:
    """Accepte soit un fichier cookies.txt (format Netscape, avec tabulations),
    soit la valeur brute de l'en-tête "cookie:" copiée depuis les outils de
    développement (format "NOM=valeur; NOM2=valeur2; ...") qu'on convertit."""
    txt = cookies_text.strip()
    if txt.lower().startswith("cookie:"):
        txt = txt[len("cookie:"):].strip()
    if "\t" in txt or txt.startswith("# Netscape"):
        return txt  # déjà au format Netscape

    lines = ["# Netscape HTTP Cookie File"]
    for pair in txt.split(";"):
        name, sep, value = pair.strip().partition("=")
        if not sep or not name:
            continue
        lines.append(f".youtube.com\tTRUE\t/\tTRUE\t2147483647\t{name}\t{value}")
    return "\n".join(lines) + "\n"


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

    # En hébergement cloud, YouTube bloque souvent les IP de datacenter
    # ("Sign in to confirm you're not a bot"). Fournis tes cookies via la
    # variable YTDLP_COOKIES : soit un export cookies.txt (format Netscape),
    # soit directement la ligne "cookie:" copiée depuis les outils de
    # développement du navigateur (F12) — convertie automatiquement.
    cookies = os.getenv("YTDLP_COOKIES")
    if cookies and cookies.strip():
        cookie_file = dest_dir / ".cookies.txt"
        cookie_file.write_text(_to_netscape(cookies), encoding="utf-8")
        opts["cookiefile"] = str(cookie_file)

    def _attempt(o):
        with yt_dlp.YoutubeDL(o) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info))
            # après merge, l'extension finale est mp4
            if not path.exists():
                path = path.with_suffix(".mp4")
            if not path.exists():
                raise FileNotFoundError(f"Fichier téléchargé introuvable pour {url}")
            return info, path

    try:
        info, path = _attempt(opts)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        blocked = "403" in msg or "Forbidden" in msg or "not a bot" in msg.lower()
        if blocked:
            # 2e essai avec le client Android (contourne parfois le blocage)
            retry = dict(opts)
            retry["extractor_args"] = {"youtube": {"player_client": ["android"]}}
            try:
                info, path = _attempt(retry)
            except yt_dlp.utils.DownloadError as e2:
                raise RuntimeError(
                    "Téléchargement bloqué par la plateforme (403). C'est fréquent sur les "
                    "serveurs cloud : YouTube bloque les IP de datacenter (Colab, Render...). "
                    "Solutions : 1) fournis tes cookies YouTube via YTDLP_COOKIES (cellule "
                    "« Cookies » du notebook) ; 2) essaie une autre plateforme (Vimeo, "
                    "Twitch...) ; 3) fais tourner l'app en local sur ton PC — ton IP "
                    "résidentielle n'est pas bloquée."
                ) from e2
        else:
            raise RuntimeError(f"Téléchargement impossible : {msg[:300]}") from e

    return SourceVideo(
        path=path,
        title=info.get("title") or "video",
        duration=float(info.get("duration") or 0),
        width=int(info.get("width") or 0),
        height=int(info.get("height") or 0),
    )
