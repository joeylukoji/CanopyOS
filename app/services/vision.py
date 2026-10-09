import threading
from io import BytesIO

import numpy as np
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

from app.services.metrics import COLORS, GROUPS, RECAPTURE, SceneRejected

MODEL_ID = "nvidia/segformer-b0-finetuned-ade-512-512"
MODEL_REVISION = "489d5cd81a0b59fab9b7ea758d3548ebe99677da"
Image.MAX_IMAGE_PIXELS = 24_000_000


def decode_image(content: bytes) -> Image.Image:
    try:
        with Image.open(BytesIO(content)) as source:
            if source.format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError("Use a JPEG, PNG or WebP image.")
            if source.width * source.height > 24_000_000:
                raise ValueError("Image exceeds the 24 megapixel limit.")
            if min(source.size) < 128:
                raise ValueError("Use an image at least 128 pixels wide and tall.")
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((1280, 1280))
            clean = Image.new("RGB", image.size)
            clean.paste(image)
            return clean
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("This file is not a supported image.") from exc


def check_quality(image: Image.Image):
    gray = image.convert("L")
    gray.thumbnail((256, 256))
    values = np.asarray(gray, dtype=float)
    # Heuristic rejection, not a general-purpose outdoor or blur classifier.
    edges = np.asarray(gray.filter(ImageFilter.FIND_EDGES), dtype=float)[2:-2, 2:-2]
    if values.mean() < 22 or values.std() < 8 or edges.mean() < 2:
        raise SceneRejected(RECAPTURE)


class SegFormer:
    model_id = MODEL_ID

    def __init__(self):
        self.status = "not_loaded"
        self.model = None
        self.lock = threading.Lock()

    def load(self):
        with self.lock:
            if self.model is not None:
                return
            self.status = "loading"
            try:
                import torch
                from transformers import (
                    SegformerForSemanticSegmentation,
                    SegformerImageProcessorPil,
                )

                torch.set_num_threads(4)
                self.processor = SegformerImageProcessorPil.from_pretrained(
                    MODEL_ID, revision=MODEL_REVISION
                )
                self.model = SegformerForSemanticSegmentation.from_pretrained(
                    MODEL_ID, revision=MODEL_REVISION, use_safetensors=True
                ).eval()
                self.status = "ready"
            except Exception:
                self.model = None
                self.status = "unavailable"
                raise

    def segment(self, image: Image.Image):
        import torch

        self.load()
        inputs = self.processor(images=image, return_tensors="pt")
        with torch.inference_mode():
            logits = self.model(**inputs).logits
            confidence = float(logits.softmax(dim=1).amax(dim=1).mean())
            labels = logits.argmax(dim=1)[0].cpu().numpy().astype(np.uint8)
        labels = np.array(Image.fromarray(labels).resize(image.size, Image.Resampling.NEAREST))
        return labels, confidence


def overlay(image: Image.Image, labels: np.ndarray) -> Image.Image:
    original = np.asarray(image).astype(float)
    for group, ids in GROUPS.items():
        mask = np.isin(labels, ids)
        original[mask] = original[mask] * 0.45 + np.array(COLORS[group]) * 0.55
    return Image.fromarray(original.astype(np.uint8))


def concept(image: Image.Image, labels: np.ndarray) -> Image.Image:
    pixels = np.asarray(image).astype(float)
    candidate = np.isin(labels, GROUPS["open_ground"])
    pixels[candidate] = pixels[candidate] * 0.35 + np.array([118, 195, 112]) * 0.65
    return Image.fromarray(pixels.astype(np.uint8))
