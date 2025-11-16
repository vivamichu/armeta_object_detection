from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pdf2image import convert_from_path


@dataclass(slots=True)
class PageImage:
    path: Path
    width: int
    height: int


def convert_pdf_to_images(pdf_path: Path | str, output_dir: Path | str | None = None, dpi: int = 200) -> list[PageImage]:
    """Convert a PDF into PNG images (one per page).

    Mirrors the utility shared in the requirements while returning concrete ``Path``
    instances so downstream consumers can easily iterate over the generated files.
    """

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if output_dir is None:
        target_dir = pdf_path.parent
    else:
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

    images = convert_from_path(pdf_path, dpi=dpi)
    created_files: list[PageImage] = []
    base_name = pdf_path.stem

    for index, image in enumerate(images):
        if len(images) == 1:
            image_path = target_dir / f"{base_name}.png"
        else:
            image_path = target_dir / f"{base_name}_page_{index + 1:03d}.png"
        image.save(image_path, "PNG")
        created_files.append(PageImage(path=image_path, width=image.width, height=image.height))

    return created_files
