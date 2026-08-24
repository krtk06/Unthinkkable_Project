"use client";

import { useCallback, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { NormalizedRequirements } from "@/lib/types";
import { FileUpload } from "./ui/file-upload";
import { GridPatternCard, GridPatternCardBody } from "./ui/grid-pattern-card";
import { ShiningText } from "./ui/shining-text";

interface JDFileUploaderProps {
  sessionId: string | null;
  onSessionCreated: (sessionId: string) => void;
  onNormalized: (requirements: NormalizedRequirements) => void;
  onUploaded?: () => void;
}

const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".txt"];
const MAX_FILE_BYTES = 10 * 1024 * 1024;

function extensionOf(filename: string): string {
  const index = filename.lastIndexOf(".");
  return index === -1 ? "" : filename.slice(index).toLowerCase();
}

export default function JDFileUploader({
  sessionId,
  onSessionCreated,
  onNormalized,
  onUploaded,
}: JDFileUploaderProps) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const upload = useCallback(
    async (selected: File) => {
      setBusy(true);
      setError(null);
      try {
        let currentSessionId = sessionId;
        if (!currentSessionId) {
          const created = await api.createSession();
          currentSessionId = created.session_id;
          onSessionCreated(currentSessionId);
        }
        const result = await api.uploadJobDescriptionFile(currentSessionId, selected);
        onNormalized(result.normalized_requirements);
        onUploaded?.();
      } catch (err) {
        setError(
          err instanceof ApiError
            ? `${err.code}: ${err.message}`
            : "Could not analyze the job description. Check that the API is running."
        );
      } finally {
        setBusy(false);
      }
    },
    [sessionId, onSessionCreated, onNormalized, onUploaded]
  );

  const handleFiles = useCallback(
    (incoming: File[]) => {
      const file = incoming[0];
      if (!file) return;
      setError(null);
      const ext = extensionOf(file.name);
      if (!ACCEPTED_EXTENSIONS.includes(ext)) {
        setError(`Unsupported file type. Accepted: ${ACCEPTED_EXTENSIONS.join(", ")}`);
        return;
      }
      if (file.size === 0) {
        setError("File is empty.");
        return;
      }
      if (file.size > MAX_FILE_BYTES) {
        setError("File exceeds 10 MB limit.");
        return;
      }
      void upload(file);
    },
    [upload]
  );

  return (
    <GridPatternCard className="flex flex-col min-h-[280px]">
      <GridPatternCardBody className="flex flex-col flex-1 p-0">
        <div className="flex items-start justify-between gap-2 p-5 pb-2">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-zinc-200" id="jd-upload-title">
              Upload Files
            </h2>
            <p className="mt-0.5 text-xs text-zinc-500">Upload Job Description</p>
          </div>
          <span className="rounded bg-zinc-900 px-1.5 py-0.5 font-data text-[10px] tracking-widest text-zinc-500 ring-1 ring-white/[0.06]">JD · FILE</span>
        </div>

        <div className="flex-1 px-3 pb-3">
          <div className="rounded-xl border border-dashed border-white/10 bg-zinc-900/30">
            <FileUpload onChange={handleFiles} accept=".pdf,.docx,.txt" />
          </div>
        </div>

        <div className="px-5 pb-4">
          {busy && (
            <p className="mt-2 text-sm">
              <ShiningText text="Analyzing…" className="text-sm font-medium" />
            </p>
          )}
          {error && (
            <p className="mt-2 text-error text-sm" role="alert">
              {error}
            </p>
          )}
        </div>
      </GridPatternCardBody>
    </GridPatternCard>
  );
}
