import logging
from app.services.ai_provider import ai_provider

logger = logging.getLogger(__name__)


async def generate_from_text(text: str) -> dict:
    description = f"Text input for social media content creation:\n\n{text}"
    try:
        result = await ai_provider.generate_content(description)
        return _ensure_fields(result)
    except Exception as e:
        logger.error("Content generation from text failed: %s", e)
        raise


async def generate_from_image(image_path: str, original_text: str = "") -> dict:
    from app.services.image_analyzer import analyze_image, analyze_image_full
    from app.services.ocr_service import extract_text_from_image

    context_parts = []

    try:
        full_analysis = analyze_image_full(image_path)
        context_parts.append(
            f"Image analysis (enhanced):\n"
            f"  Scene: {full_analysis['scene']}\n"
            f"  Categories: {', '.join(full_analysis['categories'])}\n"
            f"  Objects: {', '.join(full_analysis['objects'][:5])}\n"
            f"  Colors: {', '.join(full_analysis['dominant_colors'][:3])}\n"
            f"  Description: {full_analysis['blip_description']}\n"
            f"  Brightness: {full_analysis['brightness']:.1f}, Contrast: {full_analysis['contrast']:.1f}"
        )
    except Exception as e:
        logger.warning("Enhanced image analysis failed, falling back: %s", e)
        try:
            image_description = analyze_image(image_path)
            context_parts.append(f"Image analysis: {image_description}")
        except Exception:
            context_parts.append("Image analysis unavailable.")

    try:
        ocr_text = extract_text_from_image(image_path)
        if ocr_text:
            context_parts.append(f"Text in image (OCR): {ocr_text}")
    except Exception as e:
        logger.warning("OCR failed: %s", e)

    if original_text:
        context_parts.append(f"User-provided text: {original_text}")

    context = "\n".join(context_parts)
    try:
        result = await ai_provider.generate_content(context)
        return _ensure_fields(result)
    except Exception as e:
        logger.error("Content generation from image failed: %s", e)
        raise


async def generate_from_document(file_path: str, original_text: str = "") -> dict:
    from app.services.document_extractor import extract_document

    context_parts = []

    try:
        doc_text = extract_document(file_path)
        context_parts.append(f"Document content:\n{doc_text}")
    except Exception as e:
        logger.warning("Document extraction failed: %s", e)
        context_parts.append("Document extraction failed.")

    if original_text:
        context_parts.append(f"User-provided text: {original_text}")

    context = "\n".join(context_parts)
    try:
        result = await ai_provider.generate_content(context)
        return _ensure_fields(result)
    except Exception as e:
        logger.error("Content generation from document failed: %s", e)
        raise


async def generate_from_video(video_path: str, original_text: str = "") -> dict:
    from app.services.video_processor import process_video, analyze_video_full
    from app.services.audio_transcriber import transcribe_audio
    from app.services.image_analyzer import analyze_image

    context_parts = []

    try:
        video_data = process_video(video_path)
        context_parts.append(
            f"Video info: {video_data['duration']:.1f}s, "
            f"{video_data['width']}x{video_data['height']}, "
            f"{video_data['frame_count']} sampled frames, "
            f"FPS: {video_data.get('fps', 'N/A')}"
        )
    except Exception as e:
        logger.error("Video processing failed: %s", e)
        raise

    # Enhanced motion analysis
    try:
        full_video = analyze_video_full(video_path)
        motion = full_video.get("motion", {})
        context_parts.append(
            f"Video analysis (enhanced):\n"
            f"  Motion intensity: {motion.get('intensity', 'unknown')}\n"
            f"  Scene changes: {motion.get('scene_changes', 0)}\n"
            f"  Thumbnail available: {'yes' if full_video.get('thumbnail_path') else 'no'}\n"
            f"  Has audio: {full_video.get('has_audio', 'unknown')}\n"
            f"  Bitrate: {full_video.get('bitrate', 'unknown')}"
        )
    except Exception as e:
        logger.warning("Enhanced video analysis failed: %s", e)

    if video_data.get("audio_path"):
        try:
            transcript = transcribe_audio(video_data["audio_path"])
            context_parts.append(f"Audio transcript:\n{transcript}")
        except Exception as e:
            logger.warning("Audio transcription failed: %s", e)

    frame_descriptions = []
    for i, frame_path in enumerate(video_data.get("frame_paths", [])):
        try:
            desc = analyze_image(frame_path)
            frame_descriptions.append(f"Frame {i + 1}: {desc}")
        except Exception as e:
            logger.warning("Frame %d analysis failed: %s", i, e)

    if frame_descriptions:
        context_parts.append("Frame-by-frame analysis:\n" + "\n".join(frame_descriptions))

    if original_text:
        context_parts.append(f"User-provided text: {original_text}")

    context = "\n".join(context_parts)

    try:
        result = await ai_provider.generate_content(context)
        return _ensure_fields(result)
    except Exception as e:
        logger.error("Content generation from video failed: %s", e)
        raise


async def generate_from_audio(audio_path: str, original_text: str = "") -> dict:
    from app.services.audio_transcriber import transcribe_audio

    context_parts = []

    try:
        transcript = transcribe_audio(audio_path)
        context_parts.append(f"Audio transcript:\n{transcript}")
    except Exception as e:
        logger.error("Audio transcription failed: %s", e)
        raise

    if original_text:
        context_parts.append(f"User-provided text: {original_text}")

    context = "\n".join(context_parts)
    try:
        result = await ai_provider.generate_content(context)
        return _ensure_fields(result)
    except Exception as e:
        logger.error("Content generation from audio failed: %s", e)
        raise


async def regenerate_field(field: str, context: str) -> str:
    prompt = (
        f"Based on this context:\n{context}\n\n"
        f"Generate ONLY the '{field}' field for social media content. "
        f"Return just the text value, no JSON, no labels."
    )
    try:
        return await ai_provider.generate_text(prompt)
    except Exception as e:
        logger.error("Field regeneration failed for %s: %s", field, e)
        raise


async def translate_content(text: str, target_language: str) -> str:
    return await ai_provider.translate(text, target_language)


async def rewrite_content(text: str, tone: str, length: str) -> str:
    return await ai_provider.rewrite(text, tone, length)


def _ensure_fields(data: dict) -> dict:
    defaults = {
        "caption": "",
        "long_caption": "",
        "short_caption": "",
        "funny_caption": "",
        "professional_caption": "",
        "travel_caption": "",
        "business_caption": "",
        "food_caption": "",
        "luxury_caption": "",
        "carousel_text": "",
        "thumbnail_text": "",
        "alt_text": "",
        "hashtags": "",
        "keywords": "",
        "emojis": "",
        "cta": "",
        "hook": "",
        "reel_title": "",
        "seo_tags": "",
        "summary": "",
        "viral_score": 0,
        "viral_score_reason": "",
    }
    for key, default in defaults.items():
        if key not in data or not data[key]:
            data[key] = default
    return data
