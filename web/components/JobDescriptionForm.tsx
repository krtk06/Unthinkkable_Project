"use client";

import { useCallback, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { NormalizedRequirements } from "@/lib/types";

interface JobDescriptionFormProps {
  sessionId: string | null;
  onSessionCreated: (sessionId: string) => void;
  onNormalized: (requirements: NormalizedRequirements) => void;
  onSubmitted?: () => void;
}

export default function JobDescriptionForm({
  sessionId,
  onSessionCreated,
  onNormalized,
  onSubmitted,
}: JobDescriptionFormProps) {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = useCallback(async () => {
    const trimmed = text.trim();
    if (!trimmed) {
      setError("Enter a job description to continue.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let currentSessionId = sessionId;
      if (!currentSessionId) {
        const created = await api.createSession();
        currentSessionId = created.session_id;
        onSessionCreated(currentSessionId);
      }
      const result = await api.saveJobDescriptionText(
        currentSessionId,
        trimmed,
        title.trim() || undefined
      );
      onNormalized(result.normalized_requirements);
      onSubmitted?.();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `${err.code}: ${err.message}`
          : "Could not analyze the job description. Check that the API is running."
      );
    } finally {
      setBusy(false);
    }
  }, [sessionId, title, text, onSessionCreated, onNormalized, onSubmitted]);

  return (
    <section className="glass p-5 space-y-4" aria-labelledby="jd-form-title">
      <h2 className="text-base font-semibold tracking-tight text-text" id="jd-form-title">
        Job description
      </h2>

      <label className="block space-y-1">
        <span className="text-sm text-text-secondary">Role title</span>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Backend Software Engineer"
          className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-text placeholder:text-text-secondary/60 focus:border-accent"
        />
      </label>

      <label className="block space-y-1">
        <span className="text-sm text-text-secondary">Job description text</span>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste the full job description here..."
          rows={8}
          className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-text placeholder:text-text-secondary/60 focus:border-accent resize-y"
        />
      </label>

      {error && (
        <p className="text-error text-sm" role="alert">
          {error}
        </p>
      )}

      <button
        type="button"
        className="primaryButton w-full"
        onClick={() => void submit()}
        disabled={busy}
      >
        {busy ? "Filing job description…" : "File job description"}
      </button>
    </section>
  );
}
