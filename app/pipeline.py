import logging
import time
from threading import Lock

import httpx
from PIL import Image

from app.schemas import Report
from app.services.metrics import RECAPTURE, SceneRejected, calculate_metrics
from app.services.providers import decide, explain
from app.services.vision import check_quality, concept, overlay

log = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, store, vision, settings):
        self.store, self.vision, self.settings = store, vision, settings
        self.slot = Lock()
        self.jev_status = "configured_unverified" if settings["jev_key"] else "rules_fallback"
        self.llm_status = (
            "configured_unverified" if settings["gemma_endpoint"] else "template_fallback"
        )

    def run(self, scan):
        scan_id = scan["scan_id"]
        start = time.monotonic()
        try:
            folder = self.store.folder(scan_id)
            self.store.update(scan_id, status="processing", stage=1)
            with Image.open(folder / "original.jpg") as source:
                image = source.convert("RGB")
            check_quality(image)
            labels, confidence = self.vision.segment(image)
            if confidence < 0.35:
                raise SceneRejected(RECAPTURE)
            self.store.update(scan_id, status="processing", stage=2)
            metrics = calculate_metrics(labels)
            overlay(image, labels).save(folder / "segmentation.jpg", quality=88)
            self.store.update(scan_id, status="processing", stage=3)
            with httpx.Client(follow_redirects=False) as client:
                decision = decide(
                    metrics,
                    scan["area_type"],
                    self.settings["jev_key"],
                    self.settings["jev_model"],
                    client,
                )
                self.store.update(scan_id, status="processing", stage=4)
                explanation = explain(
                    metrics,
                    decision,
                    self.settings["gemma_endpoint"],
                    self.settings["gemma_key"],
                    self.settings["gemma_model"],
                    client,
                )
            self.jev_status = "ready" if decision.source == "jev" else "rules_fallback"
            self.llm_status = "ready" if explanation.source == "gemma" else "template_fallback"
            assets = {
                name: f"/assets/{scan_id}/{name}.jpg" for name in ("original", "segmentation")
            }
            if (
                decision.recommended_action == "PLANT_TREES"
                and metrics.open_ground_percentage > 0.05
            ):
                concept(image, labels).save(folder / "concept.jpg", quality=88)
                assets["concept"] = f"/assets/{scan_id}/concept.jpg"
            report = Report(
                metrics=metrics,
                decision=decision,
                explanation=explanation,
                assets=assets,
                vision_model=self.vision.model_id,
                elapsed_seconds=round(time.monotonic() - start, 2),
            )
            self.store.update(scan_id, status="completed", stage=4, report=report)
            log.info("analysis_completed scan=%s seconds=%.2f", scan_id, report.elapsed_seconds)
        except SceneRejected as exc:
            self.store.update(scan_id, status="rejected", stage=0, error=str(exc))
        except Exception:
            log.exception("analysis_failed scan=%s", scan_id)
            self.store.update(
                scan_id,
                status="failed",
                stage=0,
                error="Analysis is temporarily unavailable. The vision model may still need to be downloaded. Please retry shortly.",
            )
        finally:
            self.slot.release()
