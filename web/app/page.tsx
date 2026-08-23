"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import CandidateDetail from "@/components/CandidateDetail";
import FilterBar, { DEFAULT_FILTERS, type FilterState } from "@/components/FilterBar";
import JobDescriptionForm from "@/components/JobDescriptionForm";
import MatchTable from "@/components/MatchTable";
import StatusStrip from "@/components/StatusStrip";
import Uploader from "@/components/Uploader";
import { api } from "@/lib/api";
import { exportCsv, exportJson } from "@/lib/export";
import type { Match, SessionStatus, UploadResult } from "@/lib/types";
import styles from "./page.module.css";

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

  // Poll status while work is in flight; refresh matches when it settles.
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
    // Kick a status fetch immediately; the polling effect continues from there.
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
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Could not delete the session.");
    }
  }

  return (
    <div className={styles.page}>
      <header className={styles.masthead}>
        <div>
          <h1 className={styles.title}>Smart Resume Screener</h1>
          <p className={styles.subtitle}>
            Evidence-based shortlisting for one role at a time.
          </p>
        </div>
        <p className="disclaimer" style={{ margin: 0 }}>
          AI scores are decision support. A human makes the hiring decision.
        </p>
      </header>

      <div className={styles.layout}>
        <aside className={styles.rail}>
          <JobDescriptionForm sessionId={sessionId} onSessionCreated={handleSessionCreated} />
          <Uploader sessionId={sessionId} onUploaded={handleUploaded} />
        </aside>

        <main className={styles.mainColumn} aria-label="Screening results">
          {errorBanner && (
            <p className={styles.banner} role="alert">
              {errorBanner}
            </p>
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
                <div className={styles.toolbar}>
                  <button
                    type="button"
                    className="primaryButton"
                    onClick={() => exportJson(matches, sessionId ?? "")}
                  >
                    Export JSON
                  </button>
                  <button
                    type="button"
                    className="primaryButton"
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
            <div className={styles.toolbar}>
              <button type="button" className="dangerButton" onClick={() => void handleDeleteSession()}>
                Delete this session and its data
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
