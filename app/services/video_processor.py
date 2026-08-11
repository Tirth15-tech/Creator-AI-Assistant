import os
import subprocess
import logging
import tempfile
import json
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_VIDEO_DURATION_SEC = 120
MAX_FRAMES = 8


def _get_ffmpeg_path() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def get_video_info(video_path: str) -> dict:
    """Extract video metadata: duration, resolution, codec, FPS, bitrate, has_audio."""
    ffmpeg = _get_ffmpeg_path()
    try:
        cmd = [ffmpeg, "-i", video_path, "-f", "null", "-"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        stderr = result.stderr
        info = {
            "duration": 0, "width": 0, "height": 0,
            "codec": "unknown", "fps": 0, "bitrate": 0, "has_audio": False,
        }

        for line in stderr.split("\n"):
            line = line.strip()
            if "Duration:" in line:
                parts = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = parts.split(":")
                info["duration"] = float(h) * 3600 + float(m) * 60 + float(s)
            elif "Video:" in line:
                parts = line.split("Video:")[1]
                tokens = [t.strip() for t in parts.split(",")]
                info["codec"] = tokens[0] if tokens else "unknown"
                for t in tokens:
                    if "x" in t and any(c.isdigit() for c in t):
                        dims = t.split("x")
                        try:
                            info["width"] = int(dims[0].strip().split()[-1])
                            info["height"] = int(dims[1].strip().split()[0])
                        except (ValueError, IndexError):
                            pass
                    if "fps" in t.lower():
                        try:
                            info["fps"] = float("".join(c for c in t if c.isdigit() or c == "."))
                        except ValueError:
                            pass
                    if "kb/s" in t.lower() or "Mb/s" in t.lower():
                        try:
                            info["bitrate"] = float("".join(c for c in t if c.isdigit() or c == "."))
                        except ValueError:
                            pass
            elif "Audio:" in line:
                info["has_audio"] = True

        return info
    except Exception as e:
        logger.error("Failed to get video info: %s", e)
        return {"duration": 0, "width": 0, "height": 0, "codec": "unknown", "fps": 0, "bitrate": 0, "has_audio": False}


def validate_video(video_path: str) -> str | None:
    info = get_video_info(video_path)
    if info["duration"] > MAX_VIDEO_DURATION_SEC:
        return f"Video too long: {info['duration']:.0f}s. Maximum is {MAX_VIDEO_DURATION_SEC}s (2 minutes)."
    if info["duration"] == 0:
        return "Could not determine video duration. File may be corrupt."
    return None


def extract_audio(video_path: str, output_dir: str) -> str | None:
    ffmpeg = _get_ffmpeg_path()
    audio_path = os.path.join(output_dir, "audio.wav")
    try:
        cmd = [
            ffmpeg, "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            "-y", audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error("FFmpeg audio extraction failed: %s", result.stderr[:500])
            return None
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 100:
            return audio_path
        return None
    except Exception as e:
        logger.error("Audio extraction failed: %s", e)
        return None


def extract_frames(video_path: str, output_dir: str, max_frames: int = MAX_FRAMES) -> list[str]:
    ffmpeg = _get_ffmpeg_path()
    info = get_video_info(video_path)
    duration = info["duration"]
    if duration <= 0:
        return []

    frame_paths = []
    interval = max(duration / (max_frames + 1), 0.5)
    for i in range(max_frames):
        timestamp = interval * (i + 1)
        if timestamp >= duration:
            break
        frame_path = os.path.join(output_dir, f"frame_{i:03d}.jpg")
        try:
            cmd = [
                ffmpeg, "-i", video_path,
                "-ss", str(timestamp),
                "-vframes", "1",
                "-q:v", "2",
                "-y", frame_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and os.path.exists(frame_path):
                frame_paths.append(frame_path)
        except Exception as e:
            logger.warning("Frame extraction at %.1fs failed: %s", timestamp, e)

    return frame_paths


# ─────────────────────────────────────────────
# Phase 2A: Video Thumbnail Generation
# ─────────────────────────────────────────────

def generate_thumbnail(video_path: str, output_dir: str, timestamp: float = 1.0) -> str | None:
    """Generate a thumbnail image from a video at the given timestamp."""
    ffmpeg = _get_ffmpeg_path()
    thumb_path = os.path.join(output_dir, "thumbnail.jpg")
    try:
        cmd = [
            ffmpeg, "-i", video_path,
            "-ss", str(timestamp),
            "-vframes", "1",
            "-q:v", "2",
            "-y", thumb_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and os.path.exists(thumb_path):
            return thumb_path
        return None
    except Exception as e:
        logger.warning("Thumbnail generation failed: %s", e)
        return None


# ─────────────────────────────────────────────
# Phase 2A: Motion Analysis via OpenCV
# ─────────────────────────────────────────────

def analyze_motion(video_path: str, sample_frames: int = 5) -> dict:
    """Analyze video motion level using frame differencing.

    Returns:
        {
            "motion_level": "low" | "medium" | "high",
            "motion_score": float (0-100),
            "scene_changes": int,
            "description": str,
        }
    """
    try:
        import cv2
        import numpy as np

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"motion_level": "unknown", "motion_score": 0, "scene_changes": 0, "description": "Cannot open video"}

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        if total_frames < sample_frames * 2:
            cap.release()
            return {"motion_level": "low", "motion_score": 0, "scene_changes": 0, "description": "Video too short for motion analysis"}

        interval = total_frames // (sample_frames + 1)
        prev_gray = None
        motion_scores = []
        scene_changes = 0

        for i in range(1, sample_frames + 1):
            frame_num = interval * i
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            if not ret:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
                motion_score = (np.sum(thresh) / 255) / thresh.size * 100
                motion_scores.append(motion_score)

                if motion_score > 40:
                    scene_changes += 1

            prev_gray = gray

        cap.release()

        avg_motion = sum(motion_scores) / len(motion_scores) if motion_scores else 0

        if avg_motion < 5:
            level = "low"
            desc = "Static or minimal motion. Great for product shots and portraits."
        elif avg_motion < 20:
            level = "medium"
            desc = "Moderate motion. Good for lifestyle and casual content."
        else:
            level = "high"
            desc = "High motion. Great for action shots, reels, and dynamic content."

        return {
            "motion_level": level,
            "motion_score": round(avg_motion, 2),
            "scene_changes": scene_changes,
            "description": desc,
        }
    except Exception as e:
        logger.error("Motion analysis failed: %s", e)
        return {"motion_level": "unknown", "motion_score": 0, "scene_changes": 0, "description": f"Motion analysis error: {e}"}


# ─────────────────────────────────────────────
# Phase 2A: Full Video Analysis Pipeline
# ─────────────────────────────────────────────

def analyze_video_full(video_path: str) -> dict:
    """Run full video analysis and return structured data for content generation.

    Returns:
        {
            "info": {...},
            "motion": {...},
            "thumbnail_path": str | None,
            "description": str,
        }
    """
    output_dir = tempfile.mkdtemp(prefix="contentai_video_analysis_")

    info = get_video_info(video_path)
    motion = analyze_motion(video_path)
    thumb_path = generate_thumbnail(video_path, output_dir)

    parts = []
    parts.append(f"Video: {info['duration']:.1f}s, {info['width']}x{info['height']}, {info.get('fps', 0):.0f}fps")
    parts.append(f"Motion: {motion['motion_level']} ({motion['motion_score']:.1f}%)")
    if motion['scene_changes'] > 0:
        parts.append(f"{motion['scene_changes']} scene transitions detected")
    if info.get('has_audio'):
        parts.append("Has audio track")

    return {
        "info": info,
        "motion": motion,
        "thumbnail_path": thumb_path,
        "output_dir": output_dir,
        "description": ". ".join(parts) + ".",
    }


def process_video(video_path: str) -> dict:
    output_dir = tempfile.mkdtemp(prefix="contentai_video_")

    audio_path = extract_audio(video_path, output_dir)
    frame_paths = extract_frames(video_path, output_dir)
    info = get_video_info(video_path)

    return {
        "audio_path": audio_path,
        "frame_paths": frame_paths,
        "frame_count": len(frame_paths),
        "duration": info["duration"],
        "width": info["width"],
        "height": info["height"],
        "output_dir": output_dir,
    }
