import type { DocumentRecord } from "../types";

const API_BASE_URL = resolveApiBaseUrl();

function resolveApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl) {
    return envUrl.replace(/\/$/, "");
  }

  if (typeof window !== "undefined") {
    const { protocol, hostname, port } = window.location;
    const inferredPort = port === "5173" ? "8000" : port;
    const portSegment = inferredPort ? `:${inferredPort}` : "";
    return `${protocol}//${hostname}${portSegment}/api`.replace(/\/$/, "");
  }

  return "/api";
}

export function buildApiUrl(path = ""): string {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  const normalizedBase = API_BASE_URL.replace(/\/$/, "");
  if (!path) {
    return normalizedBase;
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizedBase}${normalizedPath}`;
}

async function handleResponse<T = unknown>(response: Response): Promise<T> {
  const raw = await response.text();
  if (!response.ok) {
    throw new Error(raw || "Request failed");
  }
  if (!raw) {
    return undefined as T;
  }
  try {
    return JSON.parse(raw) as T;
  } catch (error) {
    return raw as T;
  }
}

export async function uploadDocuments(files: File[]): Promise<DocumentRecord[]> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const response = await fetch(buildApiUrl("/documents/upload"), {
    method: "POST",
    body: formData
  });

  const payload = await handleResponse<{ documents: DocumentRecord[] }>(response);
  return payload.documents as DocumentRecord[];
}

export async function fetchDocuments(): Promise<DocumentRecord[]> {
  const response = await fetch(buildApiUrl("/documents"));
  const payload = await handleResponse<{ documents: DocumentRecord[] }>(response);
  return payload.documents as DocumentRecord[];
}

export async function retryDocument(documentId: string): Promise<DocumentRecord> {
  const response = await fetch(buildApiUrl(`/documents/${documentId}/retry`), {
    method: "POST"
  });
  return handleResponse<DocumentRecord>(response);
}

export async function deleteDocument(documentId: string): Promise<void> {
  const response = await fetch(buildApiUrl(`/documents/${documentId}`), {
    method: "DELETE"
  });
  await handleResponse(response);
}
