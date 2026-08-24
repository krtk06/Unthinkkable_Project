"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { ParsedCandidate } from "@/lib/types";
import ScoreGauge from "./ScoreGauge";
import { GridPatternCard, GridPatternCardBody } from "./ui/grid-pattern-card";
import { RainbowButton } from "./ui/rainbow-button";

interface CandidateDetailProps {
  candidate: ParsedCandidate;
  open: boolean;
  onClose: () => void;
  onDelete?: (candidate_id: string) => void;
}

const TABS = ["Skills", "Experience", "Education", "Raw Resume Text"] as const;
type TabKey = (typeof TABS)[number];

function SubScore({ label, value }: { label: string; value: number | undefined }) {
  return (
    <span className="flex flex-col items-center gap-0.5 rounded-lg bg-zinc-900 px-3 py-1.5">
      <span className="font-data font-medium text-zinc-200">{fmt(value)}</span>
      <span className="text-xs text-zinc-500">{label}</span>
    </span>
  );
}

function fmt(value: number | undefined): string {
  if (value === undefined || value === null) return "-";
  return value.toFixed(1);
}

export default function CandidateDetail({
  candidate,
  open,
  onClose,
  onDelete,
}: CandidateDetailProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  const score = candidate.score ?? 0;
  const years = candidate.experience_years ?? 0;

  const handleOverlayClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) onClose();
  };

  const handleDelete = () => {
    if (
      window.confirm(
        `Remove "${candidate.name || "this candidate"}" from the shortlist?`
      ) &&
      onDelete
    ) {
      onDelete(candidate.candidate_id);
      onClose();
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          aria-hidden={!open}
          onClick={handleOverlayClick}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            transition={{ type: "spring", stiffness: 300, damping: 24 }}
            className="relative max-h-[90vh] w-full max-w-3xl overflow-hidden"
            role="dialog"
            aria-modal="true"
            aria-labelledby="detail-title"
          >
            <GridPatternCard className="max-h-[90vh] flex flex-col">
              <GridPatternCardBody className="max-h-[90vh] overflow-y-auto p-6">
                <RainbowButton
                  type="button"
                  size="sm"
                  className="absolute top-3 right-3 z-10"
                  aria-label="Close"
                  onClick={onClose}
                >
                  ✕
                </RainbowButton>

                <header className="flex items-start justify-between gap-4 pr-12">
                  <div className="min-w-0">
                    <h2 id="detail-title" className="font-semibold text-lg text-zinc-200">
                      {candidate.name || "Candidate"}
                    </h2>
                    <p className="text-sm text-zinc-400">{candidate.email}</p>
                    <p className="text-sm text-zinc-400">{candidate.location}</p>
                  </div>
                  <ScoreGauge score={score} />
                </header>

                <div className="mt-4">
                  <div className="flex gap-4 mb-1">
                    {["skills_score", "experience_score", "education_score"].map((key) => (
                      <SubScore
                        key={key}
                        label={key.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                        value={
                          candidate[key as "skills_score" | "experience_score" | "education_score"]
                        }
                      />
                    ))}
                  </div>
                  {candidate.shortlisted && (
                    <span className="inline-flex items-center rounded-full bg-accent px-2.5 py-0.5 text-xs font-data font-medium text-black uppercase tracking-wider">
                      SHORTLISTED
                    </span>
                  )}
                  {candidate.semantic_similarity !== undefined && (
                    <span className="ml-2 text-xs text-zinc-400">
                      semantic similarity {candidate.semantic_similarity.toFixed(1)}/10
                    </span>
                  )}
                </div>

                <div className="my-4 flex flex-wrap gap-1.5">
                  {candidate.matching_skills?.length ? (
                    candidate.matching_skills.map((skill) => (
                      <span key={`m-${skill}`} className="inline-flex items-center rounded-full bg-accent/15 px-2.5 py-0.5 text-xs text-accent ring-1 ring-accent/25">
                        {skill}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-zinc-500">No matching skills</span>
                  )}
                  {candidate.missing_skills?.length ? (
                    candidate.missing_skills.map((skill) => (
                      <span key={`x-${skill}`} className="inline-flex items-center rounded-full bg-error/15 px-2.5 py-0.5 text-xs text-error ring-1 ring-error/25">
                        {skill}
                      </span>
                    ))
                  ) : null}
                </div>

                {candidate.analysis && (
                  <p className="mb-4 text-sm text-zinc-400">{candidate.analysis}</p>
                )}

                <Tabs
                  tabs={TABS}
                  render={(tab) => {
                    switch (tab) {
                      case "Skills":
                        return renderSkills(candidate.skills);
                      case "Experience":
                        return renderExperience(candidate.experience, years);
                      case "Education":
                        return renderEducation(candidate.education);
                      case "Raw Resume Text":
                        return renderRawText(candidate.raw_text);
                      default:
                        return null;
                    }
                  }}
                />

                {onDelete && (
                  <footer className="mt-5 flex justify-end border-t border-zinc-800 pt-4">
                    <RainbowButton
                      type="button"
                      size="sm"
                      className="border-error/40 text-error hover:bg-error/10"
                      onClick={handleDelete}
                    >
                      Delete candidate
                    </RainbowButton>
                  </footer>
                )}
              </GridPatternCardBody>
            </GridPatternCard>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function Tabs({
  tabs,
  render,
}: {
  tabs: readonly TabKey[];
  render: (tab: TabKey) => React.ReactNode;
}) {
  const [active, setActive] = useState(tabs[0]);
  return (
    <div>
      <div className="flex space-x-1 rounded-lg bg-zinc-900 p-1 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActive(tab)}
            className={`flex-1 whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              active === tab
                ? "bg-zinc-800 text-zinc-200 shadow"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>
      <motion.div
        key={active}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="mt-3 max-h-80 overflow-y-auto text-sm"
      >
        {render(active)}
      </motion.div>
    </div>
  );
}

function renderSkills(skills: string[]) {
  if (!skills.length) return <p className="text-sm text-zinc-500">No skills listed.</p>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {skills.map((skill) => (
        <span key={skill} className="inline-flex items-center rounded-full bg-accent/15 px-2.5 py-0.5 text-xs text-accent">
          {skill}
        </span>
      ))}
    </div>
  );
}

function renderExperience(experience: ParsedCandidate["experience"], years: number) {
  if (!experience.length) return <p className="text-sm text-zinc-500">No experience listed.</p>;
  return (
    <div className="space-y-3">
      <p className="text-xs font-medium text-zinc-500">
        EXPERIENCE ({years} YRS DETECTED)
      </p>
      {experience.map((exp, index) => (
        <div key={index} className="space-y-0.5">
          <p className="font-medium text-zinc-200">{exp.role || "Role"} — {exp.company || ""}</p>
          <p className="text-xs text-zinc-500">
            {exp.start_date || ""} → {exp.end_date ?? "present"}
            {exp.duration_months ? ` • ${Math.round(exp.duration_months / 12)} yrs` : ""}
          </p>
          <p className="whitespace-pre-wrap text-sm text-zinc-400">{exp.description}</p>
          {exp.evidence?.length ? (
            <ul className="list-disc list-inside text-xs text-zinc-500">
              {exp.evidence.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function renderEducation(education: ParsedCandidate["education"]) {
  if (!education.length) return <p className="text-sm text-zinc-500">No education listed.</p>;
  return (
    <div className="space-y-2">
      {education.map((edu, index) => (
        <p key={index} className="text-sm text-zinc-500">
          {edu.degree}
          {edu.field ? `, ${edu.field}` : ""}
          {edu.institution ? ` @ ${edu.institution}` : ""}
          {edu.graduation_date ? ` • ${edu.graduation_date.slice(0, 4)}` : ""}
        </p>
      ))}
    </div>
  );
}

function renderRawText(text: string | null | undefined) {
  if (!text) return <p className="text-sm text-zinc-500">No extracted text available.</p>;
  return (
    <pre className="whitespace-pre-wrap rounded-lg bg-zinc-900 p-3 text-xs text-zinc-400">
      {text}
    </pre>
  );
}
