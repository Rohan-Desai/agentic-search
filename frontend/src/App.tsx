import { useState } from "react";
import Sidebar from "./components/Sidebar";
import Message, { type ChatMessage } from "./components/Message";
import Composer from "./components/Composer";
import type { IngestedDocument, SearchMode, ConversationTurn } from "./lib/api";
import { search } from "./lib/api";

const MODES: { id: SearchMode; label: string }[] = [
  { id: "normal", label: "Normal" },
  { id: "agentic", label: "Agentic" },
  { id: "deep_research", label: "Deep research" },
];

const EXAMPLES = [
  "Summarize the key findings across all uploaded documents.",
  "What were the total figures reported, and where do they appear?",
  "Compare how two of the documents describe the same topic.",
];

export default function App() {
  const [documents, setDocuments] = useState<IngestedDocument[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [mode, setMode] = useState<SearchMode>("normal");
  const [busy, setBusy] = useState(false);

  function newChat() {
    setMessages([]);
  }

  async function handleSend(text: string) {
    const history: ConversationTurn[] = messages
      .filter((m) => !m.pending)
      .map((m) => ({ role: m.role, content: m.content }));

    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", content: text };
    const pendingMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      pending: true,
    };
    setMessages((prev) => [...prev, userMsg, pendingMsg]);
    setBusy(true);

    try {
      const res = await search(text, mode, history);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingMsg.id
            ? {
                ...m,
                pending: false,
                content: res.answer,
                citations: res.citations,
                steps: res.steps,
                clarificationNeeded: res.clarification_needed,
                answerNotFound: !res.answer_found,
              }
            : m,
        ),
      );
    } catch (e) {
      const message = e instanceof Error ? e.message : "Something went wrong.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingMsg.id
            ? { ...m, pending: false, content: `⚠ ${message}` }
            : m,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <Sidebar documents={documents} onIngested={(docs) => setDocuments((p) => [...p, ...docs])} />

      <div className="main">
        <header className="header">
          <div className="mode-tabs">
            {MODES.map((m) => (
              <button
                key={m.id}
                className={`mode-tab${mode === m.id ? " active" : ""}`}
                onClick={() => setMode(m.id)}
              >
                {m.label}
              </button>
            ))}
          </div>
          <button className="new-chat" onClick={newChat}>New chat</button>
        </header>

        <div className="messages">
          {messages.length === 0 ? (
            <div className="empty">
              <h2>Ask across your documents</h2>
              <p>
                Upload PDFs, Word docs, or spreadsheets on the left, then ask a question.
                Switch modes above to compare normal, agentic, and deep-research search.
              </p>
              <div className="examples">
                {EXAMPLES.map((ex) => (
                  <button key={ex} className="example" onClick={() => handleSend(ex)}>
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="thread">
              {messages.map((m) => (
                <Message key={m.id} msg={m} />
              ))}
            </div>
          )}
        </div>

        <Composer disabled={busy} onSend={handleSend} />
      </div>
    </div>
  );
}
