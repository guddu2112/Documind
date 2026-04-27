import { useState, useCallback } from "react";
import type { UploadResponse, DocumentStatus } from "./types";
import UploadPanel from "./components/UploadPanel";
import StatusTracker from "./components/StatusTracker";
import AnalysisView from "./components/AnalysisView";
import SearchPanel from "./components/SearchPanel";

type Tab = "upload" | "status" | "search";

export default function App() {
  const [tab, setTab] = useState<Tab>("upload");
  const [activeDoc, setActiveDoc] = useState<{
    id: string;
    docType: string;
  } | null>(null);
  const [showAnalysis, setShowAnalysis] = useState(false);

  const onUploaded = useCallback((resp: UploadResponse) => {
    setActiveDoc({ id: resp.document_id, docType: resp.doc_type });
    setShowAnalysis(false);
    setTab("status");
  }, []);

  const onCompleted = useCallback((_status: DocumentStatus) => {
    setShowAnalysis(true);
  }, []);

  const tabs: { key: Tab; label: string }[] = [
    { key: "upload", label: "Upload" },
    { key: "status", label: "Status & Analysis" },
    { key: "search", label: "Search" },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-4">
          <h1 className="text-xl font-bold text-gray-900">
            📄 DocuMind
          </h1>
          <span className="text-xs text-gray-400">
            Intelligent Document Processing
          </span>
        </div>
      </header>

      {/* Nav */}
      <nav className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-4xl gap-1 px-4">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`border-b-2 px-4 py-3 text-sm font-medium transition
                ${
                  tab === t.key
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Content */}
      <main className="mx-auto max-w-4xl space-y-6 px-4 py-6">
        {tab === "upload" && <UploadPanel onUploaded={onUploaded} />}

        {tab === "status" && (
          <>
            {activeDoc ? (
              <>
                <StatusTracker
                  documentId={activeDoc.id}
                  onCompleted={onCompleted}
                />
                {showAnalysis && (
                  <AnalysisView
                    documentId={activeDoc.id}
                    docType={activeDoc.docType}
                  />
                )}
              </>
            ) : (
              <div className="rounded-xl border border-gray-200 bg-white p-8 text-center text-sm text-gray-400">
                No document uploaded yet. Go to Upload to get started.
              </div>
            )}
          </>
        )}

        {tab === "search" && <SearchPanel />}
      </main>
    </div>
  );
}
