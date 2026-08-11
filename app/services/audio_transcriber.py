import logging

logger = logging.getLogger(__name__)

_whisper_model = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading Whisper model (base)...")
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("Whisper model loaded.")
    return _whisper_model


def transcribe_audio(audio_path: str) -> str:
    try:
        model = _get_whisper()
        segments, info = model.transcribe(audio_path, beam_size=5)
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())
        full_text = " ".join(text_parts)
        if not full_text.strip():
            return "[No speech detected in audio]"
        return full_text
    except Exception as e:
        logger.error("Whisper transcription failed: %s", e)
        return f"[Transcription error: {e}]"


def get_audio_info(audio_path: str) -> dict:
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(audio_path)
        return {
            "duration_ms": len(audio),
            "duration_sec": len(audio) / 1000,
            "channels": audio.channels,
            "sample_rate": audio.frame_rate,
        }
    except Exception:
        return {"duration_sec": 0}
