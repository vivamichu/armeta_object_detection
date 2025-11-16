from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
from typing import Iterable

from ultralytics import YOLO

from ..config import get_settings
from .pdf_utils import PageImage, convert_pdf_to_images


@dataclass(slots=True)
class DetectionResult:
    label: str
    confidence: float
    bounding_box: tuple[float, float, float, float]
    page: int | None = None
    page_width: float | None = None
    page_height: float | None = None

    def as_dict(self) -> dict[str, float | str | tuple[float, float, float, float] | int | None]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "bounding_box": self.bounding_box,
            "page": self.page,
            "page_width": self.page_width,
            "page_height": self.page_height,
        }


class DigitalInspectorClient:
    """Wraps a YOLO detector for document analysis.

    The client converts PDFs into per-page PNG images (via pdf2image) and runs a
    YOLO model to detect the supported classes (qr, signature, stamp, stamp_q).
    The model path, DPI, and confidence threshold are configurable via settings
    so different weights can be dropped in without code changes.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.model_path = Path(self.settings.model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Detection model not found at {self.model_path}. "
                "Update DI_MODEL_PATH or place the weights in the expected location."
            )
        self._model = YOLO(str(self.model_path))
        # ultralytics exposes names as dict or list; normalize to dict[int,str]
        names = self._model.names
        if isinstance(names, dict):
            self._class_names = {int(k): v for k, v in names.items()}
        else:
            self._class_names = {idx: label for idx, label in enumerate(names)}

    async def analyze(self, pdf_path: Path) -> list[DetectionResult]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._analyze_sync, pdf_path)

    def _analyze_sync(self, pdf_path: Path) -> list[DetectionResult]:
        temp_dir = Path(tempfile.mkdtemp(prefix="di_pages_"))
        try:
            page_images = convert_pdf_to_images(
                pdf_path=pdf_path,
                output_dir=temp_dir,
                dpi=self.settings.pdf_dpi,
            )
            detections: list[DetectionResult] = []
            for page_number, page_image in enumerate(page_images, start=1):
                results = self._model.predict(
                    source=str(page_image.path),
                    conf=self.settings.model_confidence,
                    verbose=False,
                )
                detections.extend(
                    self._detections_from_results(
                        results,
                        page_number,
                        page_image.width,
                        page_image.height,
                    )
                )
            return detections
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _detections_from_results(
        self,
        results: Iterable,
        page_number: int,
        page_width: int,
        page_height: int,
    ) -> list[DetectionResult]:
        parsed: list[DetectionResult] = []
        for result in results:
            if not hasattr(result, "boxes") or result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                label = self._class_names.get(cls_id, str(cls_id))
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = map(float, box.xyxy[0])
                parsed.append(
                    DetectionResult(
                        label=label,
                        confidence=confidence,
                        bounding_box=(x1, y1, x2, y2),
                        page=page_number,
                        page_width=float(page_width),
                        page_height=float(page_height),
                    )
                )
        return parsed


def detection_from_result(result: DetectionResult) -> dict[str, float | str | tuple[float, float, float, float] | int | None]:
    return result.as_dict()
