import type {
  UploadResponse,
  DocumentStatus,
  AnalysisResponse,
  SearchResponse,
} from "./types";

const BASE = "";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function uploadDocument(
  file: File,
  docType: string
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("doc_type", docType);
  const res = await fetch(`${BASE}/documents`, { method: "POST", body: form });
  return json<UploadResponse>(res);
}

export async function getDocumentStatus(
  documentId: string
): Promise<DocumentStatus> {
  const res = await fetch(`${BASE}/documents/${documentId}`);
  return json<DocumentStatus>(res);
}

export async function getAnalysis(
  documentId: string,
  docType?: string
): Promise<AnalysisResponse> {
  const params = docType ? `?doc_type=${docType}` : "";
  const res = await fetch(`${BASE}/documents/${documentId}/analysis${params}`);
  return json<AnalysisResponse>(res);
}

export async function search(
  query: string,
  docType?: string,
  top = 10
): Promise<SearchResponse> {
  const body: Record<string, unknown> = { query, top };
  if (docType) body.doc_type = docType;
  const res = await fetch(`${BASE}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return json<SearchResponse>(res);
}
