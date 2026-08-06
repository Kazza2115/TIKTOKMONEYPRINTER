from flask import Blueprint, abort, jsonify, render_template, request, send_from_directory

from . import config, jobs

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

    job = jobs.create_job(
        url, mode=mode, manual_clips=manual_clips, language=language, max_clips=max_clips
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


@bp.get("/clips/<job_id>/<path:filename>")
def serve_clip(job_id, filename):
    return send_from_directory(config.CLIPS_DIR / job_id, filename)
