import { useCallback, useRef, useState } from "react";

interface UploadPanelProps {
  disabled?: boolean;
  onUpload: (files: File[]) => Promise<void> | void;
}

export function UploadPanel({ disabled = false, onUpload }: UploadPanelProps) {
  const [localFiles, setLocalFiles] = useState<File[]>([]);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const handleFiles = useCallback(
    async (incoming: FileList | File[]) => {
      const validFiles: File[] = [];
      Array.from(incoming).forEach((file) => {
        if (file.type === "application/pdf" || file.name.endsWith(".pdf")) {
          validFiles.push(file);
        }
      });
      if (validFiles.length) {
        setLocalFiles(validFiles);
        await onUpload(validFiles);
        setLocalFiles([]);
        if (inputRef.current) {
          inputRef.current.value = "";
        }
      }
    },
    [onUpload]
  );

  const onInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      void handleFiles(event.target.files);
    }
  };

  const onDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (disabled) return;
    if (event.dataTransfer.files) {
      void handleFiles(event.dataTransfer.files);
    }
  };

  const onDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
  };

  const openFilePicker = () => {
    if (!disabled) {
      inputRef.current?.click();
    }
  };

  return (
    <div className="upload-panel" onDrop={onDrop} onDragOver={onDragOver}>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        multiple
        onChange={onInputChange}
        disabled={disabled}
        style={{ display: "none" }}
      />
      <p>Drag & drop PDFs here or use the button below.</p>
      <button type="button" onClick={openFilePicker} disabled={disabled}>
        Select PDFs
      </button>
      {localFiles.length > 0 && (
        <ul>
          {localFiles.map((file) => (
            <li key={file.name}>{file.name}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
