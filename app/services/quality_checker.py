import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def check_image_quality(image_path: str) -> dict:
    result = {
        "resolution": "unknown",
        "megapixels": 0,
        "width": 0,
        "height": 0,
        "blur_score": 0,
        "blur_assessment": "unknown",
        "brightness": 0,
        "brightness_assessment": "unknown",
        "overall_score": 0,
        "issues": [],
        "suggestions": [],
    }
    try:
        import cv2
        import numpy as np
        from PIL import Image

        img_pil = Image.open(image_path).convert("RGB")
        w, h = img_pil.size
        result["width"] = w
        result["height"] = h
        result["megapixels"] = round((w * h) / 1_000_000, 2)
        result["resolution"] = f"{w}x{h}"

        img_cv = cv2.imread(image_path)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        result["blur_score"] = round(laplacian_var, 2)
        if laplacian_var < 50:
            result["blur_assessment"] = "blurry"
            result["issues"].append("Image appears blurry")
            result["suggestions"].append("Use a sharper image or reduce motion blur")
        elif laplacian_var < 200:
            result["blur_assessment"] = "slightly soft"
        else:
            result["blur_assessment"] = "sharp"

        brightness = np.mean(gray)
        result["brightness"] = round(float(brightness), 2)
        if brightness < 60:
            result["brightness_assessment"] = "too dark"
            result["issues"].append("Image is too dark")
            result["suggestions"].append("Increase brightness or use better lighting")
        elif brightness > 200:
            result["brightness_assessment"] = "too bright"
            result["issues"].append("Image is overexposed")
            result["suggestions"].append("Reduce brightness or use diffused lighting")
        elif brightness < 80:
            result["brightness_assessment"] = "slightly dark"
        elif brightness > 180:
            result["brightness_assessment"] = "slightly bright"
        else:
            result["brightness_assessment"] = "well-lit"

        score = 100
        if w < 800 or h < 600:
            score -= 20
            result["issues"].append(f"Low resolution ({w}x{h})")
            result["suggestions"].append("Use at least 1080x1080 for social media")
        if laplacian_var < 50:
            score -= 25
        elif laplacian_var < 100:
            score -= 10
        if brightness < 60 or brightness > 200:
            score -= 20
        elif brightness < 80 or brightness > 180:
            score -= 5
        result["overall_score"] = max(0, score)

    except Exception as e:
        logger.error("Image quality check failed: %s", e)
        result["issues"].append(f"Quality check error: {e}")

    return result


def check_video_quality(video_path: str) -> dict:
    result = {
        "duration": 0,
        "width": 0,
        "height": 0,
        "resolution": "unknown",
        "bitrate": 0,
        "bitrate_assessment": "unknown",
        "fps": 0,
        "codec": "unknown",
        "overall_score": 0,
        "issues": [],
        "suggestions": [],
    }
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        import subprocess

        cmd = [ffmpeg, "-i", video_path, "-f", "null", "-"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        stderr = proc.stderr

        for line in stderr.split("\n"):
            line = line.strip()
            if "Duration:" in line:
                parts = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = parts.split(":")
                result["duration"] = round(float(h) * 3600 + float(m) * 60 + float(s), 2)
            elif "Video:" in line:
                tokens = [t.strip() for t in line.split("Video:")[1].split(",")]
                result["codec"] = tokens[0] if tokens else "unknown"
                for t in tokens:
                    if "x" in t and any(c.isdigit() for c in t):
                        dims = t.split("x")
                        try:
                            result["width"] = int(dims[0].strip().split()[-1])
                            result["height"] = int(dims[1].strip().split()[0])
                        except (ValueError, IndexError):
                            pass
                    if "kb/s" in t.lower() or "Mb/s" in t.lower():
                        try:
                            num = "".join(c for c in t if c.isdigit() or c == ".")
                            result["bitrate"] = float(num)
                        except ValueError:
                            pass
            elif "Stream #" in line and "Audio:" in line:
                tokens = [t.strip() for t in line.split("Audio:")[1].split(",")]
                if tokens:
                    result["audio_codec"] = tokens[0]

        if result["width"] and result["height"]:
            result["resolution"] = f"{result['width']}x{result['height']}"

        score = 100
        if result["width"] < 1280:
            score -= 20
            result["issues"].append(f"Low resolution ({result['resolution']})")
            result["suggestions"].append("Record in at least 720p (1280x720)")
        if result["duration"] > 120:
            score -= 30
            result["issues"].append(f"Too long for social media ({result['duration']:.0f}s)")
            result["suggestions"].append("Keep videos under 60 seconds for best engagement")
        elif result["duration"] > 60:
            score -= 10
            result["issues"].append("Video is longer than 60s (may reduce engagement)")
        if result["bitrate"] > 0 and result["bitrate"] < 1000:
            score -= 15
            result["issues"].append("Low bitrate — may appear compressed")
            result["suggestions"].append("Use higher bitrate for better quality")
        if result["duration"] < 3:
            score -= 10
            result["issues"].append("Very short video — may not convey enough content")
        result["overall_score"] = max(0, score)

    except Exception as e:
        logger.error("Video quality check failed: %s", e)
        result["issues"].append(f"Quality check error: {e}")

    return result
