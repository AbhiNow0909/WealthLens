"use client";

import { useEffect, useRef, useState } from "react";

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

interface Props {
  messages: ChatMessage[];
  onSend: (prompt: string) => void;
  sending: boolean;
}

export default function ChatPanel({ messages, onSend, sending }: Props) {
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const prompt = input.trim();
    if (!prompt || sending) return;
    onSend(prompt);
    setInput("");
  }

  return (
    <div className="flex flex-col h-[60vh] bg-[var(--surface)] border border-[var(--border)] rounded-xl overflow-hidden">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center">
            <p className="text-[var(--text-primary)] text-sm font-medium mb-2">
              Ask anything about your portfolio
            </p>
            <p className="text-[var(--text-secondary)] text-xs max-w-sm">
              e.g. &ldquo;How is my portfolio doing?&rdquo;, &ldquo;Which fund is my biggest
              risk?&rdquo;, or &ldquo;Should I rebalance?&rdquo;
            </p>
          </div>
        ) : (
          messages.map((m, i) => (
            <div
              key={i}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-xl px-4 py-3 text-sm whitespace-pre-wrap leading-relaxed ${
                  m.role === "user"
                    ? "bg-[var(--accent)] text-white"
                    : "bg-[var(--bg)] text-[var(--text-primary)] border border-[var(--border)]"
                }`}
              >
                {m.text}
              </div>
            </div>
          ))
        )}
        {sending && (
          <div className="flex justify-start">
            <div className="bg-[var(--bg)] border border-[var(--border)] rounded-xl px-4 py-3 text-sm text-[var(--text-secondary)]">
              Thinking…
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <form onSubmit={submit} className="border-t border-[var(--border)] p-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your portfolio…"
          className="flex-1 bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:outline-none focus:border-[var(--accent)]"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium disabled:opacity-40 transition-opacity"
        >
          Send
        </button>
      </form>
    </div>
  );
}
