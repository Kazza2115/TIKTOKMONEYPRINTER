"""Recherche de vidéos YouTube par thème — SANS clé API.
Utilise la recherche intégrée de yt-dlp (ytsearch), classée par nombre de vues.
Aucune configuration : ça marche dès que yt-dlp fonctionne (ton PC maison).
"""

import os
import random
from dataclasses import asdict, dataclass

DURATION_RANGES = {
    "short": (0, 240),         # jusqu'à 4 min (inclut les Shorts)
    "medium": (240, 1200),     # 4 - 20 min
    "long": (1200, 10 ** 9),   # > 20 min
    "any": (0, 10 ** 9),       # toutes durées
}


@dataclass
class VideoHit:
    video_id: str
    title: str
    channel: str
    url: str
    thumbnail: str
    views: int
    duration_sec: int
    published: str
    views_per_day: int


def search(query: str, duration: str = "long", recency_days: int = 180,
           max_results: int = 12, language: str = "fr") -> list[dict]:
    """Cherche des vidéos via yt-dlp et les classe par nombre de vues.

    duration : "any" | "short" | "medium" | "long" — pour cibler du contenu
    long découpable plutôt que des Shorts déjà finis.
    (recency_days est accepté pour compatibilité mais non filtré ici.)
    """
    query = query.strip()
    if not query:
        raise RuntimeError("Entre un thème de recherche.")

    try:
        import yt_dlp
    except ImportError as e:
        raise RuntimeError("yt-dlp n'est pas installé.") from e

    lo, hi = DURATION_RANGES.get(duration, DURATION_RANGES["any"])

    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",  # rapide : pas de téléchargement, juste les métadonnées
        "default_search": "ytsearch",
        "noplaylist": True,
    }
    cookies = os.getenv("YTDLP_COOKIES")
    if cookies and cookies.strip():
        # réutilise le même mécanisme de cookies que le téléchargeur
        from . import downloader
        from .. import config

        cookie_file = config.DOWNLOADS_DIR / ".cookies.txt"
        cookie_file.write_text(downloader._to_netscape(cookies), encoding="utf-8")
        opts["cookiefile"] = str(cookie_file)

    # on demande large (60) puis on filtre/trie côté serveur
    search_url = f"ytsearch60:{query}"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(search_url, download=False)
    except Exception as e:
        raise RuntimeError(f"Recherche échouée : {str(e)[:200]}") from e

    hits: list[VideoHit] = []
    for entry in (data.get("entries") or []):
        if not entry:
            continue
        vid = entry.get("id")
        if not vid:
            continue
        dur = int(entry.get("duration") or 0)
        if dur <= 0 or dur < lo or dur > hi:
            continue
        views = int(entry.get("view_count") or 0)
        # miniature fiable construite depuis l'ID
        thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
        hits.append(
            VideoHit(
                video_id=vid,
                title=entry.get("title") or "",
                channel=entry.get("channel") or entry.get("uploader") or "",
                url=f"https://www.youtube.com/watch?v={vid}",
                thumbnail=thumb,
                views=views,
                duration_sec=dur,
                published="",          # non fourni par la recherche rapide
                views_per_day=0,        # idem : on classe par vues totales
            )
        )

    # classe par nombre de vues (les plus vues = les plus virales sur le thème)
    hits.sort(key=lambda h: h.views, reverse=True)

    # recherche "vivante" : au lieu de renvoyer toujours le même top figé, on
    # constitue un large réservoir des plus vues et on en tire un échantillon
    # aléatoire — deux recherches du même thème donnent des vidéos différentes,
    # mais toujours parmi les plus virales.
    pool = hits[: max(max_results * 3, 30)]
    if len(pool) > max_results:
        sample = random.sample(pool, max_results)
    else:
        sample = pool
    sample.sort(key=lambda h: h.views, reverse=True)
    return [asdict(h) for h in sample]
