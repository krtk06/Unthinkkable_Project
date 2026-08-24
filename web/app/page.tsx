"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import CandidateStatusLog from "@/components/CandidateStatusLog";
import JDFileUploader from "@/components/JDFileUploader";
import JobDescriptionForm from "@/components/JobDescriptionForm";
import Uploader from "@/components/Uploader";
import CandidateDetail from "@/components/CandidateDetail";
import { api, checkApiHealth, ApiError } from "@/lib/api";
import { clearToken, getToken } from "@/lib/auth";
import { exportCsv, exportJson } from "@/lib/export";
import { RainbowButton } from "@/components/ui/rainbow-button";
import { ShiningText } from "@/components/ui/shining-text";
import type { NormalizedRequirements, ParsedCandidate, SessionStatus, UploadResult } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

function compareCandidates(a: ParsedCandidate, b: ParsedCandidate): number {
  const aScore = a.status === "scored" ? a.score ?? 0 : -1;
  const bScore = b.status === "scored" ? b.score ?? 0 : -1;
  if (aScore !== bScore) return bScore - aScore;
  return (a.name ?? "").localeCompare(b.name ?? "");
}

const SCORE_FILTERS = [
  { value: "all", label: "Filter by score" },
  { value: "9", label: "9+ score" },
  { value: "8", label: "8+ score" },
  { value: "7", label: "7+ score" },
  { value: "6", label: "6+ score" },
  { value: "5", label: "5+ score" },
];

const STATUS_FILTERS = [
  { value: "all", label: "Status" },
  { value: "shortlisted", label: "Shortlisted" },
  { value: "scored", label: "Scored" },
  { value: "scoring", label: "Scoring" },
  { value: "failed", label: "Failed" },
];

function initialsOf(candidate: ParsedCandidate): string {
  const source = candidate.name || candidate.filename || "C";
  return (
    source
      .replace(/\.[a-z]+$/i, "")
      .split(/[\s._-]+/)
      .filter(Boolean)
      .map((word) => word[0])
      .slice(0, 2)
      .join("")
      .toUpperCase() || "C"
  );
}

export default function HomePage() {
  const router = useRouter();
  const [authReady, setAuthReady] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [normalized, setNormalized] = useState<NormalizedRequirements | null>(null);
  const [parsedCandidates, setParsedCandidates] = useState<ParsedCandidate[]>([]);
  const [scoringAll, setScoringAll] = useState(false);
  const [_apiConnected, _setApiConnected] = useState(false);
  const [scoreFilter, setScoreFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      const connected = await checkApiHealth();
      if (!cancelled) _setApiConnected(connected);
    };
    void check();
    const interval = setInterval(() => void check(), 10000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

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
              ? (detail.match as {
                  score: number;
                  skills_score?: number;
                  experience_score?: number;
                  education_score?: number;
                  matching_skills?: string[];
                  missing_skills?: string[];
                  semantic_similarity?: number;
                  analysis?: string;
                  shortlisted?: boolean;
                })
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
              skills_score: match?.skills_score,
              experience_score: match?.experience_score,
              education_score: match?.education_score,
              matching_skills: match?.matching_skills,
              missing_skills: match?.missing_skills,
              semantic_similarity: match?.semantic_similarity,
              analysis: match?.analysis,
              shortlisted: match?.shortlisted,
              raw_text: detail.resume?.extracted_text ?? null,
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

  function handleDelete(candidate_id: string) {
    void api
      .deleteCandidate(candidate_id)
      .then(() => {
        setParsedCandidates((current) =>
          current.filter((c) => c.candidate_id !== candidate_id)
        );
      })
      .catch((err: unknown) =>
        setErrorBanner(
          err instanceof ApiError ? `Could not remove candidate: ${err.message}` : "Could not remove candidate."
        )
      );
    void poll();
  }

  async function handleScoreAll() {
    if (!sessionId) return;
    setScoringAll(true);
    setErrorBanner(null);
    try {
      await api.scoreAllCandidates(sessionId);
    } catch (err) {
      setErrorBanner(
        err instanceof ApiError ? `Could not score candidates: ${err.message}` : "Could not score candidates."
      );
    } finally {
      setScoringAll(false);
      void poll();
    }
  }

  function handleLogout() {
    clearToken();
    router.replace("/login");
  }

  if (!authReady) {
    return null;
  }

  const sortedCandidates = [...parsedCandidates].sort(compareCandidates);
  const filteredCandidates = sortedCandidates.filter((c) => {
    if (scoreFilter !== "all") {
      if (c.status !== "scored" || (c.score ?? 0) < Number(scoreFilter)) return false;
    }
    if (statusFilter !== "all") {
      if (statusFilter === "shortlisted" && !c.shortlisted) return false;
      if (statusFilter === "scored" && c.status !== "scored") return false;
      if (statusFilter === "scoring" && c.status !== "scoring") return false;
      if (statusFilter === "failed" && c.status !== "failed") return false;
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      const hay = `${c.name ?? ""} ${c.email ?? ""} ${c.filename ?? ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  const scoredCount = sortedCandidates.filter((c) => c.status === "scored").length;
  const selectedCandidate = selectedId ? sortedCandidates.find((c) => c.candidate_id === selectedId) ?? null : null;

  return (
    <div className="min-h-screen bg-[#080a0c] text-zinc-200">
      <div
        className="pointer-events-none fixed inset-0 opacity-[0.35]"
        aria-hidden="true"
        style={{
          backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.09) 1px, transparent 1px)",
          backgroundSize: "22px 22px",
        }}
      />

      <div className="relative">
        <header className="flex items-center justify-between gap-4 border-b border-white/[0.07] px-6 py-4">
          <div>
            <h1 className="font-scoria text-[26px] font-normal tracking-wide text-white"> Hirelytics </h1>
          </div>
          <RainbowButton type="button" size="sm" onClick={handleLogout}>
            Logout
          </RainbowButton>
        </header>

        {errorBanner && (
          <div className="mx-6 mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300" role="alert">
            {errorBanner}
          </div>
        )}

        {/* Top: 3 equal columns */}
        <div className="grid grid-cols-1 lg:grid-cols-3 divide-y lg:divide-y-0 lg:divide-x divide-white/[0.07]">
          <section className="p-6 lg:p-7">
            <JobDescriptionForm
              sessionId={sessionId}
              onSessionCreated={handleSessionCreated}
              onNormalized={setNormalized}
              onSubmitted={() => {
                setErrorBanner(null);
                void poll();
              }}
            />
            <div className="mt-6">
              <CandidateStatusLog status={status} />
            </div>
          </section>

          <section className="p-6 lg:p-7">
            <JDFileUploader
              sessionId={sessionId}
              onSessionCreated={handleSessionCreated}
              onNormalized={setNormalized}
              onUploaded={() => {
                setErrorBanner(null);
                void poll();
              }}
            />
          </section>

          <section className="p-6 lg:p-7 flex flex-col">
            <Uploader sessionId={sessionId} onUploaded={handleUploaded} />
            <p className="mt-4 text-sm leading-relaxed text-zinc-500">
              Resumes are sent automatically once a job description is filed. No data leaves the session until you export.
            </p>
            {normalized && (
              <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.03] p-4">
                {normalized.title && <p className="text-sm font-medium text-white">{normalized.title}</p>}
                <p className="mt-1 text-sm leading-relaxed text-zinc-500">
                  Required: {normalized.required.map((r) => r.name).join(", ") || "none stated"} · Preferred: {normalized.preferred.map((r) => r.name).join(", ") || "none stated"}
                </p>
                {normalized.ambiguities.length > 0 && (
                  <p className="mt-2 text-xs text-amber-400">Ambiguous items were treated as preferred — review before scoring.</p>
                )}
              </div>
            )}
            {sortedCandidates.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2 border-t border-white/[0.06] pt-4">
                <RainbowButton type="button" onClick={() => void handleScoreAll()} disabled={scoringAll || !normalized}>
                  {scoringAll ? <ShiningText text="Scoring…" className="text-sm" /> : scoredCount > 0 ? "Re-score all candidates" : "Score all candidates"}
                </RainbowButton>
                {scoredCount > 0 && (
                  <>
                    <RainbowButton type="button" size="sm" onClick={() => exportJson(sortedCandidates, sessionId ?? "")}>Export JSON</RainbowButton>
                    <RainbowButton type="button" size="sm" onClick={() => exportCsv(sortedCandidates)}>Export CSV</RainbowButton>
                  </>
                )}
              </div>
            )}
          </section>
        </div>

        {/* Bottom: full-width filter + candidate table */}
        <div className="border-t border-white/[0.07] pb-16">
          <div className="flex flex-wrap items-center gap-2 p-4">
            <div className="flex items-center gap-2">
              <div className="relative">
                <select
                  value={scoreFilter}
                  onChange={(e) => setScoreFilter(e.target.value)}
                  aria-label="Filter by score"
                  className="appearance-none rounded-full border border-white/10 bg-white/[0.04] px-4 py-1.5 pr-8 text-sm text-zinc-400 outline-none focus:border-white/20"
                >
                  {SCORE_FILTERS.map((f) => (
                    <option key={f.value} value={f.value} className="bg-zinc-900">
                      {f.label}
                    </option>
                  ))}
                </select>
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500">▾</span>
              </div>
              <div className="relative">
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  aria-label="Filter by status"
                  className="appearance-none rounded-full border border-white/10 bg-white/[0.04] px-4 py-1.5 pr-8 text-sm text-zinc-400 outline-none focus:border-white/20"
                >
                  {STATUS_FILTERS.map((f) => (
                    <option key={f.value} value={f.value} className="bg-zinc-900">
                      {f.label}
                    </option>
                  ))}
                </select>
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500">▾</span>
              </div>
            </div>
            <div className="relative ml-auto flex items-center">
              <span className="pointer-events-none absolute left-3 text-zinc-600">⌕</span>
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search"
                aria-label="Search candidates"
                className="w-64 rounded-full border border-white/10 bg-white/[0.04] py-1.5 pl-8 pr-3 text-sm text-white placeholder:text-zinc-600 outline-none focus:border-white/20"
              />
            </div>
          </div>

          <div className="hidden grid-cols-[1fr_90px_160px_100px] gap-4 border-y border-white/[0.07] px-6 py-3 text-[11px] font-medium tracking-widest text-zinc-500 sm:grid">
            <span>CANDIDATE</span>
            <span className="text-center">MATCH</span>
            <span>KEY SKILLS</span>
            <span />
          </div>

          <div className="divide-y divide-white/[0.06] min-h-[40vh]">
            {filteredCandidates.length === 0 ? (
              <>
                {sortedCandidates.length > 0 && filteredCandidates.length === 0 && (
                  <div className="px-6 py-8 text-sm text-zinc-500">No candidates match the current filters. <span className="text-zinc-600">→ Try widening the score or status filter.</span></div>
                )}
                {!sessionId && <div className="px-6 py-8 text-sm text-zinc-500">No candidates yet — no candidates yet. Drop a job description to start, then add resumes.</div>}
                {sessionId && !normalized && (
                  <div className="px-6 py-8 text-sm text-zinc-500">
                    <ShiningText text="Waiting for a job description…" className="text-sm" />
                  </div>
                )}
                {sessionId && normalized && sortedCandidates.length === 0 && (
                  <div className="px-6 py-8">
                    <p className="text-sm font-medium text-zinc-300">JD filed — ready for resumes</p>
                    <p className="mt-1 text-sm text-zinc-500">Drop PDFs on the left. They queue and score in the background.</p>
                  </div>
                )}
              </>
            ) : (
              filteredCandidates.map((candidate) => {
                const displayName = candidate.name || candidate.filename || "Candidate";
                const expRole = candidate.experience?.[0]?.role as string | undefined;
                const companyRole = expRole ? `${expRole}` : (candidate.location ?? "");
                const isPending = candidate.status !== "scored" || candidate.score === undefined;
                const score = candidate.score ?? 0;
                const pct = Math.max(8, Math.min(100, (score / 10) * 100));
                const skills = (candidate.matching_skills && candidate.matching_skills.length > 0 ? candidate.matching_skills : candidate.skills.slice(0, 3)).slice(0, 3);
                return (
                  <div
                    key={candidate.candidate_id}
                    className="grid grid-cols-1 gap-3 px-6 py-4 sm:grid-cols-[1fr_90px_160px_100px] sm:items-center sm:gap-4 hover:bg-white/[0.02] transition-colors"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-zinc-800 ring-1 ring-white/10 text-xs font-medium text-zinc-400">
                        {initialsOf(candidate)}
                      </span>
                      <div className="min-w-0">
                        <h3 className="truncate text-sm font-medium leading-tight text-white">{displayName}</h3>
                        <p className="truncate text-xs leading-tight text-zinc-500">{companyRole || "—"}</p>
                        <span className="sr-only">{candidate.email}</span>
                      </div>
                    </div>

                    <div className="flex flex-col items-start sm:items-center" role="img" aria-label={`Match score ${score.toFixed(1)} out of 10`}>
                      {isPending ? (
                        candidate.status === "failed" ? (
                          <span className="text-xs text-red-400">failed</span>
                        ) : (
                          <ShiningText text="Scoring…" className="text-xs" />
                        )
                      ) : (
                        <>
                          <div className="flex items-baseline gap-1 tabular-nums">
                            <span className="text-sm font-semibold text-white">{score.toFixed(1)}</span>
                            <span className="text-xs text-zinc-500">/10</span>
                          </div>
                          <div className="mt-1 h-0.5 w-[72px] rounded-full bg-white/10">
                            <div className="h-0.5 rounded-full bg-[#5d5d65]" style={{ width: `${pct}%` }} />
                          </div>
                          {candidate.shortlisted && (
                            <span className="mt-1.5 inline-flex items-center rounded-full bg-[#5d5d65]/15 px-1.5 py-0.5 text-[10px] font-medium leading-none text-[#5d5d65]" aria-label="Shortlisted">
                              Shortlisted
                            </span>
                          )}
                        </>
                      )}
                    </div>

                    <div className="flex flex-wrap gap-1.5 sm:flex-col sm:items-start sm:gap-1">
                      {isPending ? (
                        <span className="text-xs text-zinc-600">—</span>
                      ) : skills.length > 0 ? (
                        skills.map((s) => (
                          <span key={s} className="inline-flex rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-zinc-400">
                            {s}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-zinc-600">No skills</span>
                      )}
                    </div>

                    <div className="flex justify-end gap-3">
                      <button
                        type="button"
                        onClick={() => setSelectedId(candidate.candidate_id)}
                        className="text-xs text-zinc-500 hover:text-zinc-200 transition-colors"
                      >
                        View details
                      </button>
                      <span className="text-xs text-[#c36e5b]">Schedule</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {selectedCandidate && (
        <CandidateDetail
          candidate={selectedCandidate}
          open={!!selectedCandidate}
          onClose={() => setSelectedId(null)}
          onDelete={handleDelete}
        />
      )}
    </div>
  );
}
