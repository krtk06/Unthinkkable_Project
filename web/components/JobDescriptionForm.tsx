"use client";

import { useCallback, useState } from "react";
import { motion } from "framer-motion";
import { api, ApiError } from "@/lib/api";
import type { NormalizedRequirements } from "@/lib/types";
import { GridPatternCard, GridPatternCardBody } from "./ui/grid-pattern-card";
import { RainbowButton } from "./ui/rainbow-button";
import { ShiningText } from "./ui/shining-text";

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
    <GridPatternCard className="flex flex-col min-h-[280px]">
      <GridPatternCardBody className="flex flex-col flex-1">
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-base font-semibold tracking-tight text-zinc-200" id="jd-form-title">
            Job description
          </h2>
          <span className="rounded bg-zinc-900 px-1.5 py-0.5 font-data text-[10px] tracking-widest text-zinc-500 ring-1 ring-white/[0.06]">JD · TEXT</span>
        </div>

        <label className="mt-4 block space-y-1">
          <span className="text-sm text-zinc-400">Role title</span>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Senior Backend Software Engineer"
            className="w-full rounded-lg bg-zinc-900 border border-white/5 px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-500 focus:border-white/10 focus:ring-1 focus:ring-white/10 outline-none transition-colors"
          />
        </label>

        <label className="mt-3 block flex-1 space-y-1">
          <span className="text-sm text-zinc-400">Job description text</span>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste the full job description here..."
            rows={8}
            className="h-full min-h-40 w-full rounded-lg bg-zinc-900 border border-white/5 px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-500 focus:border-white/10 focus:ring-1 focus:ring-white/10 outline-none resize-y transition-colors"
          />
        </label>

        {error && (
          <motion.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-2 text-error text-sm"
            role="alert"
          >
            {error}
          </motion.p>
        )}

        <RainbowButton
          type="button"
          className="mt-5 w-full"
          onClick={() => void submit()}
          disabled={busy}
        >
          {busy ? <ShiningText text="Filing job description…" className="text-sm" /> : "File job description"}
        </RainbowButton>
      </GridPatternCardBody>
    </GridPatternCard>
  );
}
