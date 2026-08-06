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

# mots/expressions qui signalent un moment fort (fr + quelques génériques)
HOOK_WORDS = [
    "jamais", "personne", "secret", "vérité", "verite", "fou", "dingue",
    "incroyable", "choqué", "choque", "grave", "abusé", "abuse", "attends",
    "écoute", "ecoute", "regarde", "problème", "probleme", "argent", "euros",
    "histoire", "raconte", "avoue", "franchement", "en vrai", "wesh",
    "truc de ouf", "je te jure", "tu sais pas", "révèle", "revele", "cash",
    "million", "interdit", "caché", "cache", "peur", "pire", "meilleur",
    "première fois", "premiere fois", "dernière fois", "derniere fois",
    "never", "secret", "crazy", "insane", "money", "story", "truth",
]

STOPWORDS = set(
    "le la les un une des de du d l et ou mais donc or ni car que qui quoi "
    "dont où a à au aux ce cette ces cet il elle ils elles on nous vous je tu "
    "me te se ne pas plus moins très tres bien mal avec sans pour par sur sous "
    "dans est sont était etait être etre avoir fait faire dit dire ça ca c'est "
    "cest comme alors aussi tout tous toute toutes rien quelque chose là la-bas "
    "the a an and or but of to in is are was were be have has this that".split()
)

IDEAL_MIN, IDEAL_MAX = 20.0, 50.0


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


def analyze_free(transcript: Transcript, video_title: str, duration: float,
                 max_clips: int | None = None) -> analyzer.ClipPlan:
    max_clips = max_clips or config.MAX_CLIPS
    segs = [s for s in transcript.segments if s.text.strip()]
    if not segs:
        raise RuntimeError("Transcript vide : impossible de sélectionner des clips.")

    # --- construit toutes les fenêtres candidates (20-50 s, bornées aux segments)
    candidates: list[tuple[float, int, int]] = []  # (score, i_start, i_end_exclu)
    for i in range(len(segs)):
        j = i
        while j < len(segs) and segs[j].end - segs[i].start <= IDEAL_MAX:
            j += 1
            window = segs[i:j]
            length = window[-1].end - window[0].start
            if length >= IDEAL_MIN:
                candidates.append((_window_score(window), i, j))
    if not candidates:  # vidéo très courte : prend tout
        candidates = [(1.0, 0, len(segs))]

    candidates.sort(reverse=True, key=lambda c: c[0])
    best_score = candidates[0][0] or 1.0
    used: set[int] = set()
    clips: list[analyzer.ClipSuggestion] = []

    # --- 1. le meilleur passage devient une série Partie 1/2 s'il s'étire
    _, bi, bj = candidates[0]
    series = _try_extend_series(segs, bi, bj, used)
    if series:
        clips.extend(series[:max_clips])

    # --- 2. sélection gloutonne des autres fenêtres, non chevauchantes,
    #        en écartant les passages sans réel intérêt (< 35 % du meilleur score)
    for score, i, j in candidates:
        if len(clips) >= max_clips:
            break
        if score < 0.35 * best_score:
            break
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
                viral_score=int(35 + 40 * score / best_score),
                reasoning="Sélection gratuite : pic d'accroche/énergie détecté dans ce passage.",
            )
        )

    if not clips:
        raise RuntimeError(
            "Aucun passage assez fort détecté par l'analyse gratuite. "
            "Essaie le mode IA ou le mode manuel."
        )

    clips.sort(key=lambda c: c.start)
    return analyzer._sanitize(
        analyzer.ClipPlan(
            video_summary=f"Analyse gratuite (heuristique locale) de « {video_title} » — "
            "pour une sélection plus fine (hooks, cliffhangers), utilise le mode IA.",
            clips=clips,
        ),
        duration,
    )


def _try_extend_series(segs: list[Segment], i: int, j: int,
                       used: set[int]) -> list[analyzer.ClipSuggestion] | None:
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
            and segs[k].end - segs[i].start < 150.0
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
    if total_len <= config.CLIP_MAX_DURATION or k - i < 4:
        return None  # tient dans un seul clip : pas besoin de série

    # découpe en parties de ~45-55 s aux frontières de segments
    parts: list[tuple[int, int]] = []
    p_start = i
    for idx in range(i, k):
        if segs[idx].end - segs[p_start].start >= 45 or idx == k - 1:
            parts.append((p_start, idx + 1))
            p_start = idx + 1
        if len(parts) == 3:  # max 3 parties
            break
    parts = [p for p in parts if segs[p[1] - 1].end - segs[p[0]].start >= config.CLIP_MIN_DURATION]
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
