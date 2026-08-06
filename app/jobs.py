"""Gestion des jobs : chaque job exécute le pipeline complet dans un thread.
download -> transcribe -> analyze (IA) ou clips manuels -> cut
L'état est gardé en mémoire et persisté en JSON pour survivre à un redémarrage.
"""

import json
import re
import threading
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from . import config
from .pipeline import analyzer, cutter, downloader, subtitles, transcriber

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
    mode: str  # "ai" | "manual"
    status: str = "pending"  # pending | running | done | error
    step: str = "download"
    progress: float = 0.0
    error: str | None = None
    video_title: str = ""
    video_summary: str = ""
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
               language: str | None = None, max_clips: int | None = None) -> Job:
    job = Job(id=uuid.uuid4().hex[:12], url=url, mode=mode)
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
        _set(job, video_title=src.title, step="transcribe", progress=0.0)

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
            plan = analyzer.analyze(
                transcript, src.title, src.duration, max_clips=max_clips
            )
            suggestions = plan.clips
            summary = plan.video_summary
            if not suggestions:
                raise RuntimeError(
                    "L'IA n'a trouvé aucun moment à fort potentiel dans cette vidéo."
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
            )
            filename = f"clip_{i + 1:02d}.mp4"
            cutter.cut_clip(src.path, c.start, c.end, ass_path, clip_dir / filename)
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
