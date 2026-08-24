"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import CandidateCard from "@/components/CandidateCard";
import CandidateStatusLog from "@/components/CandidateStatusLog";
import JDFileUploader from "@/components/JDFileUploader";
import JobDescriptionForm from "@/components/JobDescriptionForm";
import StatusStrip from "@/components/StatusStrip";
import Uploader from "@/components/Uploader";
import { api } from "@/lib/api";
import { clearToken, getToken } from "@/lib/auth";
import { exportCsv, exportJson } from "@/lib/export";
import type { NormalizedRequirements, ParsedCandidate, SessionStatus, UploadResult } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

function compareCandidates(a: ParsedCandidate, b: ParsedCandidate): number {
  const aScore = a.status === "scored" ? a.score ?? 0 : -1;
  const bScore = b.status === "scored" ? b.score ?? 0 : -1;
  if (aScore !== bScore) return bScore - aScore;
  return (a.name ?? "").localeCompare(b.name ?? "");
}

export default function HomePage() {
  const router = useRouter();
  const [authReady, setAuthReady] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [normalized, setNormalized] = useState<NormalizedRequirements | null>(null);
  const [parsedCandidates, setParsedCandidates] = useState<ParsedCandidate[]>([]);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
    } else {
      setAuthReady(true);
    }
  }, [router]);

  const fetchParsedCandidates = useCallback(async (nextStatus: SessionStatus) => {
    const candidates: ParsedCandidate[] = [];
    for (const file of nextStatus.files) {
      if (file.status === "parsed" || file.status === "scored" || file.status === "scoring" || file.status === "score_failed") {
        try {
          const detail = await api.getCandidate(file.candidate_id);
          const parsed = detail.resume?.parsed_json;
          if (parsed) {
            const totalMonths = (parsed.experience || []).reduce(
              (sum, exp) => sum + (exp.duration_months || 0),
              0
            );
            const experienceYears = Math.round((totalMonths / 12) * 10) / 10;
            const match = detail.match && "score" in (detail.match as Record<string, unknown>)
              ? (detail.match as { score: number })
              : null;

            candidates.push({
              candidate_id: file.candidate_id,
              name: parsed.candidate?.name || null,
              email: parsed.candidate?.contact?.email || null,
              phone: parsed.candidate?.contact?.phone || null,
              location: parsed.candidate?.location || null,
              skills: parsed.skills || [],
              experience_years: experienceYears,
              experience: parsed.experience || [],
              education: parsed.education || [],
              status: file.status as ParsedCandidate["status"],
              score: match?.score,
              filename: file.filename,
            });
          }
        } catch {
          // Skip candidates that fail to load
        }
      }
    }
    setParsedCandidates(candidates);
  }, []);

  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
  }, []);

  const poll = useCallback(async () => {
    if (!sessionId || !mountedRef.current) return;
    try {
      const nextStatus = await api.getSessionStatus(sessionId);
      if (!mountedRef.current) return;
      setStatus((current) =>
        current && JSON.stringify(current) === JSON.stringify(nextStatus) ? current : nextStatus
      );
      await fetchParsedCandidates(nextStatus);
      if (!mountedRef.current) return;
      const pending = Object.entries(nextStatus.counts).some(
        ([stage, count]) => count > 0 && !["scored", "failed"].includes(stage)
      );
      if (pending) {
        pollTimer.current = setTimeout(() => void poll(), POLL_INTERVAL_MS);
      }
    } catch {
      if (mountedRef.current) {
        pollTimer.current = setTimeout(() => void poll(), POLL_INTERVAL_MS * 3);
      }
    }
  }, [sessionId, fetchParsedCandidates]);

  useEffect(() => {
    if (!sessionId) return;
    void poll();
  }, [sessionId, poll]);

  function handleSessionCreated(id: string) {
    setSessionId(id);
  }

  function handleUploaded(_result: UploadResult) {
    setErrorBanner(null);
    void poll();
  }

  function handleLogout() {
    clearToken();
    router.replace("/login");
  }

  if (!authReady) {
    return null;
  }

  const sortedCandidates = [...parsedCandidates].sort(compareCandidates);
  const pendingCount = status
    ? Object.entries(status.counts)
        .filter(([stage, count]) => count > 0 && !["scored", "failed"].includes(stage))
        .reduce((sum, [, count]) => sum + count, 0)
    : 0;

  return (
    <div className="max-w-[1280px] mx-auto p-6 grid gap-8">
      <header className="flex flex-wrap justify-between items-center gap-3 border-b border-border pb-4">
        <h1 className="text-[22px] font-semibold tracking-tight text-text">
          Smart Resume Screener
        </h1>
        <button
          type="button"
          className="text-sm text-text-secondary hover:text-text transition-colors"
          onClick={handleLogout}
        >
          Log out
        </button>
      </header>

      <div className="grid gap-8 items-start lg:grid-cols-[360px_1fr]">
        <aside className="flex flex-col gap-5 lg:sticky lg:top-6">
          <JobDescriptionForm
            sessionId={sessionId}
            onSessionCreated={handleSessionCreated}
            onNormalized={setNormalized}
            onSubmitted={() => {
              setErrorBanner(null);
              void poll();
            }}
          />
          <JDFileUploader
            sessionId={sessionId}
            onSessionCreated={handleSessionCreated}
            onNormalized={setNormalized}
            onUploaded={() => {
              setErrorBanner(null);
              void poll();
            }}
          />
          <Uploader sessionId={sessionId} onUploaded={handleUploaded} />
          <CandidateStatusLog status={status} />
        </aside>

        <main className="grid gap-5 min-w-0" aria-label="Screening results">
          {errorBanner && (
            <div className="px-4 py-3 rounded-lg bg-error/10 border border-error text-error text-sm" role="alert">
              {errorBanner}
            </div>
          )}

          {normalized && (
            <div className="glass p-4 space-y-2">
              {normalized.title && (
                <p className="font-data font-medium text-text text-sm">{normalized.title}</p>
              )}
              <p className="text-sm text-text-secondary">
                Required: {normalized.required.map((r) => r.name).join(", ") || "none stated"} ·{" "}
                Preferred: {normalized.preferred.map((r) => r.name).join(", ") || "none stated"}
              </p>
              {normalized.ambiguities.length > 0 && (
                <p className="text-xs text-warning">
                  Ambiguous items were treated as preferred — review before scoring.
                </p>
              )}
            </div>
          )}

          {status && pendingCount > 0 && (
            <StatusStrip total={status.total} counts={status.counts} />
          )}

          {sortedCandidates.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-sm font-medium text-text">
                Candidates {pendingCount > 0 ? `· processing ${pendingCount}…` : ""}
              </h2>
              <div className="space-y-2">
                {sortedCandidates.map((candidate, index) => (
                  <CandidateCard key={candidate.candidate_id} candidate={candidate} rank={index + 1} />
                ))}
              </div>
              {sortedCandidates.some((c) => c.status === "scored") && (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="px-4 py-2 rounded-lg bg-accent text-bg font-medium hover:bg-accent-hover transition-colors"
                    onClick={() => exportJson(sortedCandidates, sessionId ?? "")}
                  >
                    Export JSON
                  </button>
                  <button
                    type="button"
                    className="px-4 py-2 rounded-lg bg-accent text-bg font-medium hover:bg-accent-hover transition-colors"
                    onClick={() => exportCsv(sortedCandidates)}
                  >
                    Export CSV
                  </button>
                </div>
              )}
            </div>
          )}

          {!sessionId && (
            <div className="px-4 py-3 rounded-lg bg-surface border border-border text-sm text-text-secondary" role="status">
              No candidates yet. Drop a job description to start, then add resumes.
            </div>
          )}

          {sessionId && !normalized && (
            <div className="px-4 py-3 rounded-lg bg-surface border border-border text-sm text-text-secondary" role="status">
              Waiting for a job description…
            </div>
          )}

          {sessionId && normalized && sortedCandidates.length === 0 && pendingCount === 0 && (
            <div className="px-4 py-3 rounded-lg bg-surface border border-border text-sm text-text-secondary" role="status">
              No resumes yet. Drop resume files on the uploader to score them against this role.
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
