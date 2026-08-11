import logging

logger = logging.getLogger(__name__)

_ocr_reader = None


def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        logger.info("Loading EasyOCR reader (English)...")
        _ocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        logger.info("EasyOCR loaded.")
    return _ocr_reader


def extract_text_from_image(image_path: str) -> str:
    try:
        reader = _get_ocr_reader()
        results = reader.readtext(image_path, detail=0, paragraph=True)
        if not results:
            return ""
        extracted = "\n".join(results)
        if len(extracted.strip()) < 3:
            return ""
        return f"Text found in image (OCR):\n{extracted}"
    except Exception as e:
        logger.error("EasyOCR failed: %s", e)
        return ""
