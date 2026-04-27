import { useState } from "react";
import type { SearchResponse, SearchHit } from "../types";
import { search } from "../api";

function HitCard({ hit }: { hit: SearchHit }) {
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-xs font-medium uppercase text-blue-600">
          {hit.doc_type}
        </span>
        <span className="text-xs text-gray-400">
          Score: {hit.score.toFixed(3)}
        </span>
      </div>
      <p className="text-sm text-gray-700 line-clamp-4">{hit.content}</p>
      <p className="mt-1 text-[10px] text-gray-400 font-mono">{hit.id}</p>
    </div>
  );
}

export default function SearchPanel() {
  const [query, setQuery] = useState("");
  const [docType, setDocType] = useState<string>("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const resp = await search(query, docType || undefined);
      setResults(resp);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold text-gray-800">
        Semantic Search
      </h2>

      <form onSubmit={onSearch} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search across all processed documents..."
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
          disabled={searching || !query.trim()}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {searching ? "..." : "Search"}
        </button>
      </form>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {results && (
        <div className="mt-4">
          <p className="mb-3 text-xs text-gray-500">
            {results.total} result{results.total !== 1 ? "s" : ""} for "
            {results.query}"
          </p>
          {results.results.length > 0 ? (
            <div className="space-y-2">
              {results.results.map((hit) => (
                <HitCard key={hit.id} hit={hit} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400 italic">No results found.</p>
          )}
        </div>
      )}
    </div>
  );
}
