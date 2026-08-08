from flask import Blueprint, abort, jsonify, render_template, request, send_from_directory

from . import config, jobs
from .pipeline import youtube_search

bp = Blueprint("main", __name__)

jobs.load_jobs()


@bp.get("/")
def index():
    return render_template("index.html", jobs=jobs.list_jobs())


@bp.get("/job/<job_id>")
def job_page(job_id):
    job = jobs.get_job(job_id)
    if not job:
        abort(404)
    return render_template("job.html", job=job)


@bp.post("/api/jobs")
def api_create_job():
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "URL manquante"}), 400

    mode = data.get("mode", "ai")
    language = (data.get("language") or "").strip() or None
    max_clips = data.get("max_clips") or None
    if max_clips:
        max_clips = max(1, min(10, int(max_clips)))

    manual_clips = None
    if mode == "manual":
        try:
            manual_clips = jobs.parse_manual_clips(data.get("manual_clips") or "")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    framing = data.get("framing") or "fit"
    if framing not in ("fit", "crop"):
        framing = "fit"

    def _dur(key, default):
        try:
            v = int(data.get(key) or 0)
        except (TypeError, ValueError):
            return default
        return max(5, min(600, v)) if v else default

    min_duration = _dur("min_duration", 0)
    max_duration = _dur("max_duration", 0)
    if min_duration and max_duration and max_duration <= min_duration:
        return jsonify({"error": "La durée max doit être supérieure à la durée min."}), 400

    from .pipeline.subtitles import FONTS, HOOK_POSITIONS

    font = data.get("font") or "Arial"
    if font not in FONTS:
        font = "Arial"
    hook_position = data.get("hook_position") or "top"
    if hook_position not in HOOK_POSITIONS:
        hook_position = "top"
    hook_lang = "français" if (data.get("hook_lang") == "fr") else "anglais"

    def _num(key, default, lo, hi):
        try:
            v = float(data.get(key))
        except (TypeError, ValueError):
            return default
        return max(lo, min(v, hi))

    hook_pos_pct = _num("hook_pos_pct", 10.0, 0, 95)
    sub_pos_pct = _num("sub_pos_pct", 78.0, 0, 95)
    hook_size = int(_num("hook_size", 72, 30, 130))
    sub_size = int(_num("sub_size", 96, 40, 160))

    job = jobs.create_job(
        url, mode=mode, manual_clips=manual_clips, language=language,
        max_clips=max_clips, framing=framing,
        min_duration=min_duration, max_duration=max_duration,
        font=font, hook_position=hook_position, hook_lang=hook_lang,
        hook_pos_pct=hook_pos_pct, sub_pos_pct=sub_pos_pct,
        hook_size=hook_size, sub_size=sub_size,
    )
    return jsonify(job.to_dict()), 201


@bp.get("/api/jobs")
def api_list_jobs():
    return jsonify([j.to_dict() for j in jobs.list_jobs()])


@bp.get("/api/jobs/<job_id>")
def api_get_job(job_id):
    job = jobs.get_job(job_id)
    if not job:
        abort(404)
    return jsonify(job.to_dict())


@bp.post("/api/search")
def api_search():
    data = request.get_json(force=True)
    query = (data.get("query") or "").strip()
    duration = data.get("duration") or "long"
    try:
        recency = int(data.get("recency_days") or 180)
    except (TypeError, ValueError):
        recency = 180
    try:
        results = youtube_search.search(query, duration=duration, recency_days=recency)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Recherche échouée : {e}"}), 502
    return jsonify({"results": results})


@bp.get("/clips/<job_id>/<path:filename>")
def serve_clip(job_id, filename):
    return send_from_directory(config.CLIPS_DIR / job_id, filename)
