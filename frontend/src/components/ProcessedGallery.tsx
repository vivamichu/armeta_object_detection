import { useMemo } from "react";
import type { DocumentRecord, Detection } from "../types";

interface ProcessedGalleryProps {
  documents: DocumentRecord[];
  selectedId?: string | null;
  onSelect?: (documentId: string) => void;
}

const CANVAS_WIDTH = 360;
const CANVAS_HEIGHT = 480;

export function ProcessedGallery({ documents, selectedId, onSelect }: ProcessedGalleryProps) {
  return (
    <div className="preview-scroll" role="list">
      {documents.map((document) => (
        <PreviewCard
          key={document.id}
          document={document}
          active={document.id === selectedId}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

function PreviewCard({
  document,
  active,
  onSelect
}: {
  document: DocumentRecord;
  active?: boolean;
  onSelect?: (documentId: string) => void;
}) {
  const boxes = document.detections ?? [];

  const { maxX, maxY } = useMemo(() => getExtents(boxes), [boxes]);

  return (
    <article
      className={`preview-card${active ? " preview-card--active" : ""}`}
      role="listitem"
      tabIndex={0}
      onClick={() => onSelect?.(document.id)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect?.(document.id);
        }
      }}
    >
      <div className="preview-header">
        <div>
          <p className="preview-title">{document.file_name}</p>
          <p className="muted preview-subtitle">{boxes.length} detections</p>
        </div>
        <span className="preview-updated">{new Date(document.updated_at).toLocaleTimeString()}</span>
      </div>
      <div
        className="preview-canvas"
        style={{ width: CANVAS_WIDTH, height: CANVAS_HEIGHT }}
        aria-label={`Bounding boxes for ${document.file_name}`}
      >
        {boxes.map((detection, index) => (
          <BoundingBoxLayer
            key={`${document.id}-${index}`}
            detection={detection}
            maxX={maxX}
            maxY={maxY}
          />
        ))}
      </div>
    </article>
  );
}

function BoundingBoxLayer({
  detection,
  maxX,
  maxY
}: {
  detection: Detection;
  maxX: number;
  maxY: number;
}) {
  const [x1, y1, x2, y2] = detection.bounding_box;
  const width = Math.max(1, x2 - x1);
  const height = Math.max(1, y2 - y1);
  const left = (x1 / maxX) * 100;
  const top = (y1 / maxY) * 100;
  const boxWidth = (width / maxX) * 100;
  const boxHeight = (height / maxY) * 100;

  return (
    <div
      className="bbox"
      style={{
        left: `${left}%`,
        top: `${top}%`,
        width: `${boxWidth}%`,
        height: `${boxHeight}%`
      }}
    >
      <span className="bbox-label">
        {detection.label} · {Math.round(detection.confidence * 100)}%
      </span>
    </div>
  );
}

function getExtents(detections: Detection[]): { maxX: number; maxY: number } {
  if (!detections.length) {
    return { maxX: CANVAS_WIDTH, maxY: CANVAS_HEIGHT };
  }

  const maxX = Math.max(
    CANVAS_WIDTH,
    ...detections.map((detection) => Math.max(detection.bounding_box[0], detection.bounding_box[2]))
  );
  const maxY = Math.max(
    CANVAS_HEIGHT,
    ...detections.map((detection) => Math.max(detection.bounding_box[1], detection.bounding_box[3]))
  );

  return { maxX, maxY };
}
