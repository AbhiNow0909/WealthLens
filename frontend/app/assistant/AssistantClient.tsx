"use client";

import { useState } from "react";
import Link from "next/link";
import { runAgent } from "@/lib/api";
import ChatPanel, { type ChatMessage } from "@/components/assistant/ChatPanel";
import ExportButton from "@/components/assistant/ExportButton";

export default function AssistantClient() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);

  async function handleSend(prompt: string) {
    setMessages((m) => [...m, { role: "user", text: prompt }]);
    setSending(true);
    try {
      const res = await runAgent(prompt);
      setMessages((m) => [
        ...m,
        { role: "assistant", text: res.response_text || "I couldn't generate a response." },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: "Something went wrong. Please try again." },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg)]">
      <nav className="border-b border-[var(--border)] px-6 py-4 flex items-center justify-between">
        <span className="text-[var(--text-primary)] font-semibold tracking-tight">WealthLens</span>
        <div className="flex items-center gap-6 text-sm text-[var(--text-secondary)]">
          <Link href="/dashboard" className="hover:text-[var(--text-primary)] transition-colors">Portfolio</Link>
          <Link href="/compare" className="hover:text-[var(--text-primary)] transition-colors">Compare</Link>
          <Link href="/assistant" className="text-[var(--text-primary)]">Assistant</Link>
        </div>
      </nav>

      <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)] mb-1">AI Assistant</h1>
          <p className="text-[var(--text-secondary)] text-sm">
            Ask about your portfolio, or export a full report.
          </p>
        </div>

        <ChatPanel messages={messages} onSend={handleSend} sending={sending} />

        {/* Export */}
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5">
          <h2 className="text-sm font-medium text-[var(--text-primary)] mb-1">Export report</h2>
          <p className="text-xs text-[var(--text-secondary)] mb-4">
            Generate a full portfolio report with metrics and AI analysis.
          </p>
          <div className="flex flex-wrap gap-3">
            <ExportButton format="excel" />
            <ExportButton format="word" />
            <ExportButton format="ppt" />
          </div>
        </div>
      </div>
    </div>
  );
}
