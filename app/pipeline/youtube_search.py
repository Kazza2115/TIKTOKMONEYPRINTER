"""Recherche de vidéos YouTube par thème, classées par viralité (vues/jour).
Utilise l'API officielle YouTube Data v3 (nécessite YT_API_KEY dans le .env).
"""

import json
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from .. import config

API = "https://www.googleapis.com/youtube/v3"


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


def _get(endpoint: str, params: dict) -> dict:
    params = {**params, "key": config.YT_API_KEY}
    url = f"{API}/{endpoint}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _parse_duration(iso: str) -> int:
    """PT1H2M3S -> secondes."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def _days_since(iso: str) -> float:
    try:
        pub = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return max((datetime.now(timezone.utc) - pub).total_seconds() / 86400, 1.0)
    except Exception:
        return 1.0


def search(query: str, duration: str = "long", recency_days: int = 180,
           max_results: int = 12, language: str = "fr") -> list[dict]:
    """Cherche des vidéos et les classe par vues/jour (viralité récente).

    duration : "any" | "medium" (4-20 min) | "long" (>20 min) — pour cibler du
    contenu long découpable plutôt que des Shorts déjà finis.
    """
    if not config.YT_API_KEY:
        raise RuntimeError(
            "Recherche indisponible : ajoute YT_API_KEY dans ton fichier .env. "
            "Obtiens une clé gratuite sur https://console.cloud.google.com/ "
            "(active « YouTube Data API v3 »)."
        )
    if not query.strip():
        raise RuntimeError("Entre un thème de recherche.")

    published_after = None
    if recency_days:
        from datetime import timedelta

        published_after = (
            datetime.now(timezone.utc) - timedelta(days=recency_days)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

    search_params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "viewCount",
        "maxResults": 40,
        "relevanceLanguage": language or "fr",
    }
    if duration in ("medium", "long", "short"):
        search_params["videoDuration"] = duration
    if published_after:
        search_params["publishedAfter"] = published_after

    data = _get("search", search_params)
    ids = [it["id"]["videoId"] for it in data.get("items", []) if it.get("id", {}).get("videoId")]
    if not ids:
        return []

    # récupère stats (vues) + durée réelle
    details = _get("videos", {"part": "statistics,contentDetails,snippet", "id": ",".join(ids)})
    hits: list[VideoHit] = []
    for it in details.get("items", []):
        vid = it["id"]
        stats = it.get("statistics", {})
        views = int(stats.get("viewCount", 0))
        dur = _parse_duration(it.get("contentDetails", {}).get("duration", ""))
        if dur < 30:  # écarte les Shorts / clips déjà courts
            continue
        published = it.get("snippet", {}).get("publishedAt", "")
        vpd = int(views / _days_since(published))
        thumbs = it.get("snippet", {}).get("thumbnails", {})
        thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
        hits.append(
            VideoHit(
                video_id=vid,
                title=it.get("snippet", {}).get("title", ""),
                channel=it.get("snippet", {}).get("channelTitle", ""),
                url=f"https://www.youtube.com/watch?v={vid}",
                thumbnail=thumb,
                views=views,
                duration_sec=dur,
                published=published[:10],
                views_per_day=vpd,
            )
        )

    hits.sort(key=lambda h: h.views_per_day, reverse=True)
    return [asdict(h) for h in hits[:max_results]]
