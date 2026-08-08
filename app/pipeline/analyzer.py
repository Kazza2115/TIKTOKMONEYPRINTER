"""Analyse virale du transcript par Claude : sélection des meilleurs moments,
codes TikTok (hook, tension, cliffhanger) et découpage en séries Partie 1/2/...
"""

import os
from typing import Optional

from pydantic import BaseModel

from .. import config
from .transcriber import Transcript

SYSTEM_PROMPT = """Tu es un stratège de contenu TikTok de haut niveau. Tu analyses des transcripts
de vidéos longues (podcasts, interviews, streams, freestyles, sessions studio) pour en extraire
les clips qui performent le mieux en format court vertical.

Tu appliques les codes actuels des vidéos virales :

1. INTÉRÊT RÉEL — chaque clip doit APPORTER quelque chose au spectateur : une info, une
   découverte, une histoire complète, une émotion forte. Un passage énergique mais creux ne fait
   pas un clip. Test décisif : quelqu'un qui n'a pas vu la vidéo doit comprendre le clip et y
   trouver son compte du début à la fin.
2. DÉBUT AU BON ENDROIT — le clip commence là où le SUJET démarre : la phrase qui présente le
   lieu, la personne, l'objet ou l'enjeu (ex : « ici c'est la ferme de X, il produit... »).
   Jamais au milieu d'une action incompréhensible sans contexte, et jamais non plus sur du
   blabla d'intro sans rapport (salutations, transitions). La présentation du sujet EST souvent
   le meilleur hook.
3. CURIOSITY GAP — le spectateur doit vouloir connaître la suite (promesse, secret, révélation).
4. ÉMOTION — rire, choc, indignation, inspiration, tension. Un clip sans émotion ne performe pas.
5. RÉTENTION — pas de temps mort. Si un passage fort contient une longueur au milieu, préfère un
   clip plus court et dense.
6. PAYOFF OU BOUCLE — soit le clip se termine sur une chute satisfaisante, soit il donne envie de
   le revoir / de commenter. Ne coupe jamais avant la fin d'une explication entamée (hors
   cliffhanger volontaire de série).

SÉRIES MULTI-PARTIES (Partie 1 / Partie 2 / ...) :
- Quand un moment fort dure plus de {max_dur} secondes et mérite d'être gardé en entier
  (histoire, débat, tuto, storytime), découpe-le en plusieurs clips consécutifs d'une même série.
- Chaque partie sauf la dernière doit se terminer sur un CLIFFHANGER : coupe en plein milieu de la
  tension, juste AVANT la révélation ou la chute — jamais après. C'est ce qui force le spectateur
  à aller chercher la partie suivante.
- Toutes les parties d'une série partagent le même series_id (ex: "storytime-prison"), un numéro
  part (1, 2, ...) et le même series_total. La partie 1 porte le hook le plus fort de la série.
- Renseigne cliffhanger avec la phrase exacte du transcript sur laquelle couper (fin de la partie).

CONTRAINTES TECHNIQUES :
- Durée d'un clip : entre {min_dur} et {max_dur} secondes — c'est une contrainte DURE
  (en dessous de {min_dur}s le clip est inutilisable : monétisation). Si le meilleur moment est
  plus court que {min_dur}s, étends le clip au passage qui l'entoure (contexte avant, réaction
  après) pour atteindre la durée minimale en restant cohérent.
- Si la vidéo entière tient dans la durée max et qu'elle est bonne, un clip couvrant presque
  toute la vidéo est parfaitement valide.
- Les timestamps start/end doivent correspondre à des débuts/fins de phrases du transcript
  (utilise les bornes [start-end] fournies). Ne coupe jamais un mot en deux.
- hook_text : le texte incrusté sur le clip pendant les premières secondes. Court (max 8 mots),
  percutant, en MAJUSCULES ou style choc. RÉDIGE-LE EN {hook_lang}.
- caption : la description TikTok — 1 phrase qui pousse au commentaire + 3 à 5 hashtags pertinents
  (mélange gros hashtags et hashtags de niche). RÉDIGE-LA EN {hook_lang}.
- viral_score : ton estimation 0-100 du potentiel du clip. Sois exigeant : un 80+ doit être rare.
- Classe les clips du plus fort au plus faible potentiel, mais garde les parties d'une même série
  consécutives et dans l'ordre.
- Propose au maximum {max_clips} clips (une série de N parties compte pour N clips).
- Si la vidéo ne contient aucun moment à vrai potentiel, retourne moins de clips plutôt que de
  forcer des clips faibles."""


class ClipSuggestion(BaseModel):
    start: float
    end: float
    title: str
    hook_text: str
    caption: str
    viral_score: int
    reasoning: str
    series_id: Optional[str] = None
    part: Optional[int] = None
    series_total: Optional[int] = None
    cliffhanger: Optional[str] = None


class ClipPlan(BaseModel):
    video_summary: str
    clips: list[ClipSuggestion]


def analyze(transcript: Transcript, video_title: str, duration: float,
            max_clips: int | None = None, min_dur: int | None = None,
            max_dur: int | None = None, hook_lang: str = "anglais") -> ClipPlan:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY manquante. Copie .env.example vers .env et renseigne ta clé, "
            "ou utilise le mode manuel."
        )

    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise RuntimeError("Le SDK anthropic n'est pas installé. Lance : pip install anthropic") from e

    max_clips = max_clips or config.MAX_CLIPS
    client = Anthropic()

    min_dur = min_dur or config.CLIP_MIN_DURATION
    max_dur = max_dur or config.CLIP_MAX_DURATION

    system = SYSTEM_PROMPT.format(
        min_dur=min_dur,
        max_dur=max_dur,
        max_clips=max_clips,
        hook_lang=hook_lang,
    )

    user_content = (
        f"Titre de la vidéo : {video_title}\n"
        f"Durée totale : {duration:.0f} secondes\n"
        f"Langue détectée : {transcript.language}\n\n"
        f"Transcript (format [début-fin] texte, en secondes) :\n\n"
        f"{transcript.as_prompt_text()}"
    )

    import anthropic

    try:
        response = client.messages.parse(
            model=config.CLAUDE_MODEL,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user_content}],
            output_format=ClipPlan,
        )
    except anthropic.AuthenticationError as e:
        raise RuntimeError(
            "Clé API invalide ou révoquée. Vérifie ANTHROPIC_API_KEY "
            "(https://platform.claude.com/settings/keys)."
        ) from e
    except anthropic.RateLimitError as e:
        raise RuntimeError(
            "Limite de débit API atteinte. Attends une minute et relance."
        ) from e
    except anthropic.BadRequestError as e:
        msg = str(e)
        if "credit balance" in msg.lower() or "billing" in msg.lower():
            raise RuntimeError(
                "Ton compte API n'a pas de crédit. L'abonnement Claude.ai (Pro/Max) ne "
                "couvre pas l'API : achète du crédit (5 $ suffisent) sur "
                "https://platform.claude.com/settings/billing puis relance. "
                "En attendant, le mode manuel fonctionne sans API."
            ) from e
        raise RuntimeError(f"Requête refusée par l'API : {msg}") from e

    if response.stop_reason == "refusal":
        raise RuntimeError("L'analyse a été refusée par le modèle. Réessaie ou passe en mode manuel.")

    plan = response.parsed_output
    if plan is None:
        raise RuntimeError("Réponse du modèle invalide (parsing échoué). Réessaie.")

    return _sanitize(plan, duration, min_dur=min_dur)


def _sanitize(plan: ClipPlan, duration: float, min_dur: int = 0) -> ClipPlan:
    """Borne les timestamps, filtre les clips invalides, renumérote les séries."""
    # si la vidéo est plus courte que le min demandé, on prend ce qu'on peut
    effective_min = max(3.0, min(float(min_dur), duration - 2.0))
    valid: list[ClipSuggestion] = []
    for c in plan.clips:
        c.start = max(0.0, min(c.start, duration))
        c.end = max(0.0, min(c.end, duration))
        if c.end - c.start < effective_min - 3.0:
            continue
        c.viral_score = max(0, min(100, c.viral_score))
        valid.append(c)

    # cohérence des séries : recompte series_total à partir des parties réellement présentes
    by_series: dict[str, list[ClipSuggestion]] = {}
    for c in valid:
        if c.series_id:
            by_series.setdefault(c.series_id, []).append(c)
    for clips in by_series.values():
        clips.sort(key=lambda c: (c.part or 0, c.start))
        for i, c in enumerate(clips, start=1):
            c.part = i
            c.series_total = len(clips)

    plan.clips = valid
    return plan
