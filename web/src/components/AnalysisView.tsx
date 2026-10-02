import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import type { AnalysisResponse, RiskItem } from "../types";
import { getAnalysis } from "../api";

interface Props {
  documentId: string;
  docType: string;
}

function SeverityBadge({ severity }: { severity: RiskItem["severity"] }) {
  const colors: Record<string, string> = {
    critical: "bg-red-100 text-red-800",
    high: "bg-orange-100 text-orange-800",
    medium: "bg-yellow-100 text-yellow-800",
    low: "bg-green-100 text-green-800",
  };
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${colors[severity] ?? "bg-gray-100 text-gray-600"}`}
    >
      {severity}
    </span>
  );
}

function humanize(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function MetadataValue({ value }: { value: unknown }): ReactNode {
  if (value === null || value === undefined) {
    return <span className="text-gray-400 italic">—</span>;
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return <span>{String(value)}</span>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="text-gray-400 italic">(empty)</span>;
    }
    const allPrimitive = value.every(
      (v) => typeof v === "string" || typeof v === "number" || typeof v === "boolean"
    );
    if (allPrimitive) {
      return (
        <ul className="list-disc pl-5 space-y-0.5">
          {value.map((v, i) => (
            <li key={i}>{String(v)}</li>
          ))}
        </ul>
      );
    }
    return (
      <ul className="space-y-2">
        {value.map((v, i) => (
          <li key={i} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
            <MetadataValue value={v} />
          </li>
        ))}
      </ul>
    );
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    return (
      <div className="space-y-1">
        {entries.map(([k, v]) => (
          <div key={k} className="text-sm">
            <span className="font-medium text-gray-700">{humanize(k)}:</span>{" "}
            <span className="text-gray-600"><MetadataValue value={v} /></span>
          </div>
        ))}
      </div>
    );
  }
  return <span>{String(value)}</span>;
}

function StructuredMetadata({ metadata }: { metadata: Record<string, unknown> }) {
  const entries = Object.entries(metadata).filter(([, v]) => v !== null && v !== "");
  return (
    <div className="space-y-4">
      {entries.map(([key, value]) => (
        <section key={key}>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
            {humanize(key)}
          </h3>
          <div className="text-sm text-gray-700">
            <MetadataValue value={value} />
          </div>
        </section>
      ))}
    </div>
  );
}

export default function AnalysisView({ documentId, docType }: Props) {
  const [data, setData] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"summary" | "risks" | "extraction">(
    "summary"
  );

  useEffect(() => {
    getAnalysis(documentId, docType)
      .then(setData)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load analysis")
      );
  }, [documentId, docType]);

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }
  if (!data) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6 text-sm text-gray-500">
        Loading analysis...
      </div>
    );
  }

  const { analysis, extraction } = data;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold text-gray-800">
        Analysis Results
      </h2>

      {/* Tabs */}
      <div className="mb-4 flex gap-1 rounded-lg bg-gray-100 p-1">
        {(["summary", "risks", "extraction"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition
              ${tab === t ? "bg-white text-gray-800 shadow-sm" : "text-gray-500 hover:text-gray-700"}`}
          >
            {t === "summary"
              ? "Summary"
              : t === "risks"
                ? `Risks (${analysis?.risks?.length ?? 0})`
                : "Extraction"}
          </button>
        ))}
      </div>

      {/* Summary tab */}
      {tab === "summary" && (
        <div className="prose prose-sm max-w-none text-gray-700">
          {analysis?.summary ? (
            <p className="whitespace-pre-wrap">{analysis.summary}</p>
          ) : analysis?.metadata && Object.keys(analysis.metadata).length > 0 ? (
            <StructuredMetadata metadata={analysis.metadata} />
          ) : (
            <p className="text-gray-400 italic">No summary available.</p>
          )}
        </div>
      )}

      {/* Risks tab */}
      {tab === "risks" && (
        <div className="space-y-3">
          {analysis?.risks && analysis.risks.length > 0 ? (
            analysis.risks.map((risk, i) => (
              <div
                key={i}
                className="rounded-lg border border-gray-100 bg-gray-50 p-4"
              >
                <div className="mb-1 flex items-center gap-2">
                  <SeverityBadge severity={risk.severity} />
                  <span className="text-sm font-medium text-gray-800">
                    {risk.title}
                  </span>
                </div>
                <p className="text-sm text-gray-600">{risk.description}</p>
                {risk.recommendation && (
                  <p className="mt-2 text-xs text-blue-700">
                    💡 {risk.recommendation}
                  </p>
                )}
              </div>
            ))
          ) : (
            <p className="text-sm text-gray-400 italic">No risks identified.</p>
          )}
        </div>
      )}

      {/* Extraction tab */}
      {tab === "extraction" && (
        <div className="space-y-4">
          {extraction && (
            <div className="grid grid-cols-3 gap-3 text-sm">
              <div className="rounded-lg bg-blue-50 p-3 text-center">
                <div className="text-2xl font-bold text-blue-700">
                  {extraction.page_count}
                </div>
                <div className="text-xs text-blue-500">Pages</div>
              </div>
              <div className="rounded-lg bg-purple-50 p-3 text-center">
                <div className="text-2xl font-bold text-purple-700">
                  {extraction.key_value_pairs.length}
                </div>
                <div className="text-xs text-purple-500">Key-Value Pairs</div>
              </div>
              <div className="rounded-lg bg-teal-50 p-3 text-center">
                <div className="text-2xl font-bold text-teal-700">
                  {extraction.tables.length}
                </div>
                <div className="text-xs text-teal-500">Tables</div>
              </div>
            </div>
          )}

          {/* Tables */}
          {extraction?.tables?.map((table) => (
            <div key={table.table_id} className="overflow-x-auto">
              <p className="mb-1 text-xs font-medium text-gray-500">
                Table {table.table_id + 1}
                {table.page != null && ` · Page ${table.page}`}
              </p>
              <table className="min-w-full border-collapse text-xs">
                {table.headers.length > 0 && (
                  <thead>
                    <tr>
                      {table.headers.map((h, j) => (
                        <th
                          key={j}
                          className="border border-gray-200 bg-gray-100 px-2 py-1 text-left font-semibold"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody>
                  {table.rows.map((row, ri) => (
                    <tr key={ri}>
                      {row.map((cell, ci) => (
                        <td
                          key={ci}
                          className="border border-gray-200 px-2 py-1"
                        >
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}

          {/* Key-value pairs */}
          {extraction?.key_value_pairs &&
            extraction.key_value_pairs.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium text-gray-500">
                  Key-Value Pairs
                </p>
                <div className="grid grid-cols-2 gap-1 text-xs">
                  {extraction.key_value_pairs.map((kv, i) => (
                    <div key={i} className="flex gap-1">
                      <span className="font-medium text-gray-700">
                        {kv.key}:
                      </span>
                      <span className="text-gray-600">{kv.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
        </div>
      )}
    </div>
  );
}
