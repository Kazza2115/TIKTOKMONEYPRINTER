"""Gestion des jobs : chaque job exécute le pipeline complet dans un thread.
download -> transcribe -> analyze (IA) ou clips manuels -> cut
L'état est gardé en mémoire et persisté en JSON pour survivre à un redémarrage.
"""

import json
import os
import re
import threading
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .pipeline import analyzer, analyzer_free, cutter, downloader, subtitles, transcriber

STEPS = ["download", "transcribe", "analyze", "cut", "done"]


@dataclass
class ClipResult:
    filename: str
    title: str
    hook_text: str
    caption: str
    viral_score: int
    reasoning: str
    start: float
    end: float
    part: int | None = None
    series_total: int | None = None
    series_id: str | None = None
    cliffhanger: str | None = None


@dataclass
class Job:
    id: str
    url: str
    mode: str  # "ai" | "auto_free" | "manual"
    framing: str = "crop"  # "crop" (plein écran zoomable) | "fit" (fond flouté)
    zoom: float = 1.0  # facteur de zoom (0.5–3.0), réglable
    min_duration: int = 0  # 0 = valeur par défaut de config
    max_duration: int = 0
    font: str = "Arial"
    hook_position: str = "top"  # top | middle | bottom (compat)
    hook_lang: str = "anglais"  # langue des hooks/légendes en mode IA
    hook_pos_pct: float = 10.0  # position verticale du hook (% depuis le haut)
    sub_pos_pct: float = 78.0   # position verticale des sous-titres
    hook_size: int = 72
    sub_size: int = 96
    status: str = "pending"  # pending | running | done | error
    step: str = "download"
    progress: float = 0.0
    error: str | None = None
    video_title: str = ""
    video_summary: str = ""
    source_path: str = ""  # chemin de la vidéo téléchargée (pour re-render)
    clips: list = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self):
        return asdict(self)


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def _save(job: Job):
    (config.JOBS_DIR / f"{job.id}.json").write_text(
        json.dumps(job.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_jobs():
    for f in sorted(config.JOBS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            job = Job(**{k: v for k, v in data.items() if k in Job.__dataclass_fields__})
            if job.status == "running":  # interrompu par un redémarrage
                job.status = "error"
                job.error = "Interrompu (redémarrage du serveur). Relance le job."
            _jobs[job.id] = job
        except Exception:
            continue


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def list_jobs() -> list[Job]:
    return sorted(_jobs.values(), key=lambda j: j.created_at, reverse=True)


def parse_manual_clips(text: str) -> list[dict]:
    """Parse le format manuel : une ligne par clip
    `1:23-1:55 | HOOK OPTIONNEL | légende optionnelle`
    Timestamps acceptés : SS, MM:SS ou HH:MM:SS.
    """

    def to_seconds(ts: str) -> float:
        parts = [float(p) for p in ts.strip().split(":")]
        sec = 0.0
        for p in parts:
            sec = sec * 60 + p
        return sec

    clips = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        fields = [f.strip() for f in line.split("|")]
        m = re.match(r"^([\d:.]+)\s*-\s*([\d:.]+)$", fields[0])
        if not m:
            raise ValueError(f"Ligne invalide : « {line} » (attendu : 1:23-1:55 | hook | légende)")
        clips.append(
            {
                "start": to_seconds(m.group(1)),
                "end": to_seconds(m.group(2)),
                "hook_text": fields[1] if len(fields) > 1 else "",
                "caption": fields[2] if len(fields) > 2 else "",
            }
        )
    if not clips:
        raise ValueError("Aucun clip fourni en mode manuel.")
    return clips


def create_job(url: str, mode: str = "ai", manual_clips: list[dict] | None = None,
               language: str | None = None, max_clips: int | None = None,
               framing: str = "fit", min_duration: int = 0,
               max_duration: int = 0, font: str = "Arial",
               hook_position: str = "top", hook_lang: str = "anglais",
               hook_pos_pct: float = 10.0, sub_pos_pct: float = 78.0,
               hook_size: int = 72, sub_size: int = 96,
               zoom: float = 1.0) -> Job:
    job = Job(id=uuid.uuid4().hex[:12], url=url, mode=mode, framing=framing,
              zoom=zoom, min_duration=min_duration, max_duration=max_duration,
              font=font, hook_position=hook_position, hook_lang=hook_lang,
              hook_pos_pct=hook_pos_pct, sub_pos_pct=sub_pos_pct,
              hook_size=hook_size, sub_size=sub_size)
    with _lock:
        _jobs[job.id] = job
    _save(job)

    thread = threading.Thread(
        target=_run, args=(job, manual_clips, language, max_clips), daemon=True
    )
    thread.start()
    return job


def _set(job: Job, **kw):
    for k, v in kw.items():
        setattr(job, k, v)
    _save(job)


def _run(job: Job, manual_clips: list[dict] | None, language: str | None,
         max_clips: int | None):
    try:
        cutter.ensure_ffmpeg()
        _set(job, status="running", step="download", progress=0.0)

        # 1. téléchargement
        src = downloader.download(
            job.url,
            config.DOWNLOADS_DIR,
            progress_cb=lambda p: _set(job, progress=p),
        )
        _set(job, video_title=src.title, source_path=str(src.path),
             step="transcribe", progress=0.0)

        # 2. transcription (mots horodatés — nécessaire pour les sous-titres,
        #    même en mode manuel)
        transcript = transcriber.transcribe(
            src.path, language=language, progress_cb=lambda p: _set(job, progress=p)
        )

        # 3. sélection des clips
        _set(job, step="analyze", progress=0.0)
        if job.mode == "manual":
            suggestions = [
                analyzer.ClipSuggestion(
                    start=c["start"],
                    end=c["end"],
                    title=f"Clip {i + 1}",
                    hook_text=c.get("hook_text", ""),
                    caption=c.get("caption", ""),
                    viral_score=0,
                    reasoning="Clip défini manuellement",
                )
                for i, c in enumerate(manual_clips or [])
            ]
            summary = ""
        else:
            dur_kw = {
                "min_dur": job.min_duration or None,
                "max_dur": job.max_duration or None,
            }
            has_speech = any(s.text.strip() for s in transcript.segments)
            if not has_speech:
                # aucune parole détectée : clip(s) brut(s) sans sous-titres,
                # quel que soit le mode (inutile de dépenser des crédits IA).
                min_d = float(job.min_duration or config.CLIP_MIN_DURATION)
                max_d = float(job.max_duration or config.CLIP_MAX_DURATION)
                min_d = min(min_d, max(src.duration - 2.0, 3.0))
                plan = analyzer_free._no_transcript_plan(
                    src.title, src.duration, min_d, max_d
                )
            elif job.mode == "auto_free":
                plan = analyzer_free.analyze_free(
                    transcript, src.title, src.duration, max_clips=max_clips, **dur_kw
                )
            else:
                plan = analyzer.analyze(
                    transcript, src.title, src.duration, max_clips=max_clips,
                    hook_lang=job.hook_lang, **dur_kw
                )
            suggestions = plan.clips
            summary = plan.video_summary
            if not suggestions:
                # garantie absolue : on ne renvoie JAMAIS « aucun clip ».
                # On retombe sur un ou plusieurs clips bruts couvrant la vidéo.
                min_d = float(job.min_duration or config.CLIP_MIN_DURATION)
                max_d = float(job.max_duration or config.CLIP_MAX_DURATION)
                min_d = min(min_d, max(src.duration - 2.0, 3.0))
                fallback = analyzer_free._no_transcript_plan(
                    src.title, src.duration, min_d, max_d
                )
                suggestions = fallback.clips
                summary = summary or fallback.video_summary
            if not suggestions:
                # ne devrait jamais arriver (vidéo de durée nulle)
                raise RuntimeError(
                    "Vidéo inexploitable (durée nulle ou fichier corrompu). "
                    "Vérifie le lien et réessaie."
                )
        _set(job, video_summary=summary, step="cut", progress=0.0)

        # 4. montage
        clip_dir = config.CLIPS_DIR / job.id
        clip_dir.mkdir(parents=True, exist_ok=True)
        results = []
        for i, c in enumerate(suggestions):
            words = transcript.words_between(c.start, c.end)
            ass_path = subtitles.build_ass(
                words=words,
                clip_start=c.start,
                clip_end=c.end,
                hook_text=c.hook_text,
                part=c.part,
                series_total=c.series_total,
                out_path=clip_dir / f"clip_{i + 1:02d}.ass",
                font=job.font,
                hook_position=job.hook_position,
                hook_pos_pct=job.hook_pos_pct,
                sub_pos_pct=job.sub_pos_pct,
                hook_size=job.hook_size,
                sub_size=job.sub_size,
            )
            filename = f"clip_{i + 1:02d}.mp4"
            cutter.cut_clip(
                src.path, c.start, c.end, ass_path, clip_dir / filename,
                framing=job.framing, zoom=job.zoom,
            )
            results.append(
                asdict(
                    ClipResult(
                        filename=filename,
                        title=c.title,
                        hook_text=c.hook_text,
                        caption=c.caption,
                        viral_score=c.viral_score,
                        reasoning=c.reasoning,
                        start=c.start,
                        end=c.end,
                        part=c.part,
                        series_total=c.series_total,
                        series_id=c.series_id,
                        cliffhanger=c.cliffhanger,
                    )
                )
            )
            _set(job, clips=results, progress=(i + 1) / len(suggestions))

        _set(job, status="done", step="done", progress=1.0)
    except Exception as e:
        traceback.print_exc()
        _set(job, status="error", error=str(e))


def rerender_clip(job_id: str, index: int, zoom: float,
                  framing: str | None = None) -> dict:
    """Réencode UN seul clip avec un nouveau zoom/cadrage, sans re-télécharger
    ni ré-analyser (réutilise le fichier .ass déjà généré). Rapide et gratuit.
    Retourne le clip mis à jour (dict) avec un champ `version` pour forcer le
    rafraîchissement du cache navigateur.
    """
    job = _jobs.get(job_id)
    if not job:
        raise ValueError("Job introuvable.")
    if index < 0 or index >= len(job.clips):
        raise ValueError("Clip introuvable.")
    if not job.source_path or not os.path.isfile(job.source_path):
        raise RuntimeError(
            "Vidéo source introuvable (supprimée ou serveur redémarré). "
            "Relance la génération pour ce clip."
        )

    clip = job.clips[index]
    clip_dir = config.CLIPS_DIR / job.id
    ass_path = clip_dir / f"clip_{index + 1:02d}.ass"
    out_path = clip_dir / clip["filename"]

    fr = framing if framing in ("fit", "crop") else job.framing
    z = cutter._clamp_zoom(zoom)

    cutter.cut_clip(
        Path(job.source_path), clip["start"], clip["end"],
        ass_path if ass_path.exists() else None, out_path,
        framing=fr, zoom=z,
    )

    # mémorise le dernier réglage sur le job (pratique pour les prochains)
    clip["zoom"] = z
    clip["framing"] = fr
    clip["version"] = clip.get("version", 0) + 1
    _set(job, clips=job.clips, zoom=z, framing=fr)
    return clip
