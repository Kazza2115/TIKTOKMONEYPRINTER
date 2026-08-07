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


def _list_formats(url: str, cookiefile) -> str:
    """Renvoie une liste compacte des formats disponibles (pour diagnostic)."""
    try:
        import yt_dlp

        o = {"quiet": True, "no_warnings": True, "skip_download": True}
        if cookiefile:
            o["cookiefile"] = str(cookiefile)
        with yt_dlp.YoutubeDL(o) as ydl:
            info = ydl.extract_info(url, download=False)
        fmts = info.get("formats") or []
        ids = sorted({f.get("format_id") for f in fmts if f.get("format_id")})
        return ", ".join(ids[:25]) if ids else ""
    except Exception:
        return ""


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

    base = {
        "merge_output_format": "mp4",
        "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "progress_hooks": [hook],
        "ffmpeg_location": config.FFMPEG,
    }

    # En hébergement cloud, YouTube bloque souvent les IP de datacenter
    # ("Sign in to confirm you're not a bot"). Fournis tes cookies via la
    # variable YTDLP_COOKIES : soit un export cookies.txt (format Netscape),
    # soit directement la ligne "cookie:" copiée depuis les outils de
    # développement du navigateur (F12) — convertie automatiquement.
    cookies = os.getenv("YTDLP_COOKIES")
    cookiefile = None
    if cookies and cookies.strip():
        cookiefile = dest_dir / ".cookies.txt"
        content = _to_netscape(cookies)
        cookiefile.write_text(content, encoding="utf-8")
        n = sum(1 for line in content.splitlines() if "\t" in line)
        names = [line.split("\t")[5] for line in content.splitlines() if line.count("\t") >= 6]
        essentials = [c for c in ("SID", "__Secure-3PSID", "LOGIN_INFO") if c in names]
        print(f"🍪 {n} cookies chargés (essentiels présents : {', '.join(essentials) or 'AUCUN ⚠️'})",
              flush=True)
    else:
        print("🍪 Aucun cookie fourni (YTDLP_COOKIES vide)", flush=True)

    def _attempt(clients, fmt):
        o = dict(base)
        o["extractor_args"] = {"youtube": {"player_client": clients}}
        if fmt:
            o["format"] = fmt
        if cookiefile:
            o["cookiefile"] = str(cookiefile)
        with yt_dlp.YoutubeDL(o) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info))
            if not path.exists():
                path = path.with_suffix(".mp4")
            if not path.exists():
                raise FileNotFoundError(f"Fichier téléchargé introuvable pour {url}")
            return info, path

    # cascade de configurations : on essaie plusieurs clients YouTube et
    # plusieurs sélecteurs de format, du plus souhaitable au plus permissif
    fmt_pref = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
    attempts = [
        (["web_safari", "web"], fmt_pref),
        (["mweb"], fmt_pref),
        (["tv"], None),
        (["web_safari"], None),
        (["ios"], None),
        (["default"], None),
    ]

    info = path = None
    last_err = ""
    for clients, fmt in attempts:
        try:
            info, path = _attempt(clients, fmt)
            print(f"✅ Téléchargé via client(s) {', '.join(clients)}", flush=True)
            break
        except Exception as e:
            last_err = str(e)
            continue

    if info is None:
        # diagnostic : liste ce que YouTube expose réellement pour cette vidéo
        available = _list_formats(url, cookiefile)
        low = last_err.lower()
        if "not a bot" in low or "sign in to confirm" in low or "403" in low or "forbidden" in low:
            hint = ("YouTube a refusé (blocage anti-bot / cookies expirés depuis un "
                    "serveur cloud). Refais un export de cookies TOUT frais.")
        else:
            hint = f"Formats vus par yt-dlp : {available or 'aucun'}."
        raise RuntimeError(
            f"Téléchargement impossible après plusieurs tentatives. {hint} "
            f"Dernière erreur : {last_err[:200]}"
        )

    return SourceVideo(
        path=path,
        title=info.get("title") or "video",
        duration=float(info.get("duration") or 0),
        width=int(info.get("width") or 0),
        height=int(info.get("height") or 0),
    )
