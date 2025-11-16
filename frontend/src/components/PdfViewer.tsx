import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DocumentRecord, Detection } from "../types";
import { buildApiUrl } from "../api/client";
import { GlobalWorkerOptions, getDocument } from "pdfjs-dist";
import type { PDFDocumentProxy } from "pdfjs-dist/types/src/pdf";

if (typeof window !== "undefined" && typeof Worker !== "undefined") {
  const pdfWorker = new Worker(new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url), {
    type: "module"
  });
  GlobalWorkerOptions.workerPort = pdfWorker as unknown as Worker;
}

interface PdfViewerProps {
  document: DocumentRecord | null;
}

interface Size {
  width: number;
  height: number;
}

interface PageMeta extends Size {
  pageNumber: number;
}

const BASE_SCALE = 1.35;
const MIN_STAGE_WIDTH = 320;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 2.5;
const ZOOM_STEP = 0.1;
const MAX_FIT_SCALE = 2.5;

export function PdfViewer({ document }: PdfViewerProps) {
  const [pages, setPages] = useState<PageMeta[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pdfRef = useRef<PDFDocumentProxy | null>(null);
  const canvasRefs = useRef<Record<number, HTMLCanvasElement | null>>({});
  const renderTokenRef = useRef(0);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const [stageWidth, setStageWidth] = useState<number | null>(null);
  const [zoomMode, setZoomMode] = useState<"fit" | "manual">("fit");
  const [zoomLevel, setZoomLevel] = useState(1);

  const detections = document?.detections ?? [];
  const detectionsByPage = useMemo(() => groupDetectionsByPage(detections), [detections]);
  const documentId = document?.id ?? null;
  const documentUpdatedAt = document?.updated_at ?? null;
  const documentDownloadUrl = document?.download_url ?? null;

  const pageMetaMap = useMemo(() => new Map(pages.map((page) => [page.pageNumber, page])), [pages]);

  const clampZoom = useCallback((value: number) => {
    return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number(value.toFixed(2))));
  }, []);

  const fitScaleForPage = useCallback(
    (page?: PageMeta) => {
      if (!page || !stageWidth) {
        return 1;
      }
      const availableWidth = Math.max(stageWidth, MIN_STAGE_WIDTH);
      const ratio = availableWidth / page.width;
      return Math.min(ratio, MAX_FIT_SCALE);
    },
    [stageWidth]
  );

  const getScaleFactor = useCallback(
    (page?: PageMeta) => {
      if (zoomMode === "fit") {
        return fitScaleForPage(page);
      }
      return zoomLevel;
    },
    [fitScaleForPage, zoomMode, zoomLevel]
  );

  const applyManualZoom = useCallback(
    (delta: number) => {
      setZoomMode("manual");
      setZoomLevel((prev) => {
        const base = zoomMode === "fit" ? fitScaleForPage(pages[0]) : prev;
        return clampZoom(base + delta);
      });
    },
    [clampZoom, fitScaleForPage, pages, zoomMode]
  );

  const handleZoomIn = useCallback(() => {
    applyManualZoom(ZOOM_STEP);
  }, [applyManualZoom]);

  const handleZoomOut = useCallback(() => {
    applyManualZoom(-ZOOM_STEP);
  }, [applyManualZoom]);

  const handleResetZoom = useCallback(() => {
    setZoomMode("manual");
    setZoomLevel(1);
  }, []);

  const handleFitWidth = useCallback(() => {
    setZoomMode("fit");
  }, []);

  const getDisplaySize = useCallback(
    (page: PageMeta) => {
      const scale = getScaleFactor(page);
      return {
        width: page.width * scale,
        height: page.height * scale,
        scale
      };
    },
    [getScaleFactor]
  );

  const registerCanvas = useCallback(
    (pageNumber: number, node: HTMLCanvasElement | null) => {
      canvasRefs.current[pageNumber] = node;
      if (node) {
        const pageMeta = pageMetaMap.get(pageNumber);
        const scale = getScaleFactor(pageMeta);
        const pageDetections = detectionsByPage.get(pageNumber) ?? [];
        void renderPage(pageNumber, node, pdfRef.current, scale, pageDetections);
      }
    },
    [detectionsByPage, getScaleFactor, pageMetaMap]
  );

  const clearAllCanvases = useCallback(() => {
    Object.values(canvasRefs.current).forEach((canvas) => {
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    const token = renderTokenRef.current + 1;
    renderTokenRef.current = token;

    async function renderPdf() {
      clearAllCanvases();
      setPages([]);

      if (!documentId || !documentDownloadUrl) {
        if (pdfRef.current) {
          await pdfRef.current.destroy();
          pdfRef.current = null;
        }
        setIsLoading(false);
        setError(null);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(buildApiUrl(documentDownloadUrl));
        if (!response.ok) {
          throw new Error("Unable to load PDF");
        }
        const buffer = await response.arrayBuffer();
        if (cancelled || renderTokenRef.current !== token) return;

        const pdf = await getDocument({ data: buffer }).promise;
        if (cancelled || renderTokenRef.current !== token) {
          await pdf.destroy();
          return;
        }

        if (pdfRef.current) {
          await pdfRef.current.destroy();
        }
        pdfRef.current = pdf;

        const metadata: PageMeta[] = [];
        for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
          const page = await pdf.getPage(pageNumber);
          const viewport = page.getViewport({ scale: BASE_SCALE });
          metadata.push({ pageNumber, width: viewport.width, height: viewport.height });
        }

        if (!cancelled && renderTokenRef.current === token) {
          setPages(metadata);
        }
      } catch (err) {
        if (!cancelled) {
          setError((err as Error).message || "Failed to render PDF");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void renderPdf();
    return () => {
      cancelled = true;
    };
  }, [documentId, documentUpdatedAt, documentDownloadUrl, clearAllCanvases]);

  useEffect(() => {
    pages.forEach(({ pageNumber }) => {
      const canvas = canvasRefs.current[pageNumber];
      if (canvas) {
        const pageMeta = pageMetaMap.get(pageNumber);
        const scale = getScaleFactor(pageMeta);
        const pageDetections = detectionsByPage.get(pageNumber) ?? [];
        void renderPage(pageNumber, canvas, pdfRef.current, scale, pageDetections);
      }
    });
  }, [pages, pageMetaMap, getScaleFactor, detectionsByPage]);

  useEffect(() => {
    const node = stageRef.current;
    if (!node) return;

    const measure = () => {
      const target = stageRef.current;
      if (!target) return;
      let width = target.clientWidth;
      if (typeof window !== "undefined") {
        const styles = window.getComputedStyle(target);
        width -= parseFloat(styles.paddingLeft || "0");
        width -= parseFloat(styles.paddingRight || "0");
      }
      setStageWidth(Math.max(width, MIN_STAGE_WIDTH));
    };

    measure();

    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(() => measure());
      observer.observe(node);
      return () => observer.disconnect();
    }

    window.addEventListener("resize", measure);
    return () => {
      window.removeEventListener("resize", measure);
    };
  }, []);

  useEffect(() => {
    if (stageWidth || !stageRef.current) {
      return;
    }
    const width = stageRef.current.clientWidth;
    setStageWidth(Math.max(width, MIN_STAGE_WIDTH));
  }, [stageWidth]);

  useEffect(() => {
    setZoomMode("fit");
    setZoomLevel(1);
  }, [documentId]);

  useEffect(() => {
    return () => {
      if (pdfRef.current) {
        void pdfRef.current.destroy();
        pdfRef.current = null;
      }
    };
  }, []);

  if (!document || !document.download_url) {
    return <div className="pdf-viewer empty">Select a processed document to preview the PDF output.</div>;
  }

  const hasAnyDetections = detections.length > 0;
  const emptyMessage = document.status === "succeeded" ? "No detections for this document." : "Awaiting detections for this document…";
  const referencePage = pages[0];
  const currentScale = referencePage ? getScaleFactor(referencePage) : zoomMode === "fit" ? 1 : zoomLevel;
  const zoomLabel = zoomMode === "fit" ? `Fit · ${Math.round(currentScale * 100)}%` : `${Math.round(zoomLevel * 100)}%`;
  const disableZoomControls = pages.length === 0;
  const canZoomIn = currentScale < MAX_ZOOM - 0.01;
  const canZoomOut = currentScale > MIN_ZOOM + 0.01;

  return (
    <div className="pdf-viewer">
      <div className="pdf-toolbar">
        <button
          type="button"
          className={`toolbar-button${zoomMode === "fit" ? " active" : ""}`}
          onClick={handleFitWidth}
          disabled={disableZoomControls}
        >
          Fit width
        </button>
        <div className="toolbar-divider" aria-hidden="true" />
        <button
          type="button"
          className="toolbar-button"
          onClick={handleZoomOut}
          disabled={disableZoomControls || !canZoomOut}
        >
          -
        </button>
        <span className="zoom-indicator">{zoomLabel}</span>
        <button
          type="button"
          className="toolbar-button"
          onClick={handleZoomIn}
          disabled={disableZoomControls || !canZoomIn}
        >
          +
        </button>
        <button
          type="button"
          className="toolbar-button"
          onClick={handleResetZoom}
          disabled={disableZoomControls}
        >
          Reset
        </button>
      </div>
      <div className="pdf-stage" ref={stageRef}>
        {pages.length === 0 && !isLoading ? (
          <div className="empty small">No preview available.</div>
        ) : (
          <div className="pdf-pages">
            {pages.map((page) => {
              const pageDetections = detectionsByPage.get(page.pageNumber) ?? [];
              const displaySize = getDisplaySize(page);
              return (
                <div className="pdf-page" key={`${document.id}-page-${page.pageNumber}`}>
                  <div className="pdf-stage-inner" style={{ width: displaySize.width, height: displaySize.height }}>
                    <canvas
                      ref={(node) => registerCanvas(page.pageNumber, node)}
                      className="pdf-canvas"
                    />
                  </div>
                  <div className="pdf-page-label">Page {page.pageNumber}</div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {isLoading && <div className="muted small-text">Rendering PDF…</div>}
      {error && <div className="error-banner compact">{error}</div>}
      {!hasAnyDetections && !isLoading && <div className="muted small-text">{emptyMessage}</div>}
    </div>
  );
}

async function renderPage(
  pageNumber: number,
  canvas: HTMLCanvasElement | null,
  pdf: PDFDocumentProxy | null,
  scaleFactor = 1,
  detections: Detection[] = []
) {
  if (!canvas || !pdf) return;
  const context = canvas.getContext("2d");
  if (!context) return;
  const page = await pdf.getPage(pageNumber);
  const viewport = page.getViewport({ scale: BASE_SCALE * scaleFactor });
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  await page.render({ canvasContext: context, viewport, canvas }).promise;
  if (detections.length) {
    drawDetections(context, detections, viewport.width, viewport.height);
  }
}

function getExtents(detections: Detection[]): { maxX: number; maxY: number } {
  if (!detections.length) {
    return { maxX: 1, maxY: 1 };
  }

  const maxX = Math.max(...detections.map((d) => Math.max(d.bounding_box[0], d.bounding_box[2])));
  const maxY = Math.max(...detections.map((d) => Math.max(d.bounding_box[1], d.bounding_box[3])));

  return {
    maxX: Math.max(maxX, 1),
    maxY: Math.max(maxY, 1)
  };
}

function groupDetectionsByPage(detections: Detection[]): Map<number, Detection[]> {
  const map = new Map<number, Detection[]>();
  detections.forEach((detection) => {
    const pageNumber = detection.page && detection.page > 0 ? detection.page : 1;
    const bucket = map.get(pageNumber) ?? [];
    bucket.push(detection);
    map.set(pageNumber, bucket);
  });
  return map;
}

function drawDetections(
  context: CanvasRenderingContext2D,
  detections: Detection[],
  viewportWidth: number,
  viewportHeight: number
) {
  if (!detections.length) return;
  const fallback = getExtents(detections);
  context.save();
  context.lineWidth = 2;
  context.textBaseline = "top";
  context.font = "12px 'Inter', system-ui, sans-serif";
  detections.forEach((detection) => {
    const [x1, y1, x2, y2] = detection.bounding_box;
    const sourceWidth = detection.page_width ?? fallback.maxX;
    const sourceHeight = detection.page_height ?? fallback.maxY;
    const widthBase = Math.max(sourceWidth, 1);
    const heightBase = Math.max(sourceHeight, 1);
    const scaleX = viewportWidth / widthBase;
    const scaleY = viewportHeight / heightBase;
    const left = x1 * scaleX;
    const top = y1 * scaleY;
    const boxWidth = Math.max(1, (x2 - x1) * scaleX);
    const boxHeight = Math.max(1, (y2 - y1) * scaleY);

    context.strokeStyle = "rgba(37, 99, 235, 0.95)";
    context.shadowColor = "rgba(37, 99, 235, 0.35)";
    context.shadowBlur = 0;
    context.strokeRect(left, top, boxWidth, boxHeight);

    const label = `${detection.label} · ${Math.round(detection.confidence * 100)}%`;
    const paddingX = 4;
    const paddingY = 2;
    const textWidth = context.measureText(label).width;
    const labelWidth = textWidth + paddingX * 2;
    const labelHeight = 14 + paddingY * 2;
    const labelLeft = Math.min(Math.max(0, left), viewportWidth - labelWidth);
    const labelTop = Math.min(top + boxHeight + 4, viewportHeight - labelHeight);

    context.fillStyle = "rgba(30, 41, 59, 0.9)";
    context.fillRect(labelLeft, labelTop, labelWidth, labelHeight);
    context.fillStyle = "#fff";
    context.fillText(label, labelLeft + paddingX, labelTop + paddingY);
  });
  context.restore();
}
