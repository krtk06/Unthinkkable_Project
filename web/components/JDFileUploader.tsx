"use client";

import { useCallback, useId, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { NormalizedRequirements } from "@/lib/types";

interface JDFileUploaderProps {
  sessionId: string | null;
  onSessionCreated: (sessionId: string) => void;
  onNormalized: (requirements: NormalizedRequirements) => void;
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
}: JDFileUploaderProps) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();

  const handleFile = useCallback((file: File) => {
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
    setSelectedFile(file);
  }, []);

  function handleDrop(event: React.DragEvent) {
    event.preventDefault();
    setDragActive(false);
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) {
      handleFile(files[0]);
    }
  }

  async function handleAnalyze() {
    if (!selectedFile) return;
    setBusy(true);
    setError(null);
    try {
      let currentSessionId = sessionId;
      if (!currentSessionId) {
        const created = await api.createSession();
        currentSessionId = created.session_id;
        onSessionCreated(currentSessionId);
      }
      const result = await api.uploadJobDescriptionFile(currentSessionId, selectedFile);
      onNormalized(result.normalized_requirements);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `${err.code}: ${err.message}`
          : "Could not analyze the job description. Check that the API is running."
      );
    } finally {
      setBusy(false);
    }
  }

  function handleRemove() {
    setSelectedFile(null);
    setError(null);
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  return (
    <section className="glass p-5" aria-labelledby="jd-upload-title">
      <h2 className="text-base font-semibold tracking-tight text-text mb-4" id="jd-upload-title">
        Job description
      </h2>

      {!selectedFile ? (
        <div
          className={`border-2 border-dashed rounded-xl p-5 text-center transition-all duration-150 cursor-pointer ${
            dragActive
              ? "border-accent bg-accent/5 shadow-[0_0_20px_4px_rgba(52,211,153,0.1)]"
              : "border-border bg-surface hover:border-border-hover"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          role="button"
          tabIndex={0}
          aria-label="Drop a job description file or click to browse"
        >
          <input
            ref={inputRef}
            id={inputId}
            type="file"
            accept=".pdf,.docx,.txt"
            className="visuallyHidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(file);
              e.target.value = "";
            }}
          />
          <div className="text-text-secondary text-sm">
            <p className="mb-1">Drop a job description here or <span className="text-accent underline">browse files</span></p>
            <p className="text-xs text-text-secondary/60">PDF, DOCX, or TXT. Up to 10 MB.</p>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3 px-3 py-2 bg-bg/60 rounded-lg">
            <div className="min-w-0">
              <p className="text-sm text-text truncate">{selectedFile.name}</p>
              <p className="text-xs text-text-secondary">{formatSize(selectedFile.size)}</p>
            </div>
            <button
              type="button"
              className="text-xs text-text-secondary hover:text-text transition-colors shrink-0"
              onClick={handleRemove}
            >
              Remove
            </button>
          </div>
          <button
            type="button"
            className="w-full px-4 py-2 rounded-lg bg-accent text-bg font-medium hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => void handleAnalyze()}
            disabled={busy}
          >
            {busy ? "Analyzing…" : "Analyze job description"}
          </button>
        </div>
      )}

      {error && (
        <p className="text-error text-sm mt-2" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
