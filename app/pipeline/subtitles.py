"""Génération de sous-titres .ass style TikTok :
- groupes de 2-4 mots, gros, centrés, mot actif surligné en jaune (karaoké)
- hook incrusté en haut pendant les premières secondes
- badge "PARTIE X/N" pour les séries
Tous les timestamps sont relatifs au début du clip.
"""

from pathlib import Path

from .transcriber import Word

HOOK_DURATION = 3.5  # secondes d'affichage du hook
WORDS_PER_GROUP = 3

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Arial,96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,9,3,2,60,60,660,1
Style: Hook,Arial,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,3,10,0,8,70,70,180,1
Style: Badge,Arial,52,&H0000E5FF,&H0000E5FF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,3,8,0,8,70,70,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

HIGHLIGHT = r"{\c&H00E5FF&}"  # jaune-or (BGR)
RESET = r"{\c&HFFFFFF&}"


def _ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _escape(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def build_ass(
    words: list[Word],
    clip_start: float,
    clip_end: float,
    hook_text: str | None,
    part: int | None,
    series_total: int | None,
    out_path: Path,
) -> Path:
    """Écrit le fichier .ass du clip (timestamps relatifs au clip)."""
    clip_len = clip_end - clip_start
    events: list[str] = []

    # --- hook en haut ---
    if hook_text:
        events.append(
            f"Dialogue: 1,{_ts(0)},{_ts(min(HOOK_DURATION, clip_len))},Hook,,0,0,0,,"
            f"{_escape(hook_text.upper())}"
        )

    # --- badge partie X/N ---
    if part and series_total and series_total > 1:
        events.append(
            f"Dialogue: 1,{_ts(0)},{_ts(clip_len)},Badge,,0,0,0,,"
            f"PARTIE {part}/{series_total}"
        )

    # --- sous-titres karaoké : groupes de mots, mot actif en jaune ---
    rel_words = [
        Word(start=w.start - clip_start, end=w.end - clip_start, text=w.text)
        for w in words
        if w.end > clip_start and w.start < clip_end
    ]
    groups = [
        rel_words[i : i + WORDS_PER_GROUP]
        for i in range(0, len(rel_words), WORDS_PER_GROUP)
    ]

    for group in groups:
        for idx, active in enumerate(group):
            start = max(0.0, active.start)
            # le dernier mot du groupe reste affiché jusqu'à la fin du mot
            end = group[idx + 1].start if idx + 1 < len(group) else active.end
            end = min(max(end, start + 0.05), clip_len)
            if end <= start:
                continue
            parts = []
            for j, w in enumerate(group):
                txt = _escape(w.text).upper()
                parts.append(f"{HIGHLIGHT}{txt}{RESET}" if j == idx else txt)
            events.append(
                f"Dialogue: 0,{_ts(start)},{_ts(end)},Sub,,0,0,0,,{' '.join(parts)}"
            )

    out_path.write_text(ASS_HEADER + "\n".join(events) + "\n", encoding="utf-8")
    return out_path
