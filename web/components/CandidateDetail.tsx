"use client";

import { motion, type Variants } from "framer-motion";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { usePrefersReducedMotion } from "@/lib/hooks";
import type { CandidateDetail as CandidateDetailData, Match } from "@/lib/types";
import ScoreGauge, { formatCoverage } from "./ScoreGauge";
import styles from "./CandidateDetail.module.css";

const panelVariants: Variants = {
  hidden: { opacity: 0, x: 32 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.3, ease: "easeOut" } },
  exit: { opacity: 0, x: 32, transition: { duration: 0.2, ease: "easeIn" } },
};

const TABS = ["Parsed", "Score", "Evidence", "Uncertainty", "File"] as const;
type Tab = (typeof TABS)[number];

interface CandidateDetailProps {
  candidateId: string;
  onClose: () => void;
}

export default function CandidateDetail({ candidateId, onClose }: CandidateDetailProps) {
  const [detail, setDetail] = useState<CandidateDetailData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("Score");
  const prefersReduced = usePrefersReducedMotion();

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setError(null);
    api
      .getCandidate(candidateId)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load this candidate. Try again.");
      });
    return () => {
      cancelled = true;
    };
  }, [candidateId]);

  const match: Match | null =
    detail?.match && "score" in (detail.match as Record<string, unknown>)
      ? (detail.match as Match)
      : null;
  const parsed = detail?.resume.parsed_json ?? null;

  return (
    <motion.div
      className={styles.panel}
      role="region"
      aria-label={`Candidate ${candidateId} details`}
      variants={prefersReduced ? undefined : panelVariants}
      initial={prefersReduced ? undefined : "hidden"}
      animate={prefersReduced ? undefined : "visible"}
      exit={prefersReduced ? undefined : "exit"}
    >
      <div className={styles.panelHeader}>
        <h2 style={{ margin: 0, fontSize: 16 }}>
          Candidate <code>{candidateId}</code>
        </h2>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {match && <ScoreGauge score={match.score} large showLabel />}
          <button type="button" className={styles.closeButton} onClick={onClose} aria-label="Close candidate details">
            ×
          </button>
        </div>
      </div>

      <div className={styles.tabs} role="tablist" aria-label="Candidate detail sections">
        {TABS.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            className={styles.tab}
            onClick={() => setTab(name)}
          >
            {name}
          </button>
        ))}
      </div>

      <div className={styles.tabPanel} role="tabpanel">
        {error && (
          <p role="alert" className="fieldError">
            {error}
          </p>
        )}
        {!error && !detail && <p role="status">Loading candidate…</p>}

        {detail && tab === "Parsed" && parsed && (
          <div className={styles.kvGrid}>
            <span className={styles.kvKey}>Name</span>
            <span>{parsed.candidate.name ?? "—"}</span>
            <span className={styles.kvKey}>Email</span>
            <span>{parsed.candidate.contact.email ?? "—"}</span>
            <span className={styles.kvKey}>Phone</span>
            <span>{parsed.candidate.contact.phone ?? "—"}</span>
            <span className={styles.kvKey}>Location</span>
            <span>{parsed.candidate.location ?? "—"}</span>
            <span className={styles.kvKey}>Skills</span>
            <ul className={styles.tagList}>
              {parsed.skills.map((skill) => (
                <li key={skill} className={styles.tag}>
                  {skill}
                </li>
              ))}
            </ul>
            <span className={styles.kvKey}>Experience</span>
            <ul className={styles.listPlain}>
              {parsed.experience.map((record, index) => (
                <li key={index}>
                  {record.role ?? "Unknown role"} at {record.company ?? "Unknown company"} ·{" "}
                  {record.duration_months ?? "?"} months
                </li>
              ))}
            </ul>
            <span className={styles.kvKey}>Education</span>
            <ul className={styles.listPlain}>
              {parsed.education.map((record, index) => (
                <li key={index}>
                  {record.degree ?? "Degree not stated"}{record.field ? `, ${record.field}` : ""} —{" "}
                  {record.institution ?? "institution not stated"}
                </li>
              ))}
            </ul>
            <span className={styles.kvKey}>Languages</span>
            <span>{parsed.languages.join(", ") || "—"}</span>
          </div>
        )}
        {detail && tab === "Parsed" && !parsed && (
          <p>This candidate has no parsed data yet — processing may still be running or have failed.</p>
        )}

        {detail && tab === "Score" && match && (
          <div style={{ display: "grid", gap: "var(--space-5)" }}>
            <div className={styles.kvGrid}>
              <span className={styles.kvKey}>Required coverage</span>
              <span className={styles.coverage}>{formatCoverage(match.required_coverage)}</span>
              <span className={styles.kvKey}>Preferred coverage</span>
              <span className={styles.coverage}>{formatCoverage(match.preferred_coverage)}</span>
              <span className={styles.kvKey}>Model</span>
              <span>
                {match.model.provider}/{match.model.model} · prompt {match.model.prompt_version}
              </span>
            </div>
            <div>
              <h3 style={{ margin: "0 0 8px" }}>Strengths</h3>
              <ul className={styles.listPlain}>
                {match.strengths.map((strength) => (
                  <li key={strength} className={styles.strengthItem}>
                    {strength}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 style={{ margin: "0 0 8px" }}>Gaps</h3>
              <ul className={styles.listPlain}>
                {match.gaps.map((gap) => (
                  <li key={gap} className={styles.gapItem}>
                    {gap}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
        {detail && tab === "Score" && !match && (
          <p>No score yet. This candidate has not completed scoring.</p>
        )}

        {detail && tab === "Evidence" &&
          (match && match.evidence.length > 0 ? (
            <ul className={styles.evidenceList}>
              {match.evidence.map((item) => (
                <li key={`${item.source}-${item.claim}`} className={styles.evidenceItem}>
                  <strong>{item.claim}</strong>
                  <blockquote className={styles.quote}>"{item.quote}"</blockquote>
                  <span className={styles.source}>{item.source}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p>No evidence recorded for this candidate.</p>
          ))}

        {detail && tab === "Uncertainty" &&
          (match && match.uncertainty.length > 0 ? (
            <ul className={styles.listPlain}>
              {match.uncertainty.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p>No uncertainty notes for this candidate.</p>
          ))}

        {detail && tab === "File" && (
          <div className={styles.kvGrid}>
            <span className={styles.kvKey}>Filename</span>
            <span>{detail.resume.filename ?? "—"}</span>
            <span className={styles.kvKey}>Content type</span>
            <span>{detail.resume.content_type ?? "—"}</span>
            <span className={styles.kvKey}>Size</span>
            <span>{detail.resume.size_bytes != null ? `${detail.resume.size_bytes} bytes` : "—"}</span>
            <span className={styles.kvKey}>Checksum</span>
            <span style={{ fontFamily: "var(--font-data)", fontSize: 12, overflowWrap: "anywhere" }}>
              {detail.resume.checksum ?? "—"}
            </span>
            <span className={styles.kvKey}>Status</span>
            <span>{detail.resume.status ?? "—"}</span>
          </div>
        )}
      </div>
    </motion.div>
  );
}
