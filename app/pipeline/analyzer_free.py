"""Mode automatique GRATUIT (sans API) : sélection heuristique des moments forts.

Moins malin que l'analyse IA, mais 100 % local et gratuit. Principe :
- chaque segment du transcript reçoit un score (mots d'accroche, questions,
  exclamations, chiffres, densité de parole)
- on construit des fenêtres de clips (20-50 s) autour des pics de score
- si le meilleur passage s'étire au-delà de la durée max, on le découpe en
  série Partie 1/2 avec coupe en fin de tension (cliffhanger approximatif)
"""

import re
from collections import Counter

from . import analyzer
from .. import config
from .transcriber import Segment, Transcript

# mots/expressions qui signalent un moment fort (français + anglais)
HOOK_WORDS = [
    # français
    "jamais", "personne", "secret", "vérité", "verite", "fou", "dingue",
    "incroyable", "choqué", "choque", "grave", "abusé", "abuse", "attends",
    "écoute", "ecoute", "regarde", "problème", "probleme", "argent", "euros",
    "histoire", "raconte", "avoue", "franchement", "en vrai", "wesh",
    "truc de ouf", "je te jure", "tu sais pas", "révèle", "revele", "cash",
    "million", "interdit", "caché", "cache", "peur", "pire", "meilleur",
    "première fois", "premiere fois", "dernière fois", "derniere fois",
    # anglais
    "never", "nobody", "everybody", "secret", "truth", "crazy", "insane",
    "money", "dollars", "story", "listen", "wait", "look", "problem",
    "believe", "shocked", "worst", "best", "first time", "last time",
    "biggest", "reveal", "honestly", "literally", "actually", "the thing is",
    "you won't", "you wont", "i swear", "guess what", "here's why", "heres why",
    "million", "billion", "changed my life", "nobody tells you", "mistake",
    "afraid", "scared", "danger", "illegal", "banned", "hidden", "warning",
]

STOPWORDS = set(
    "le la les un une des de du d l et ou mais donc or ni car que qui quoi "
    "dont où a à au aux ce cette ces cet il elle ils elles on nous vous je tu "
    "me te se ne pas plus moins très tres bien mal avec sans pour par sur sous "
    "dans est sont était etait être etre avoir fait faire dit dire ça ca c'est "
    "cest comme alors aussi tout tous toute toutes rien quelque chose là la-bas "
    "the a an and or but of to in is are was were be have has this that".split()
)



def _segment_score(seg: Segment) -> float:
    text = seg.text.lower()
    score = 0.0
    for w in HOOK_WORDS:
        if w in text:
            score += 2.0
    score += text.count("?") * 2.5      # questions = engagement
    score += text.count("!") * 1.5      # exclamations = émotion
    score += len(re.findall(r"\d", text)) * 0.5  # chiffres = concret
    dur = max(seg.end - seg.start, 0.5)
    words_per_sec = len(seg.words) / dur if seg.words else len(text.split()) / dur
    if words_per_sec > 2.5:             # débit élevé = énergie
        score += 1.5
    return score / max(dur / 10, 1.0)   # normalise par durée


def _make_hook(segments: list[Segment]) -> str:
    """Prend les premiers mots de la phrase la plus forte comme hook."""
    best = max(segments, key=_segment_score)
    words = best.text.strip().split()[:8]
    hook = " ".join(words).strip(" .,;:")
    return hook.upper()


def _make_caption(segments: list[Segment]) -> str:
    text = " ".join(s.text for s in segments).lower()
    words = [w.strip(".,!?;:'\"()") for w in text.split()]
    freq = Counter(w for w in words if len(w) > 4 and w not in STOPWORDS)
    tags = "".join(f" #{w}" for w, _ in freq.most_common(3))
    first_sentence = re.split(r"[.!?]", segments[0].text.strip())[0][:100]
    return f"{first_sentence}… ton avis ? 👇{tags} #pourtoi #fyp"


def _window_score(segments: list[Segment]) -> float:
    return sum(_segment_score(s) for s in segments)


def _trim_dead_edges(segs: list[Segment], i: int, j: int) -> tuple[int, int]:
    """Retire les segments sans aucun intérêt en début et fin de fenêtre
    (le recalage sur le début du sujet se fait ensuite via les pauses)."""
    while i < j - 1 and _segment_score(segs[i]) <= 0:
        i += 1
    while j - 1 > i and _segment_score(segs[j - 1]) <= 0:
        j -= 1
    return i, j


def _ensure_min_length(segs: list[Segment], i: int, j: int, min_dur: float,
                       used: set[int]) -> tuple[int, int]:
    """Étend la fenêtre (fin d'abord, puis début) jusqu'à la durée minimale,
    même sur des segments calmes — un clip trop court est inutilisable."""
    def length():
        return segs[j - 1].end - segs[i].start

    while length() < min_dur and j < len(segs) and j not in used:
        j += 1
    while length() < min_dur and i > 0 and (i - 1) not in used:
        i -= 1
    return i, j


def _snap_to_topic_start(segs: list[Segment], i: int, end_time: float,
                         used: set[int], max_dur: float,
                         max_extra: float = 15.0,
                         min_gap: float = 0.8) -> int:
    """Recule le début du clip jusqu'au début de la prise de parole en cours
    (la pause précédente marque généralement le début du sujet), pour éviter
    de démarrer au milieu d'une phrase ou d'une explication."""
    j = i
    while j > 0:
        prev = segs[j - 1]
        if (j - 1) in used:
            break
        if segs[j].start - prev.end >= min_gap:
            break  # pause : on est au début d'une prise de parole
        if segs[i].start - prev.start > max_extra:
            break
        if end_time - prev.start > max_dur:
            break
        j -= 1
    return j


def analyze_free(transcript: Transcript, video_title: str, duration: float,
                 max_clips: int | None = None, min_dur: int | None = None,
                 max_dur: int | None = None) -> analyzer.ClipPlan:
    max_clips = max_clips or config.MAX_CLIPS
    min_dur = float(min_dur or config.CLIP_MIN_DURATION)
    max_dur = float(max_dur or config.CLIP_MAX_DURATION)
    # vidéo plus courte que le minimum demandé : on prend ce qu'on peut
    min_dur = min(min_dur, max(duration - 2.0, 3.0))

    segs = [s for s in transcript.segments if s.text.strip()]
    if not segs:
        raise RuntimeError("Transcript vide : impossible de sélectionner des clips.")

    # --- construit toutes les fenêtres candidates (min-max s, bornées aux segments)
    candidates: list[tuple[float, int, int]] = []  # (score, i_start, i_end_exclu)
    for i in range(len(segs)):
        j = i
        while j < len(segs) and segs[j].end - segs[i].start <= max_dur:
            j += 1
            window = segs[i:j]
            length = window[-1].end - window[0].start
            if length >= min_dur:
                candidates.append((_window_score(window), i, j))
    if not candidates:  # vidéo très courte : prend tout
        candidates = [(1.0, 0, len(segs))]

    # tri par score décroissant ; s'il n'y a aucun signal fort (vidéo calme,
    # langue non couverte...), on ordonne par position pour couvrir la vidéo
    best_score = candidates[0][0]
    has_signal = best_score > 0
    denom = best_score or 1.0
    if not has_signal:
        candidates.sort(key=lambda c: c[1])  # par ordre chronologique
    else:
        candidates.sort(reverse=True, key=lambda c: c[0])

    used: set[int] = set()
    clips: list[analyzer.ClipSuggestion] = []

    # --- 1. le meilleur passage devient une série Partie 1/2 s'il s'étire
    _, bi, bj = candidates[0]
    bi, bj = _trim_dead_edges(segs, bi, bj)
    bi = _snap_to_topic_start(segs, bi, segs[bj - 1].end, used, max_dur)
    series = _try_extend_series(segs, bi, bj, used, min_dur, max_dur)
    if series:
        clips.extend(series[:max_clips])

    # --- 2. sélection gloutonne des autres fenêtres, non chevauchantes.
    #        Avec signal : on écarte les passages faibles (< 35 % du meilleur).
    #        Sans signal : on prend des fenêtres réparties sur toute la vidéo.
    for score, i, j in candidates:
        if len(clips) >= max_clips:
            break
        if has_signal and score < 0.35 * denom:
            break
        if any(k in used for k in range(i, j)):
            continue
        i, j = _trim_dead_edges(segs, i, j)
        i = _snap_to_topic_start(segs, i, segs[j - 1].end, used, max_dur)
        i, j = _ensure_min_length(segs, i, j, min_dur, used)
        if any(k in used for k in range(i, j)):
            continue
        used.update(range(i, j))
        window = segs[i:j]
        clips.append(
            analyzer.ClipSuggestion(
                start=window[0].start,
                end=window[-1].end,
                title=_make_hook(window).capitalize()[:60],
                hook_text=_make_hook(window),
                caption=_make_caption(window),
                viral_score=int(35 + 40 * score / denom) if has_signal else 45,
                reasoning=("Sélection gratuite : pic d'accroche/énergie détecté."
                           if has_signal else
                           "Sélection gratuite : passage réparti (aucun signal fort détecté)."),
            )
        )

    # --- filet de sécurité : toujours produire au moins un clip ---
    if not clips:
        a, b = _trim_dead_edges(segs, 0, len(segs))
        e = a + 1
        while e < b and segs[e - 1].end - segs[a].start < max_dur:
            e += 1
        window = segs[a:e]
        clips.append(
            analyzer.ClipSuggestion(
                start=window[0].start,
                end=window[-1].end,
                title=_make_hook(window).capitalize()[:60] or "Clip",
                hook_text=_make_hook(window),
                caption=_make_caption(window),
                viral_score=40,
                reasoning="Sélection gratuite : clip par défaut sur la vidéo.",
            )
        )

    clips.sort(key=lambda c: c.start)
    return analyzer._sanitize(
        analyzer.ClipPlan(
            video_summary=f"Analyse gratuite (heuristique locale) de « {video_title} » — "
            "pour une sélection plus fine (hooks, cliffhangers), utilise le mode IA.",
            clips=clips,
        ),
        duration,
        min_dur=int(min_dur),
    )


def _try_extend_series(segs: list[Segment], i: int, j: int, used: set[int],
                       min_dur: float, max_dur: float,
                       ) -> list[analyzer.ClipSuggestion] | None:
    """Étend le meilleur passage tant que l'énergie reste haute ; si le résultat
    dépasse la durée max d'un clip, le découpe en Partie 1/2/3."""
    scores = [_segment_score(s) for s in segs]
    mean_window = sum(scores[i:j]) / max(j - i, 1)
    threshold = max(1.0, 0.5 * mean_window)

    def ok(k: int) -> bool:
        return (
            k < len(segs)
            and k not in used
            and segs[k].start - segs[k - 1].end < 3.0
            and segs[k].end - segs[i].start < 3.0 * max_dur
        )

    k = j
    while ok(k):
        if scores[k] >= threshold:
            k += 1
        elif ok(k + 1) and scores[k + 1] >= threshold:
            k += 2  # tolère un creux isolé au milieu du passage fort
        else:
            break

    total_len = segs[k - 1].end - segs[i].start
    if total_len <= max_dur or k - i < 4:
        return None  # tient dans un seul clip : pas besoin de série

    # découpe en parties (chacune >= durée min) aux frontières de segments
    part_target = max(min_dur + 5.0, (min_dur + max_dur) / 2)
    parts: list[tuple[int, int]] = []
    p_start = i
    for idx in range(i, k):
        if segs[idx].end - segs[p_start].start >= part_target or idx == k - 1:
            parts.append((p_start, idx + 1))
            p_start = idx + 1
        if len(parts) == 3:  # max 3 parties
            break
    parts = [p for p in parts if segs[p[1] - 1].end - segs[p[0]].start >= min_dur]
    if len(parts) < 2:
        return None

    used.update(range(i, parts[-1][1]))
    total = len(parts)
    series = []
    hook = _make_hook(segs[parts[0][0]:parts[0][1]])
    for n, (a, b) in enumerate(parts, start=1):
        window = segs[a:b]
        last_sentence = window[-1].text.strip()
        series.append(
            analyzer.ClipSuggestion(
                start=window[0].start,
                end=window[-1].end,
                title=f"{hook.capitalize()[:45]} — partie {n}",
                hook_text=hook if n == 1 else f"PARTIE {n} 🔥",
                caption=(
                    f"Partie {n}/{total} — la suite arrive 👀 #pourtoi #fyp #partie{n}"
                    if n < total
                    else f"Partie {total}/{total} — le final 🎬 #pourtoi #fyp"
                ),
                viral_score=70,
                reasoning="Passage fort étendu, découpé en série (mode gratuit).",
                series_id="serie-1",
                part=n,
                series_total=total,
                cliffhanger=last_sentence if n < total else None,
            )
        )
    return series
