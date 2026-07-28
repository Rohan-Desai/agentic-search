import type { Citation, AgentStep } from "../lib/api";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  steps?: AgentStep[];
  clarificationNeeded?: boolean;
  answerNotFound?: boolean;
  pending?: boolean;
}

export default function Message({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={`msg ${msg.role} fade-in`}>
      <div className="avatar">{isUser ? "You" : "AI"}</div>
      <div className="body">
        <div className="role">
          {isUser ? "You" : "Assistant"}
          {msg.clarificationNeeded && <span className="badge warn">needs clarification</span>}
          {msg.answerNotFound && <span className="badge info">no answer in docs</span>}
        </div>

        {msg.pending ? (
          <div className="typing">Thinking…</div>
        ) : (
          <div className="content">{msg.content}</div>
        )}

        {msg.citations && msg.citations.length > 0 && (
          <details className="disclosure">
            <summary>{msg.citations.length} citation{msg.citations.length > 1 ? "s" : ""}</summary>
            <div className="inner">
              {msg.citations.map((c, i) => (
                <div className="citation" key={`${c.chunk_id}-${i}`}>
                  <div className="file">
                    {c.filename}
                    {typeof c.score === "number" && (
                      <span style={{ color: "var(--text-faint)", fontWeight: 400 }}>
                        {" "}· {c.score.toFixed(2)}
                      </span>
                    )}
                  </div>
                  {c.snippet && <div className="snippet">{c.snippet}</div>}
                </div>
              ))}
            </div>
          </details>
        )}

        {msg.steps && msg.steps.length > 0 && (
          <details className="disclosure">
            <summary>Reasoning trace ({msg.steps.length} steps)</summary>
            <div className="inner">
              {msg.steps.map((s, i) => (
                <div className="step" key={i}>
                  <span className="kind">{s.kind}</span>
                  {s.name ? ` · ${s.name}` : ""}
                  {s.detail ? `: ${s.detail.slice(0, 240)}` : ""}
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}
