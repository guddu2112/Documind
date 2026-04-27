import { useEffect, useState, useRef } from "react";
import type { DocumentStatus, ProcessingStatus } from "../types";
import { getDocumentStatus } from "../api";

interface Props {
  documentId: string;
  onCompleted: (status: DocumentStatus) => void;
}

const STAGES: { key: string; label: string; after: ProcessingStatus }[] = [
  { key: "ingestion", label: "Ingestion", after: "pending" },
  { key: "extraction", label: "Extraction", after: "extracting" },
  { key: "analysis", label: "Analysis", after: "analyzing" },
  { key: "search", label: "Search Indexing", after: "indexing" },
];

function stageState(
  status: ProcessingStatus,
  completed: string[],
  stageKey: string,
  afterStatus: ProcessingStatus
): "done" | "active" | "pending" {
  if (completed.includes(stageKey)) return "done";
  if (status === afterStatus) return "active";
  return "pending";
}

export default function StatusTracker({ documentId, onCompleted }: Props) {
  const [status, setStatus] = useState<DocumentStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval>>(null);
  const onCompletedRef = useRef(onCompleted);
  onCompletedRef.current = onCompleted;
  const doneRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    doneRef.current = false;

    const poll = async () => {
      if (doneRef.current) return;
      try {
        const s = await getDocumentStatus(documentId);
        if (cancelled) return;
        setStatus(s);
        if (s.status === "completed" || s.status === "failed") {
          doneRef.current = true;
          if (intervalRef.current) clearInterval(intervalRef.current);
          if (s.status === "completed") onCompletedRef.current(s);
        }
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Polling failed");
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 2000);

    return () => {
      cancelled = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [documentId]);

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!status) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6 text-sm text-gray-500">
        Loading status...
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-800">
          Pipeline Progress
        </h2>
        <span className="text-xs text-gray-400 font-mono">{documentId}</span>
      </div>

      {status.filename && (
        <p className="mb-4 text-sm text-gray-600">
          File: <span className="font-medium">{status.filename}</span>
          {" · "}
          Type: <span className="font-medium uppercase">{status.doc_type}</span>
        </p>
      )}

      {/* Stage progress */}
      <div className="flex items-center gap-2">
        {STAGES.map((stage, i) => {
          const state = stageState(
            status.status,
            status.stages_completed,
            stage.key,
            stage.after
          );
          return (
            <div key={stage.key} className="flex items-center gap-2">
              <div className="flex flex-col items-center">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold transition
                    ${state === "done" ? "bg-green-500 text-white" : ""}
                    ${state === "active" ? "bg-blue-500 text-white animate-pulse" : ""}
                    ${state === "pending" ? "bg-gray-200 text-gray-400" : ""}`}
                >
                  {state === "done" ? "✓" : i + 1}
                </div>
                <span className="mt-1 text-[10px] text-gray-500">
                  {stage.label}
                </span>
              </div>
              {i < STAGES.length - 1 && (
                <div
                  className={`h-0.5 w-6 ${
                    state === "done" ? "bg-green-400" : "bg-gray-200"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>

      {status.status === "failed" && (
        <p className="mt-4 text-sm text-red-600">
          {status.error_message ?? "Processing failed."}
        </p>
      )}

      {status.status === "completed" && (
        <p className="mt-4 text-sm text-green-600 font-medium">
          ✓ Pipeline completed
        </p>
      )}
    </div>
  );
}
