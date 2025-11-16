export type DocumentStatus =
  | "pending"
  | "processing"
  | "succeeded"
  | "failed"
  | "upload_failed"
  | "processing_failed";

export interface Detection {
  label: string;
  confidence: number;
  bounding_box: [number, number, number, number];
  page?: number | null;
  page_width?: number | null;
  page_height?: number | null;
}

export interface DocumentRecord {
  id: string;
  file_name: string;
  status: DocumentStatus;
  created_at: string;
  updated_at: string;
  detections?: Detection[] | null;
  failure_reason?: string | null;
  download_url?: string | null;
}
