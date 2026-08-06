"""Transcription locale avec faster-whisper, avec timestamps par mot."""

from dataclasses import dataclass, field
from pathlib import Path

from .. import config


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)


@dataclass
class Transcript:
    language: str
    segments: list[Segment]

    def as_prompt_text(self) -> str:
        """Format compact pour l'analyse par l'IA : [start-end] texte."""
        lines = []
        for s in self.segments:
            lines.append(f"[{s.start:.1f}-{s.end:.1f}] {s.text.strip()}")
        return "\n".join(lines)

    def words_between(self, start: float, end: float) -> list[Word]:
        out = []
        for s in self.segments:
            for w in s.words:
                if w.end > start and w.start < end:
                    out.append(w)
        return out


_model_cache = {}


def _get_model():
    key = (config.WHISPER_MODEL, config.WHISPER_DEVICE)
    if key not in _model_cache:
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise RuntimeError(
                "faster-whisper n'est pas installé. Lance : pip install faster-whisper"
            ) from e
        compute = "float16" if config.WHISPER_DEVICE == "cuda" else "int8"
        _model_cache[key] = WhisperModel(
            config.WHISPER_MODEL, device=config.WHISPER_DEVICE, compute_type=compute
        )
    return _model_cache[key]


def transcribe(video_path: Path, language: str | None = None, progress_cb=None) -> Transcript:
    model = _get_model()
    segments_iter, info = model.transcribe(
        str(video_path),
        language=language,
        word_timestamps=True,
        vad_filter=True,
    )

    total = info.duration or 1.0
    segments: list[Segment] = []
    for seg in segments_iter:
        words = [
            Word(start=w.start, end=w.end, text=w.word.strip())
            for w in (seg.words or [])
            if w.word.strip()
        ]
        segments.append(Segment(start=seg.start, end=seg.end, text=seg.text, words=words))
        if progress_cb:
            progress_cb(min(seg.end / total, 1.0))

    return Transcript(language=info.language, segments=segments)
