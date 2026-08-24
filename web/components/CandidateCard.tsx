"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import type { ParsedCandidate } from "@/lib/types";
import { cn } from "@/lib/utils";
import CandidateDetail from "./CandidateDetail";
import ScoreGauge from "./ScoreGauge";
import { GridPatternCard, GridPatternCardBody } from "./ui/grid-pattern-card";
import { RainbowButton } from "./ui/rainbow-button";
import { ShiningText } from "./ui/shining-text";

interface CandidateCardProps {
  candidate: ParsedCandidate;
  onDelete?: (candidate_id: string) => void;
  index?: number;
}

function SkillChip({ skill, matched }: { skill: string; matched: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs transition-colors",
        matched
          ? "border-border bg-zinc-900 text-text"
          : "border-error/30 bg-error/10 text-error/90"
      )}
      title={matched ? "Matching skill" : "Missing skill"}
    >
      {skill}
    </span>
  );
}

function initialsOf(candidate: ParsedCandidate): string {
  let source: string | null = candidate.name;
  if (source == null || source.trim() === "") {
    source = candidate.filename;
  }
  if (source == null || source.trim() === "") {
    throw new Error("MISSING_IDENTITY");
  }
  const initials = source
    .replace(/\.[a-z]+$/i, "")
    .split(/[\s._-]+/)
    .filter(Boolean)
    .map((word) => word[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  if (initials === "") {
    throw new Error("UNPARSABLE_IDENTITY");
  }
  return initials;
}

export default function CandidateCard({ candidate, onDelete, index }: CandidateCardProps) {
  const [detailOpen, setDetailOpen] = useState(false);

  const isPending = candidate.status !== "scored" || candidate.score === undefined;
  const isError = candidate.status === "failed";
  const displayName: string = (() => {
    if (candidate.name) return candidate.name;
    if (candidate.filename) return candidate.filename;
    // conservative estimate for missing display name — not authoritative
    return isError ? "Failed candidate" : "Candidate";
  })();

  // conservative estimates for missing skill arrays — treat absent as empty for display
  const matching: string[] = Array.isArray(candidate.matching_skills) ? candidate.matching_skills : [];
  const missing: string[] = Array.isArray(candidate.missing_skills) ? candidate.missing_skills : [];
  const fallbackSkills: string[] = matching.length === 0 ? candidate.skills.slice(0, 4) : [];

  const handleScheduleInterview = () => {
    if (candidate.email) {
      const subject = encodeURIComponent(`Interview — ${displayName}`);
      window.location.href = `mailto:${candidate.email}?subject=${subject}`;
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.5,
        ease: [0.16, 1, 0.3, 1],
        delay: index !== undefined ? Math.min(index * 0.04, 0.2) : 0,
      }}
    >
      <GridPatternCard
        className={cn(
          "h-[292px] flex flex-col group",
          "shadow-[0_1px_2px_rgba(0,0,0,0.5),0_4px_16px_rgba(0,0,0,0.25)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.5),0_12px_32px_rgba(0,0,0,0.35)]",
          "transition-shadow duration-300",
          isError && "border-error/40",
          candidate.shortlisted && "ring-1 ring-accent/20"
        )}
      >
        {candidate.shortlisted && (
          <div className="h-px w-full bg-gradient-to-r from-accent/60 via-accent/25 to-transparent" aria-hidden="true" />
        )}
        <GridPatternCardBody className="flex flex-col flex-1 overflow-hidden p-4 pt-3.5">
          <CandidateDetail
            candidate={candidate}
            open={detailOpen}
            onClose={() => setDetailOpen(false)}
            onDelete={onDelete}
          />

          <header className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2.5">
              {(() => {
                let display: string;
                try {
                  display = initialsOf(candidate);
                } catch {
                  // conservative estimate for missing identity — not authoritative
                  display = "—";
                }
                return (
                  <span
                    className="flex size-9 shrink-0 items-center justify-center rounded-full bg-zinc-800 ring-1 ring-white/[0.06] text-[11px] font-semibold tracking-wide text-zinc-300"
                    aria-hidden="true"
                  >
                    {display}
                  </span>
                );
              })()}
              <div className="min-w-0">
                <div className="flex items-baseline gap-2">
                  {index !== undefined && (
                    <span className="font-data text-[10px] leading-none tracking-widest text-zinc-500">
                      {(index + 1).toString().padStart(2, "0")}
                    </span>
                  )}
                  <h3 className="text-[13px] font-medium leading-tight tracking-[-0.01em] text-zinc-100">{displayName}</h3>
                </div>
                {candidate.shortlisted ? (
                  <span
                    className="mt-1 inline-flex items-center gap-1 rounded-full bg-accent/10 px-2 py-0.5 text-[10px] font-data font-medium tracking-wider text-accent ring-1 ring-accent/20"
                    aria-label="Shortlisted"
                  >
                    <span className="size-1 rounded-full bg-accent" aria-hidden="true" />
                    Shortlisted
                  </span>
                ) : candidate.location ? (
                  <span className="mt-0.5 block truncate text-xs leading-none text-zinc-500">{candidate.location}</span>
                ) : null}
              </div>
            </div>
            {!isPending && <ScoreGauge score={candidate.score ?? 0} />}
          </header>

          {isPending ? (
            <div className="flex-1 flex flex-col justify-center gap-1.5 py-5">
              <p className="text-sm text-zinc-400">
                {isError ? (
                  <span className="font-data text-xs">
                    Failed to process <span className="text-zinc-300">{candidate.filename || "this resume"}</span>
                  </span>
                ) : (
                  <ShiningText text="Scoring…" className="font-medium text-sm" />
                )}
              </p>
              {!isError && candidate.filename && (
                <span className="font-data text-[11px] tracking-wide text-zinc-600">{candidate.filename}</span>
              )}
            </div>
          ) : (
            <div className="flex-1 mt-5">
              <p className="mb-2 text-[11px] font-data font-medium tracking-widest text-zinc-500 uppercase">
                {(matching.length > 0 || missing.length > 0) ? "Key skills" : "Skills"}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {matching.map((skill) => (
                  <SkillChip key={`m-${skill}`} skill={skill} matched />
                ))}
                {fallbackSkills.map((skill) => (
                  <SkillChip key={`f-${skill}`} skill={skill} matched />
                ))}
                {missing.map((skill) => (
                  <SkillChip key={`x-${skill}`} skill={skill} matched={false} />
                ))}
                {matching.length === 0 && fallbackSkills.length === 0 && missing.length === 0 && (
                  <span className="text-xs text-zinc-500">No skills parsed</span>
                )}
              </div>
            </div>
          )}

          <footer className="mt-auto flex items-center gap-2 border-t border-white/[0.04] pt-3.5">
            <RainbowButton
              type="button"
              size="sm"
              className="flex-1 text-xs"
              onClick={() => setDetailOpen(true)}
            >
              View details
            </RainbowButton>
            <RainbowButton
              type="button"
              size="sm"
              className="flex-1 text-xs"
              onClick={handleScheduleInterview}
              disabled={!candidate.email}
              title={candidate.email ? `Email ${candidate.email}` : "No email on resume"}
            >
              Schedule Interview
            </RainbowButton>
          </footer>
        </GridPatternCardBody>
      </GridPatternCard>
    </motion.div>
  );
}
