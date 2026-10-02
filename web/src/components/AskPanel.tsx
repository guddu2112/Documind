import { useState } from "react";
import type { AskResponse, AskCitation } from "../types";
import { askQuestion } from "../api";

function CitationCard({ citation, index }: { citation: AskCitation; index: number }) {
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-700">
          [{index + 1}]{" "}
          <span className="uppercase text-blue-600">{citation.doc_type}</span>
        </span>
        <span className="text-xs text-gray-400">
          Score: {citation.score.toFixed(3)}
        </span>
      </div>
      <p className="text-xs text-gray-700 line-clamp-3">{citation.preview}</p>
      <p className="mt-1 text-[10px] text-gray-400 font-mono">{citation.id}</p>
    </div>
  );
}

export default function AskPanel() {
  const [question, setQuestion] = useState("");
  const [docType, setDocType] = useState<string>("");
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setResponse(null);
    try {
      const resp = await askQuestion(question, docType || undefined);
      setResponse(resp);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ask failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="mb-1 text-lg font-semibold text-gray-800">
        Ask (RAG)
      </h2>
      <p className="mb-4 text-xs text-gray-500">
        Ask a question — the answer is grounded in your indexed documents, with citations.
      </p>

      <form onSubmit={onAsk} className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. What are the confidentiality obligations?"
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        />
        <select
          value={docType}
          onChange={(e) => setDocType(e.target.value)}
          className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option value="">All types</option>
          <option value="rfp">RFP</option>
          <option value="contract">Contract</option>
          <option value="spec">Spec</option>
        </select>
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "..." : "Ask"}
        </button>
      </form>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {loading && (
        <p className="mt-4 text-sm text-gray-400 italic">
          Retrieving passages and asking the LLM…
        </p>
      )}

      {response && (
        <div className="mt-6 space-y-4">
          <div>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
              Answer
            </h3>
            <div className="rounded-lg border border-blue-100 bg-blue-50 p-4 text-sm text-gray-800 whitespace-pre-wrap">
              {response.answer || <em className="text-gray-400">(empty)</em>}
            </div>
          </div>

          {response.citations.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
                Sources ({response.citations.length})
              </h3>
              <div className="space-y-2">
                {response.citations.map((c, i) => (
                  <CitationCard key={`${c.id}-${i}`} citation={c} index={i} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
