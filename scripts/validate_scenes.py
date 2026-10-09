"""Run real, local segmentation on operator-supplied validation photographs."""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.metrics import SceneRejected, calculate_metrics
from app.services.vision import SegFormer, check_quality, decode_image, overlay


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/model-validation"))
    args = parser.parse_args()
    inputs = sorted(
        p for p in args.images.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
    )
    if not inputs:
        parser.error("No supported validation images found.")
    args.output.mkdir(parents=True, exist_ok=True)
    model = SegFormer()
    started = time.monotonic()
    model.load()
    load_seconds = round(time.monotonic() - started, 2)
    results = []
    for path in inputs:
        start = time.monotonic()
        result = {"file": path.name}
        try:
            image = decode_image(path.read_bytes())
            check_quality(image)
            labels, confidence = model.segment(image)
            if confidence < 0.35:
                raise SceneRejected("Low segmentation confidence")
            result.update(
                status="analyzed",
                metrics=calculate_metrics(labels).model_dump(),
                model_confidence=round(confidence, 4),
            )
            overlay(image, labels).save(args.output / f"{path.stem}-segmentation.jpg")
        except (SceneRejected, ValueError) as exc:
            result.update(status="rejected", reason=str(exc))
        result["seconds"] = round(time.monotonic() - start, 2)
        results.append(result)
        print(json.dumps(result))
    (args.output / "results.json").write_text(
        json.dumps(
            {
                "model": model.model_id,
                "load_seconds": load_seconds,
                "results": results,
                "scope": "Software smoke test, not a scientific accuracy benchmark.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
