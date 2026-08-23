"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import CandidateDetail from "@/components/CandidateDetail";
import FilterBar, { DEFAULT_FILTERS, type FilterState } from "@/components/FilterBar";
import JDFileUploader from "@/components/JDFileUploader";
import MatchTable from "@/components/MatchTable";
import StatusStrip from "@/components/StatusStrip";
import Uploader from "@/components/Uploader";
import { api } from "@/lib/api";
import { exportCsv, exportJson } from "@/lib/export";
import type { Match, NormalizedRequirements, SessionStatus, UploadResult } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

function buildQuery(filters: FilterState) {
  return {
    ...(filters.mode === "threshold" ? { threshold: filters.threshold } : { top_n: filters.topN }),
    min_required_coverage: filters.minRequiredCoverage,
    min_experience_months: filters.minExperienceMonths ?? undefined,
    work_mode: filters.workMode || undefined,
    location: filters.location || undefined,
    ...(filters.requiredSkillsComplete !== "any"
      ? { required_skills_complete: filters.requiredSkillsComplete === "true" }
      : {}),
  };
}

export default function HomePage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [matchesLoading, setMatchesLoading] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [normalized, setNormalized] = useState<NormalizedRequirements | null>(null);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refreshMatches = useCallback(async () => {
    if (!sessionId) return;
    setMatchesLoading(true);
    try {
      const page = await api.getMatches(sessionId, buildQuery(filters));
      setMatches(page.matches);
      setErrorBanner(null);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Could not load matches.");
    } finally {
      setMatchesLoading(false);
    }
  }, [sessionId, filters]);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;

    async function poll() {
      if (!sessionId || cancelled) return;
      try {
        const nextStatus = await api.getSessionStatus(sessionId);
        setStatus((current) =>
          current && JSON.stringify(current) === JSON.stringify(nextStatus) ? current : nextStatus
        );
        const pending = Object.entries(nextStatus.counts).some(
          ([stage, count]) => count > 0 && !["scored", "failed"].includes(stage)
        );
        if (pending) {
          pollTimer.current = setTimeout(poll, POLL_INTERVAL_MS);
        } else {
          void refreshMatches();
        }
      } catch {
        pollTimer.current = setTimeout(poll, POLL_INTERVAL_MS * 3);
      }
    }

    void poll();
    return () => {
      cancelled = true;
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
  }, [sessionId, refreshMatches]);

  function handleSessionCreated(id: string) {
    setSessionId(id);
  }

  function handleUploaded(result: UploadResult) {
    setSelectedCandidateId(null);
    void api
      .getSessionStatus(sessionId ?? result.session_id)
      .then((next) => setStatus(next))
      .catch(() => undefined);
  }

  async function handleDeleteSession() {
    if (!sessionId) return;
    try {
      await api.deleteSession(sessionId);
      setSessionId(null);
      setStatus(null);
      setMatches([]);
      setSelectedCandidateId(null);
      setErrorBanner(null);
      setNormalized(null);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Could not delete the session.");
    }
  }

  return (
    <div className="max-w-[1280px] mx-auto p-6 grid gap-8">
      <header className="flex flex-wrap justify-between items-baseline gap-3 border-b border-border pb-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-text">
            Smart Resume Screener
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            Evidence-based shortlisting for one role at a time.
          </p>
        </div>
        <p className="text-sm text-text-secondary border-l-2 border-accent pl-3 py-1 bg-surface rounded-r-lg">
          AI scores are decision support. A human makes the hiring decision.
        </p>
      </header>

      <div className="grid gap-8 items-start lg:grid-cols-[360px_1fr]">
        <aside className="flex flex-col gap-5 lg:sticky lg:top-6">
          <JDFileUploader
            sessionId={sessionId}
            onSessionCreated={handleSessionCreated}
            onNormalized={setNormalized}
          />
          <Uploader sessionId={sessionId} onUploaded={handleUploaded} />
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

          {status && (
            <>
              <StatusStrip total={status.total} counts={status.counts} />
              <FilterBar
                filters={filters}
                onChange={setFilters}
                onApply={() => void refreshMatches()}
                busy={matchesLoading}
              />
              <MatchTable
                matches={matches}
                loading={matchesLoading}
                hasSession={Boolean(sessionId)}
                selectedCandidateId={selectedCandidateId}
                onSelect={(id) => setSelectedCandidateId((current) => (current === id ? null : id))}
              />
              {matches.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="px-4 py-2 rounded-lg bg-accent text-bg font-medium hover:bg-accent-hover transition-colors"
                    onClick={() => exportJson(matches, sessionId ?? "")}
                  >
                    Export JSON
                  </button>
                  <button
                    type="button"
                    className="px-4 py-2 rounded-lg bg-accent text-bg font-medium hover:bg-accent-hover transition-colors"
                    onClick={() => exportCsv(matches)}
                  >
                    Export CSV
                  </button>
                </div>
              )}
            </>
          )}
          {!status && !sessionId && (
            <MatchTable matches={[]} loading={false} hasSession={false} selectedCandidateId={null} onSelect={() => undefined} />
          )}

          {selectedCandidateId && (
            <CandidateDetail
              candidateId={selectedCandidateId}
              onClose={() => setSelectedCandidateId(null)}
            />
          )}

          {sessionId && (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="px-4 py-2 rounded-lg border border-error text-error hover:bg-error/10 transition-colors font-medium"
                onClick={() => void handleDeleteSession()}
              >
                Delete this session and its data
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
