"""Téléchargement de la vidéo source via yt-dlp (YouTube, Twitch, Vimeo, ...)."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

from .. import config


def _to_netscape(cookies_text: str) -> str:
    """Accepte soit un fichier cookies.txt (format Netscape, avec tabulations),
    soit la valeur brute de l'en-tête "cookie:" copiée depuis les outils de
    développement (format "NOM=valeur; NOM2=valeur2; ...") qu'on convertit.
    Tolère le mot « cookie » collé devant la valeur et les retours à la ligne."""
    txt = cookies_text.strip()
    if "\t" in txt or txt.startswith("# Netscape"):
        return txt  # déjà au format Netscape

    # retire un éventuel préfixe "cookie" / "cookie:" (nom de l'en-tête copié
    # avec sa valeur) et les retours à la ligne dus au retour automatique
    txt = re.sub(r"^\s*cookies?\s*:?\s*", "", txt, flags=re.IGNORECASE)
    txt = " ".join(txt.split())

    lines = ["# Netscape HTTP Cookie File"]
    for pair in txt.split(";"):
        name, sep, value = pair.strip().partition("=")
        name = name.strip()
        if not sep or not name or " " in name:
            continue
        lines.append(f".youtube.com\tTRUE\t/\tTRUE\t2147483647\t{name}\t{value.strip()}")
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
        # sélection souple : idéalement <=1080p, sinon la meilleure dispo,
        # sinon n'importe quel format en dernier recours
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "progress_hooks": [hook],
        # clients les plus résistants à la détection anti-bot de YouTube
        "extractor_args": {"youtube": {"player_client": ["tv", "web_safari", "web"]}},
        "ffmpeg_location": config.FFMPEG,
    }

    # En hébergement cloud, YouTube bloque souvent les IP de datacenter
    # ("Sign in to confirm you're not a bot"). Fournis tes cookies via la
    # variable YTDLP_COOKIES : soit un export cookies.txt (format Netscape),
    # soit directement la ligne "cookie:" copiée depuis les outils de
    # développement du navigateur (F12) — convertie automatiquement.
    cookies = os.getenv("YTDLP_COOKIES")
    if cookies and cookies.strip():
        cookie_file = dest_dir / ".cookies.txt"
        content = _to_netscape(cookies)
        cookie_file.write_text(content, encoding="utf-8")
        opts["cookiefile"] = str(cookie_file)
        n = sum(1 for line in content.splitlines() if "\t" in line)
        names = [line.split("\t")[5] for line in content.splitlines() if line.count("\t") >= 6]
        essentials = [c for c in ("SID", "__Secure-3PSID", "LOGIN_INFO") if c in names]
        print(f"🍪 {n} cookies chargés (essentiels présents : {', '.join(essentials) or 'AUCUN ⚠️'})",
              flush=True)
    else:
        print("🍪 Aucun cookie fourni (YTDLP_COOKIES vide)", flush=True)

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
        low = msg.lower()
        blocked = "403" in msg or "forbidden" in low or "not a bot" in low
        bad_format = "requested format" in low or "format is not available" in low

        if blocked or bad_format:
            # 2e essai : format le plus permissif + clients compatibles cookies.
            # (le client "android" ignore les cookies : on ne l'utilise que
            #  s'il n'y a PAS de cookies, sinon on garde les clients par défaut)
            retry = dict(opts)
            retry.pop("format", None)  # laisse yt-dlp choisir le meilleur défaut
            if not opts.get("cookiefile"):
                retry["extractor_args"] = {"youtube": {"player_client": ["android", "web"]}}
            try:
                info, path = _attempt(retry)
            except yt_dlp.utils.DownloadError as e2:
                if "403" in str(e2) or "forbidden" in str(e2).lower():
                    raise RuntimeError(
                        "Téléchargement bloqué par YouTube (403). Tes cookies sont "
                        "probablement expirés : refais un export frais et mets à jour "
                        "le secret YTDLP_COOKIES."
                    ) from e2
                raise RuntimeError(f"Téléchargement impossible : {str(e2)[:300]}") from e2
        else:
            raise RuntimeError(f"Téléchargement impossible : {msg[:300]}") from e

    return SourceVideo(
        path=path,
        title=info.get("title") or "video",
        duration=float(info.get("duration") or 0),
        width=int(info.get("width") or 0),
        height=int(info.get("height") or 0),
    )
