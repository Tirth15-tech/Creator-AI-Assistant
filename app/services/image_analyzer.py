import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_yolo_model = None
_clip_model = None
_clip_processor = None
_blip_model = None
_blip_processor = None

# Phase 2A: Social-media-relevant object classes for YOLOv8
# Maps COCO class IDs to human-friendly labels grouped by category
SOCIAL_OBJECT_CATEGORIES = {
    "person": {"label": "Person", "emoji": "👤"},
    "animal": {"label": "Animal", "emoji": "🐾"},
    "vehicle": {"label": "Vehicle", "emoji": "🚗"},
    "laptop": {"label": "Laptop", "emoji": "💻"},
    "cell phone": {"label": "Mobile Phone", "emoji": "📱"},
    "building": {"label": "Building", "emoji": "🏢"},
    "potted plant": {"label": "Plant", "emoji": "🌿"},
    "food": {"label": "Food", "emoji": "🍕"},
    "tree": {"label": "Tree", "emoji": "🌳"},
    "flower": {"label": "Flower", "emoji": "🌸"},
    "mountain": {"label": "Mountain", "emoji": "🏔️"},
    "surfboard": {"label": "Beach/Surf", "emoji": "🏖️"},
    "skateboard": {"label": "Skateboard", "emoji": "🛹"},
    "bicycle": {"label": "Bicycle", "emoji": "🚲"},
    "motorcycle": {"label": "Motorcycle", "emoji": "🏍️"},
    "car": {"label": "Car", "emoji": "🚗"},
    "truck": {"label": "Truck", "emoji": "🚛"},
    "bus": {"label": "Bus", "emoji": "🚌"},
    "train": {"label": "Train", "emoji": "🚆"},
    "airplane": {"label": "Airplane", "emoji": "✈️"},
    "boat": {"label": "Boat", "emoji": "⛵"},
    "bird": {"label": "Bird", "emoji": "🐦"},
    "cat": {"label": "Cat", "emoji": "🐱"},
    "dog": {"label": "Dog", "emoji": "🐕"},
    "horse": {"label": "Horse", "emoji": "🐴"},
    "sheep": {"label": "Sheep", "emoji": "🐑"},
    "cow": {"label": "Cow", "emoji": "🐄"},
    "bear": {"label": "Bear", "emoji": "🐻"},
    "elephant": {"label": "Elephant", "emoji": "🐘"},
    "cup": {"label": "Cup/Drink", "emoji": "☕"},
    "wine glass": {"label": "Wine Glass", "emoji": "🍷"},
    "bottle": {"label": "Bottle", "emoji": "🍶"},
    "fork": {"label": "Fork", "emoji": "🍴"},
    "knife": {"label": "Knife", "emoji": "🔪"},
    "bowl": {"label": "Bowl", "emoji": "🥣"},
    "sandwich": {"label": "Sandwich", "emoji": "🥪"},
    "pizza": {"label": "Pizza", "emoji": "🍕"},
    "cake": {"label": "Cake", "emoji": "🎂"},
    "chair": {"label": "Chair", "emoji": "🪑"},
    "couch": {"label": "Couch", "emoji": "🛋️"},
    "bed": {"label": "Bed", "emoji": "🛏️"},
    "dining table": {"label": "Dining Table", "emoji": "🍽️"},
    "tv": {"label": "TV/Screen", "emoji": "📺"},
    "keyboard": {"label": "Keyboard", "emoji": "⌨️"},
    "mouse": {"label": "Mouse", "emoji": "🖱️"},
    "book": {"label": "Book", "emoji": "📚"},
    "clock": {"label": "Clock", "emoji": "🕐"},
    "umbrella": {"label": "Umbrella", "emoji": "☂️"},
    "handbag": {"label": "Handbag", "emoji": "👜"},
    "suitcase": {"label": "Suitcase", "emoji": "🧳"},
    "teddy bear": {"label": "Teddy Bear", "emoji": "🧸"},
    "scissors": {"label": "Scissors", "emoji": "✂️"},
    "sports ball": {"label": "Sports Ball", "emoji": "⚽"},
    "tennis racket": {"label": "Tennis Racket", "emoji": "🎾"},
    "baseball bat": {"label": "Baseball Bat", "emoji": "⚾"},
    "frisbee": {"label": "Frisbee", "emoji": "🥏"},
}

# Phase 2A: Enhanced CLIP scene labels for social media categorization
SOCIAL_SCENE_LABELS = [
    "travel destination", "food photography", "nature landscape",
    "urban cityscape", "business meeting", "sports action",
    "technology gadgets", "fashion outfit", "fitness gym",
    "beach sunset", "mountain adventure", "street photography",
    "coffee shop", "restaurant dining", "home interior",
    "office workspace", "concert stage", "festival celebration",
    "portrait selfie", "group photo", "product flat lay",
    "pet animal", "wildlife nature", "flower garden",
    "night city lights", "morning sunrise", "rainy day mood",
    "minimalist aesthetic", "vintage retro", "luxury lifestyle",
    "adventure hiking", "yoga meditation", "party celebration",
    "baby family", "wedding ceremony", "graduation milestone",
    "car automotive", "real estate property", "craft DIY",
    "painting art", "book reading", "music performance",
]


def _get_yolo():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        logger.info("Loading YOLOv8 model...")
        _yolo_model = YOLO("yolov8n.pt")
        logger.info("YOLOv8 loaded.")
    return _yolo_model


def _get_clip():
    global _clip_model, _clip_processor
    if _clip_model is None:
        import torch
        from transformers import CLIPModel, CLIPProcessor
        logger.info("Loading CLIP model...")
        _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        _clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        if torch.cuda.is_available():
            _clip_model = _clip_model.cuda()
        logger.info("CLIP loaded.")
    return _clip_model, _clip_processor


def _get_blip():
    global _blip_model, _blip_processor
    if _blip_model is None:
        import torch
        from transformers import BlipProcessor, BlipForConditionalGeneration
        logger.info("Loading BLIP model...")
        _blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        _blip_model = BlipForConditionalGeneration.from_pretrained(
            "Salesforce/blip-image-captioning-base"
        )
        if torch.cuda.is_available():
            _blip_model = _blip_model.cuda()
        logger.info("BLIP loaded.")
    return _blip_model, _blip_processor


# ─────────────────────────────────────────────
# Phase 2A: Enhanced YOLOv8 Object Detection
# ─────────────────────────────────────────────

def detect_objects(image_path: str) -> list[str]:
    """Detect objects using YOLOv8 with social-media-relevant labels and confidence."""
    try:
        model = _get_yolo()
        results = model(image_path, verbose=False)
        objects = []
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label = r.names[cls_id]
                conf = float(box.conf[0])
                if conf > 0.3:
                    # Use social-media-friendly label if available
                    social_info = SOCIAL_OBJECT_CATEGORIES.get(label, None)
                    if social_info:
                        display = f"{social_info['emoji']} {social_info['label']} ({conf:.0%})"
                    else:
                        display = f"{label.title()} ({conf:.0%})"
                    objects.append(display)
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for obj in objects:
            if obj not in seen:
                seen.add(obj)
                unique.append(obj)
        return unique
    except Exception as e:
        logger.error("YOLOv8 detection failed: %s", e)
        return []


def detect_objects_by_category(image_path: str) -> dict:
    """Detect objects grouped by category for structured analysis.

    Returns dict like: {
        "people": [{"label": "Person", "confidence": 0.87, "count": 2}],
        "animals": [...],
        "vehicles": [...],
        "objects": [...],
        "food": [...],
        "nature": [...],
    }
    """
    try:
        model = _get_yolo()
        results = model(image_path, verbose=False)

        # Category grouping maps
        person_labels = {"person"}
        animal_labels = {"cat", "dog", "bird", "horse", "sheep", "cow", "bear", "elephant", "teddy bear"}
        vehicle_labels = {"car", "truck", "bus", "motorcycle", "bicycle", "train", "airplane", "boat"}
        food_labels = {"cup", "wine glass", "bottle", "fork", "knife", "bowl", "sandwich", "pizza", "cake", "apple", "orange", "banana"}
        nature_labels = {"potted plant", "tree", "flower"}

        categories = {
            "people": [], "animals": [], "vehicles": [],
            "objects": [], "food": [], "nature": [],
        }

        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label = r.names[cls_id]
                conf = float(box.conf[0])
                if conf <= 0.3:
                    continue

                entry = {"label": label.title(), "confidence": round(conf, 3)}
                social = SOCIAL_OBJECT_CATEGORIES.get(label, {})
                entry["display"] = f"{social.get('emoji', '')} {social.get('label', label.title())}"

                if label in person_labels:
                    categories["people"].append(entry)
                elif label in animal_labels:
                    categories["animals"].append(entry)
                elif label in vehicle_labels:
                    categories["vehicles"].append(entry)
                elif label in food_labels:
                    categories["food"].append(entry)
                elif label in nature_labels:
                    categories["nature"].append(entry)
                else:
                    categories["objects"].append(entry)

        # Add counts
        summary = {}
        for cat, items in categories.items():
            if items:
                summary[cat] = {"count": len(items), "items": items}
        return summary
    except Exception as e:
        logger.error("YOLOv8 category detection failed: %s", e)
        return {}


# ─────────────────────────────────────────────
# Phase 2A: Enhanced CLIP Scene Classification
# ─────────────────────────────────────────────

def classify_scene(image_path: str) -> list[str]:
    """Classify image scene using CLIP with social-media-relevant labels."""
    try:
        from PIL import Image
        model, processor = _get_clip()
        image = Image.open(image_path).convert("RGB")

        inputs = processor(text=SOCIAL_SCENE_LABELS, images=image, return_tensors="pt", padding=True)
        import torch
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs)

        logits = outputs.logits_per_image[0]
        probs = logits.softmax(dim=0)
        top_indices = probs.argsort(descending=True)[:3]

        scenes = []
        for idx in top_indices:
            prob = probs[idx.item()].item()
            scenes.append(f"{SOCIAL_SCENE_LABELS[idx.item()]} ({prob:.0%})")
        return scenes
    except Exception as e:
        logger.error("CLIP scene classification failed: %s", e)
        return []


def get_dominant_scene(image_path: str) -> str:
    """Return the single most relevant scene category for social media."""
    scenes = classify_scene(image_path)
    if scenes:
        # Extract just the label without confidence
        return scenes[0].split(" (")[0]
    return "general"


# ─────────────────────────────────────────────
# Phase 2A: Enhanced BLIP-2 Image Descriptions
# ─────────────────────────────────────────────

def generate_caption(image_path: str) -> str:
    """Generate a detailed image description using BLIP-2."""
    try:
        from PIL import Image
        model, processor = _get_blip()
        image = Image.open(image_path).convert("RGB")

        # Use conditional captioning with a descriptive prompt for richer output
        text = "a photograph of"
        inputs = processor(image, text, return_tensors="pt")
        import torch
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        with torch.no_grad():
            output = model.generate(**inputs, max_length=100, num_beams=5)

        caption = processor.decode(output[0], skip_special_tokens=True)
        return caption
    except Exception as e:
        logger.error("BLIP captioning failed: %s", e)
        return ""


def generate_detailed_caption(image_path: str) -> str:
    """Generate a detailed multi-sentence description of the image."""
    try:
        from PIL import Image
        model, processor = _get_blip()
        image = Image.open(image_path).convert("RGB")

        prompts = ["a photograph of", "a picture showing", "an image of"]
        captions = []
        for prompt in prompts:
            try:
                inputs = processor(image, prompt, return_tensors="pt")
                import torch
                if torch.cuda.is_available():
                    inputs = {k: v.cuda() for k, v in inputs.items()}
                with torch.no_grad():
                    output = model.generate(**inputs, max_length=80, num_beams=3)
                caption = processor.decode(output[0], skip_special_tokens=True)
                if caption and caption not in captions:
                    captions.append(caption)
            except Exception:
                continue

        if captions:
            # Return the most descriptive caption (longest)
            return max(captions, key=len)
        return ""
    except Exception as e:
        logger.error("BLIP detailed captioning failed: %s", e)
        return ""


# ─────────────────────────────────────────────
# Phase 2A: Full Image Analysis Pipeline
# ─────────────────────────────────────────────

def analyze_image(image_path: str) -> str:
    """Run full image pipeline and return structured description."""
    from PIL import Image

    objects = detect_objects(image_path)
    scenes = classify_scene(image_path)
    caption = generate_caption(image_path)

    img = Image.open(image_path)
    width, height = img.size

    parts = []
    if caption:
        parts.append(f"Image caption: {caption}")
    if scenes:
        parts.append(f"Scene context: {', '.join(scenes)}")
    if objects:
        parts.append(f"Detected objects: {', '.join(objects)}")
    parts.append(f"Image dimensions: {width}x{height}")

    description = ". ".join(parts) + "."
    return description


def analyze_image_full(image_path: str) -> dict:
    """Run full image analysis and return structured dict for frontend display.

    Returns:
        {
            "caption": str,
            "scenes": list[str],
            "objects": list[str],
            "object_categories": dict,
            "dominant_scene": str,
            "dimensions": {"width": int, "height": int, "megapixels": float},
            "description": str,
        }
    """
    from PIL import Image

    objects = detect_objects(image_path)
    categories = detect_objects_by_category(image_path)
    scenes = classify_scene(image_path)
    caption = generate_caption(image_path)
    detailed_caption = generate_detailed_caption(image_path)
    dominant_scene = get_dominant_scene(image_path)

    img = Image.open(image_path)
    width, height = img.size
    megapixels = round((width * height) / 1_000_000, 2)

    parts = []
    if caption:
        parts.append(f"Image caption: {caption}")
    if scenes:
        parts.append(f"Scene context: {', '.join(scenes)}")
    if objects:
        parts.append(f"Detected objects: {', '.join(objects)}")
    parts.append(f"Image dimensions: {width}x{height}")

    return {
        "caption": detailed_caption or caption,
        "scenes": scenes,
        "objects": objects,
        "object_categories": categories,
        "dominant_scene": dominant_scene,
        "dimensions": {"width": width, "height": height, "megapixels": megapixels},
        "description": ". ".join(parts) + ".",
    }


def get_image_info(image_path: str) -> dict:
    try:
        from PIL import Image
        img = Image.open(image_path)
        width, height = img.size
        mode = img.mode
        fmt = img.format
        return {
            "width": width,
            "height": height,
            "mode": mode,
            "format": fmt,
            "megapixels": round((width * height) / 1_000_000, 2),
        }
    except Exception as e:
        return {"error": str(e)}
