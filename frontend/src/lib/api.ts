// Typed client for the FastAPI backend. Mirrors app/models/schemas.py.

export type SearchMode = "normal" | "agentic" | "deep_research";

export interface Citation {
  doc_id: string;
  filename: string;
  chunk_id?: string | null;
  snippet?: string | null;
  score?: number | null;
  page?: number | null;
  sheet?: string | null;
  section?: string | null;
}

export interface AgentStep {
  kind: string;
  name?: string | null;
  detail?: string | null;
}

export interface IngestedDocument {
  doc_id: string;
  filename: string;
  doc_type: string;
  num_chunks: number;
}

export interface ConversationTurn {
  role: "user" | "assistant";
  content: string;
}

export interface SearchResponse {
  query: string;
  mode: SearchMode;
  answer: string;
  citations: Citation[];
  steps: AgentStep[];
  clarification_needed: boolean;
  answer_found: boolean;
  partial: boolean;
}

export async function uploadDocuments(files: File[]): Promise<IngestedDocument[]> {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  const res = await fetch("/documents/upload", { method: "POST", body: fd });
  if (!res.ok) throw new Error(`Upload failed (${res.status})`);
  const data = await res.json();
  return data.documents;
}

export async function search(
  query: string,
  mode: SearchMode,
  history: ConversationTurn[],
  topK = 8,
): Promise<SearchResponse> {
  const res = await fetch("/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, mode, top_k: topK, history }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail || `Search failed (${res.status})`);
  }
  return res.json();
}
