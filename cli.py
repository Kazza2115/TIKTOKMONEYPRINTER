#!/usr/bin/env python3
"""Génération de clips en ligne de commande — utilisé par GitHub Actions,
utilisable aussi en local : python cli.py "https://..." --mode auto_free
"""

import argparse
import sys

from app import config
from app.jobs import parse_manual_clips
from app.pipeline import analyzer, analyzer_free, cutter, downloader, subtitles, transcriber


def main() -> int:
    p = argparse.ArgumentParser(description="Génère des clips TikTok depuis une URL vidéo")
    p.add_argument("url", help="URL de la vidéo (YouTube, Twitch, Vimeo...)")
    p.add_argument("--mode", default="auto_free", choices=["auto_free", "ai", "manual"])
    p.add_argument("--framing", default="fit", choices=["fit", "crop"])
    p.add_argument("--min-duration", type=int, default=60)
    p.add_argument("--max-duration", type=int, default=180)
    p.add_argument("--max-clips", type=int, default=5)
    p.add_argument("--language", default="")
    p.add_argument("--manual-clips", default="",
                   help="Mode manuel : '1:23-1:55 | HOOK | légende' — plusieurs clips séparés par ;;")
    p.add_argument("--summary", default="", help="Fichier markdown de résumé (pour GitHub Actions)")
    a = p.parse_args()

    try:
        return _run(a)
    except Exception as e:
        msg = str(e)
        print(f"❌ ERREUR : {msg}", flush=True)
        if a.summary:
            with open(a.summary, "w", encoding="utf-8") as f:
                f.write(f"# ❌ La génération a échoué\n\n```\n{msg}\n```\n")
        return 1


def _run(a) -> int:
    manual = None
    if a.mode == "manual":
        manual = parse_manual_clips(a.manual_clips.replace(";;", "\n"))

    cutter.ensure_ffmpeg()

    print(f"📥 Téléchargement : {a.url}", flush=True)
    src = downloader.download(a.url, config.DOWNLOADS_DIR)
    print(f"   → « {src.title} » ({src.duration:.0f}s)", flush=True)

    print("🎙️ Transcription (Whisper)...", flush=True)
    transcript = transcriber.transcribe(src.path, language=a.language or None)
    print(f"   → {len(transcript.segments)} segments ({transcript.language})", flush=True)

    print(f"🧠 Sélection des clips (mode {a.mode})...", flush=True)
    if a.mode == "manual":
        suggestions = [
            analyzer.ClipSuggestion(
                start=c["start"], end=c["end"], title=f"Clip {i + 1}",
                hook_text=c.get("hook_text", ""), caption=c.get("caption", ""),
                viral_score=0, reasoning="Clip défini manuellement",
            )
            for i, c in enumerate(manual or [])
        ]
        summary_text = ""
    else:
        fn = analyzer_free.analyze_free if a.mode == "auto_free" else analyzer.analyze
        plan = fn(transcript, src.title, src.duration, max_clips=a.max_clips,
                  min_dur=a.min_duration, max_dur=a.max_duration)
        suggestions = plan.clips
        summary_text = plan.video_summary
        if not suggestions:
            print("❌ Aucun moment à fort potentiel trouvé.", flush=True)
            return 1

    out_dir = config.CLIPS_DIR / "cli"
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# 🎬 Clips générés — {src.title}", ""]
    if summary_text:
        lines += [f"> {summary_text}", ""]

    for i, c in enumerate(suggestions):
        words = transcript.words_between(c.start, c.end)
        ass_path = subtitles.build_ass(
            words=words, clip_start=c.start, clip_end=c.end,
            hook_text=c.hook_text, part=c.part, series_total=c.series_total,
            out_path=out_dir / f"clip_{i + 1:02d}.ass",
        )
        filename = f"clip_{i + 1:02d}.mp4"
        print(f"🎬 Montage {filename} ({c.start:.0f}s → {c.end:.0f}s)...", flush=True)
        cutter.cut_clip(src.path, c.start, c.end, ass_path, out_dir / filename,
                        framing=a.framing)

        part = f" — PARTIE {c.part}/{c.series_total}" if c.part and (c.series_total or 0) > 1 else ""
        score = f" · 🔥 {c.viral_score}/100" if c.viral_score else ""
        lines += [
            f"## {filename}{part}",
            f"**{c.title}**{score}",
            f"- ⏱️ {c.start:.0f}s → {c.end:.0f}s ({c.end - c.start:.0f}s)",
            f"- 🪝 Hook : {c.hook_text}" if c.hook_text else "",
            f"- 📝 Légende : `{c.caption}`" if c.caption else "",
            f"- 💡 {c.reasoning}" if c.reasoning else "",
            "",
        ]

    print(f"✅ {len(suggestions)} clip(s) dans {out_dir}", flush=True)

    if a.summary:
        with open(a.summary, "w", encoding="utf-8") as f:
            f.write("\n".join(l for l in lines if l is not None))

    return 0


if __name__ == "__main__":
    sys.exit(main())
