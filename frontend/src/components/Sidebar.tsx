import { useRef, useState } from "react";
import type { IngestedDocument } from "../lib/api";
import { uploadDocuments } from "../lib/api";

interface Props {
  documents: IngestedDocument[];
  onIngested: (docs: IngestedDocument[]) => void;
}

export default function Sidebar({ documents, onIngested }: Props) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      const docs = await uploadDocuments(Array.from(files));
      onIngested(docs);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <aside className="sidebar">
      <div className="brand">Agentic Search</div>
      <div className="brand-sub">Ask questions across your documents.</div>

      <div className="section-label">Documents</div>
      <div
        className={`dropzone${dragging ? " drag" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
      >
        {uploading ? (
          "Ingesting…"
        ) : (
          <>
            Drop PDFs, Word docs, or spreadsheets here, or{" "}
            <label onClick={() => inputRef.current?.click()}>browse</label>.
            <input
              ref={inputRef}
              type="file"
              multiple
              accept=".pdf,.docx,.doc,.xlsx,.xls,.csv"
              onChange={(e) => handleFiles(e.target.files)}
            />
          </>
        )}
      </div>

      {error && <div className="error" style={{ marginTop: 10 }}>{error}</div>}

      <div className="doc-list">
        {documents.map((d) => (
          <div className="doc" key={d.doc_id}>
            <div className="doc-name">{d.filename}</div>
            <div className="doc-meta">
              {d.doc_type} · {d.num_chunks} chunks · {d.doc_id}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
