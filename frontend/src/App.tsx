import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { buildApiUrl, deleteDocument, fetchDocuments, retryDocument, uploadDocuments } from "./api/client";
import type { DocumentRecord, DocumentStatus } from "./types";
import { UploadPanel } from "./components/UploadPanel";
import { PdfViewer } from "./components/PdfViewer";

const POLL_INTERVAL = 5000;
type DocumentAction = "retry" | "delete";

function StatusBadge({ status }: { status: DocumentStatus }) {
  const STATUS_LABELS: Record<DocumentStatus, string> = {
    pending: "Pending",
    processing: "Processing",
    succeeded: "Completed",
    failed: "Processing failed",
    upload_failed: "Upload failed",
    processing_failed: "Processing failed"
  };

  const className = useMemo(() => `status status-${status}`, [status]);
  return <span className={className}>{STATUS_LABELS[status] ?? status}</span>;
}

function DetectionList({
  detections,
  status
}: {
  detections?: DocumentRecord["detections"];
  status: DocumentStatus;
}) {
  if (!detections || detections.length === 0) {
    const message = status === "succeeded" ? "No detections found." : "Waiting for model output…";
    return <span className="muted">{message}</span>;
  }

  const counts = detections.reduce<Record<string, number>>((acc, detection) => {
    const key = detection.label || "unknown";
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});

  const entries = Object.entries(counts).sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="detections detections--compact">
      {entries.map(([label, count]) => (
        <span key={label} className="detection-count">
          <strong>{label}</strong>: {count}
        </span>
      ))}
    </div>
  );
}

function DocumentTable({
  documents,
  onPreview,
  selectedId,
  onRetry,
  onDelete,
  pendingActions
}: {
  documents: DocumentRecord[];
  onPreview?: (documentId: string) => void;
  selectedId?: string | null;
  onRetry?: (documentId: string) => void;
  onDelete?: (documentId: string) => void;
  pendingActions?: Record<string, DocumentAction>;
}) {
  if (!documents.length) {
    return <div className="empty">No documents uploaded yet. Drag in a PDF to get started.</div>;
  }

  return (
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Status</th>
          <th>Detections</th>
          <th>Updated</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {documents.map((doc) => {
          const action = pendingActions?.[doc.id];
          const isRetrying = action === "retry";
          const isDeleting = action === "delete";
          const canRetry = !!onRetry && (doc.status === "processing_failed" || doc.status === "failed");
          const requiresReupload = doc.status === "upload_failed";
          const hasPreview = Boolean(doc.download_url);
          const downloadDisabled = !doc.download_url || isDeleting;
          const previewDisabled = !hasPreview || isDeleting;

          return (
            <tr key={doc.id} className={doc.id === selectedId ? "row-active" : undefined}>
              <td>
                {doc.file_name}
                {requiresReupload && <div className="muted small-text">Upload failed — please upload again.</div>}
              </td>
            <td>
              <StatusBadge status={doc.status} />
              {doc.failure_reason && <div className="error">{doc.failure_reason}</div>}
            </td>
            <td>
              <DetectionList detections={doc.detections ?? undefined} status={doc.status} />
            </td>
            <td>{new Date(doc.updated_at).toLocaleString()}</td>
            <td>
              <div className="table-actions">
                <div className="action-group">
                  {onPreview && (
                    <button
                      type="button"
                      className="ghost table-button"
                      onClick={() => onPreview(doc.id)}
                      disabled={previewDisabled}
                    >
                      Preview
                    </button>
                  )}
                  <button
                    type="button"
                    className="ghost table-button"
                    onClick={() => openDownload(doc.download_url)}
                    disabled={downloadDisabled}
                  >
                    Download
                  </button>
                  {onDelete && (
                    <button
                      type="button"
                      className="ghost danger table-button"
                      onClick={() => onDelete(doc.id)}
                      disabled={isDeleting}
                    >
                      {isDeleting ? "Removing…" : "Remove"}
                    </button>
                  )}
                </div>
                {canRetry && (
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => onRetry?.(doc.id)}
                    disabled={isRetrying}
                  >
                    {isRetrying ? "Retrying…" : "Retry"}
                  </button>
                )}
              </div>
            </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function getDownloadUrl(downloadUrl: string): string {
  try {
    const target = new URL(downloadUrl);
    target.searchParams.set("download", "1");
    return target.toString();
  } catch (error) {
    return buildApiUrl(downloadUrl.includes("?") ? downloadUrl : `${downloadUrl}?download=1`);
  }
}

function openDownload(downloadUrl?: string | null) {
  if (!downloadUrl) return;
  const finalUrl = getDownloadUrl(downloadUrl);
  if (typeof window !== "undefined") {
    window.open(finalUrl, "_blank", "noopener,noreferrer");
  } else {
    void fetch(finalUrl);
  }
}

export default function App() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const documentsHashRef = useRef<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pendingActions, setPendingActions] = useState<Record<string, DocumentAction>>({});
  const processedDocuments = useMemo(
    () => documents.filter((doc) => doc.status === "succeeded" && (doc.detections?.length ?? 0) > 0),
    [documents]
  );
  const selectedDocument = useMemo(() => {
    if (selectedId) {
      return documents.find((doc) => doc.id === selectedId) ?? null;
    }
    if (processedDocuments.length) {
      return processedDocuments[0];
    }
    return documents[0] ?? null;
  }, [documents, processedDocuments, selectedId]);

  const refreshDocuments = useCallback(
    async (options?: { force?: boolean }) => {
      try {
        const all = await fetchDocuments();
        const nextHash = fingerprintDocuments(all);
        if (options?.force || nextHash !== documentsHashRef.current) {
          documentsHashRef.current = nextHash;
          setDocuments(all);
        }
      } catch (err) {
        setError((err as Error).message);
      }
    },
    []
  );

  useEffect(() => {
    void refreshDocuments({ force: true });
  }, [refreshDocuments]);

  const shouldPoll = useMemo(() => {
    if (isUploading) return true;
    return documents.some((doc) => doc.status === "pending" || doc.status === "processing");
  }, [documents, isUploading]);

  useEffect(() => {
    if (!shouldPoll) {
      return undefined;
    }
    const interval = setInterval(() => {
      void refreshDocuments();
    }, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [refreshDocuments, shouldPoll]);

  useEffect(() => {
    if (!documents.length) {
      setSelectedId(null);
      return;
    }

    const currentExists = selectedId ? documents.some((doc) => doc.id === selectedId) : false;

    if (!currentExists) {
      const fallback = processedDocuments[0] ?? documents[0];
      setSelectedId(fallback?.id ?? null);
      return;
    }
  }, [documents, processedDocuments, selectedId]);

  const handleUpload = useCallback(
    async (files: File[]) => {
      setIsUploading(true);
      setError(null);
      try {
        await uploadDocuments(files);
        await refreshDocuments();
      } catch (err) {
        setError((err as Error).message || "Upload failed");
      } finally {
        setIsUploading(false);
      }
    },
    [refreshDocuments]
  );

  const markAction = useCallback((documentId: string, action: DocumentAction) => {
    setPendingActions((prev) => ({ ...prev, [documentId]: action }));
  }, []);

  const clearAction = useCallback((documentId: string) => {
    setPendingActions((prev) => {
      const next = { ...prev };
      delete next[documentId];
      return next;
    });
  }, []);

  const handleRetry = useCallback(
    async (documentId: string) => {
      markAction(documentId, "retry");
      setError(null);
      try {
        await retryDocument(documentId);
        await refreshDocuments({ force: true });
      } catch (err) {
        setError((err as Error).message || "Retry failed");
      } finally {
        clearAction(documentId);
      }
    },
    [clearAction, markAction, refreshDocuments]
  );

  const handleDelete = useCallback(
    async (documentId: string) => {
      if (typeof window !== "undefined") {
        const confirmed = window.confirm("Remove this document from history? This cannot be undone.");
        if (!confirmed) {
          return;
        }
      }
      markAction(documentId, "delete");
      setError(null);
      try {
        await deleteDocument(documentId);
        await refreshDocuments({ force: true });
      } catch (err) {
        setError((err as Error).message || "Removal failed");
      } finally {
        clearAction(documentId);
      }
    },
    [clearAction, markAction, refreshDocuments]
  );

  return (
    <div className="app-shell">
      <header>
        <div>
          <h1>Digital Inspector</h1>
          <p className="muted">Async PDF ingestion with ready-to-plug ML hooks.</p>
        </div>
        {isUploading && <div className="badge">Uploading…</div>}
      </header>

      {error && <div className="error-banner">{error}</div>}

      <UploadPanel disabled={isUploading} onUpload={handleUpload} />

      <section>
        <div className="section-header">
          <h2>Recent uploads</h2>
          <button onClick={() => void refreshDocuments({ force: true })} disabled={isUploading}>
            Refresh
          </button>
        </div>
        <div className="table-scroll">
          <DocumentTable
            documents={documents}
            onPreview={setSelectedId}
            onRetry={handleRetry}
            onDelete={handleDelete}
            pendingActions={pendingActions}
            selectedId={selectedDocument?.id ?? null}
          />
        </div>
      </section>

      <section className="viewer-section">
        <div className="section-header">
          <h2>PDF viewer</h2>
          {selectedDocument ? (
            <span className="muted">Showing {selectedDocument.file_name}</span>
          ) : (
            <span className="muted">Select a processed document to visualize detections.</span>
          )}
        </div>
        <PdfViewer document={selectedDocument} />
      </section>
    </div>
  );
}

function fingerprintDocuments(documents: DocumentRecord[]): string {
  return JSON.stringify(
    documents.map((doc) => ({
      id: doc.id,
      status: doc.status,
      updated_at: doc.updated_at,
      detectionsCount: doc.detections?.length ?? 0,
      failure_reason: doc.failure_reason ?? null
    }))
  );
}
