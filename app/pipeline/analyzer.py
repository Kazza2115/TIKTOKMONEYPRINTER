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

1. HOOK IMMÉDIAT — les 1 à 3 premières secondes doivent accrocher : une phrase choc, une question,
   une affirmation contre-intuitive, un début d'histoire. Jamais de mise en contexte lente.
   Commence le clip PILE au moment fort, quitte à couper le début d'une phrase d'intro.
2. CURIOSITY GAP — le spectateur doit vouloir connaître la suite (promesse, secret, révélation).
3. ÉMOTION — rire, choc, indignation, inspiration, tension. Un clip sans émotion ne performe pas.
4. RÉTENTION — pas de temps mort. Si un passage fort contient une longueur au milieu, préfère un
   clip plus court et dense.
5. PAYOFF OU BOUCLE — soit le clip se termine sur une chute satisfaisante, soit il donne envie de
   le revoir / de commenter.

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
- Durée d'un clip : entre {min_dur} et {max_dur} secondes. Idéal : 20 à 45 secondes.
- Les timestamps start/end doivent correspondre à des débuts/fins de phrases du transcript
  (utilise les bornes [start-end] fournies). Ne coupe jamais un mot en deux.
- hook_text : le texte incrusté en haut du clip pendant les premières secondes. Court (max 8 mots),
  percutant, en MAJUSCULES ou style choc. En français sauf si la vidéo est dans une autre langue.
- caption : la description TikTok — 1 phrase qui pousse au commentaire + 3 à 5 hashtags pertinents
  (mélange gros hashtags et hashtags de niche).
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
            max_clips: int | None = None) -> ClipPlan:
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

    system = SYSTEM_PROMPT.format(
        min_dur=config.CLIP_MIN_DURATION,
        max_dur=config.CLIP_MAX_DURATION,
        max_clips=max_clips,
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

    return _sanitize(plan, duration)


def _sanitize(plan: ClipPlan, duration: float) -> ClipPlan:
    """Borne les timestamps, filtre les clips invalides, renumérote les séries."""
    valid: list[ClipSuggestion] = []
    for c in plan.clips:
        c.start = max(0.0, min(c.start, duration))
        c.end = max(0.0, min(c.end, duration))
        if c.end - c.start < 3:
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
