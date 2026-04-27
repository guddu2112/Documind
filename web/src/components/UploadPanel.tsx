import { useState, useRef, useCallback } from "react";
import type { UploadResponse } from "../types";
import { uploadDocument } from "../api";

interface Props {
  onUploaded: (resp: UploadResponse) => void;
}

const DOC_TYPES = ["auto", "rfp", "contract", "spec"] as const;

export default function UploadPanel({ onUploaded }: Props) {
  const [docType, setDocType] = useState<string>("auto");
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File) => {
    setFile(f);
    setError(null);
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, []);

  const onSubmit = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const resp = await uploadDocument(file, docType);
      onUploaded(resp);
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold text-gray-800">
        Upload Document
      </h2>

      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition
          ${dragging ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-gray-400"}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.xlsx,.pptx,.png,.jpg,.tiff"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
          }}
        />
        {file ? (
          <p className="text-sm text-gray-700">
            <span className="font-medium">{file.name}</span>{" "}
            <span className="text-gray-400">
              ({(file.size / 1024 / 1024).toFixed(1)} MB)
            </span>
          </p>
        ) : (
          <p className="text-sm text-gray-500">
            Drag &amp; drop a file here, or click to browse
          </p>
        )}
      </div>

      {/* Controls */}
      <div className="mt-4 flex items-center gap-3">
        <select
          value={docType}
          onChange={(e) => setDocType(e.target.value)}
          className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        >
          {DOC_TYPES.map((t) => (
            <option key={t} value={t}>
              {t === "auto" ? "Auto-detect" : t.toUpperCase()}
            </option>
          ))}
        </select>

        <button
          onClick={onSubmit}
          disabled={!file || uploading}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {uploading ? "Uploading..." : "Upload"}
        </button>
      </div>

      {error && (
        <p className="mt-3 text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}
