"use client";

import { motion, type Variants } from "framer-motion";
import ScoreGauge from "./ScoreGauge";
import type { ParsedCandidate } from "@/lib/types";
import styles from "./CandidateCard.module.css";

const cardVariants: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3, ease: "easeOut" } },
};

interface CandidateCardProps {
  candidate: ParsedCandidate;
  rank: number;
}

export default function CandidateCard({ candidate, rank }: CandidateCardProps) {
  const initials = candidate.name
    ? candidate.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "?";

  const experienceText =
    candidate.experience_years > 0
      ? `${candidate.experience_years} yrs experience`
      : "Fresher";

  const highestEducation = [...candidate.education].sort((a, b) =>
    (a.graduation_date ?? "").localeCompare(b.graduation_date ?? "")
  )[0];

  return (
    <motion.div
      className={styles.card}
      variants={cardVariants}
      initial="hidden"
      animate="visible"
    >
      <div className={styles.rank} aria-hidden="true">
        {rank}
      </div>
      <div className={styles.avatar}>{initials}</div>
      <div className={styles.info}>
        <p className={styles.name}>{candidate.name || "Unknown Candidate"}</p>
        <p className={styles.details}>
          {highestEducation?.degree
            ? `${highestEducation.degree}${highestEducation.field ? `, ${highestEducation.field}` : ""}`
            : "Education not stated"}
          {" · "}
          {experienceText}
          {candidate.location ? ` · ${candidate.location}` : ""}
        </p>
        {candidate.skills.length > 0 && (
          <div className={styles.skills}>
            {candidate.skills.slice(0, 6).map((skill) => (
              <span key={skill} className={styles.skillTag}>
                {skill}
              </span>
            ))}
            {candidate.skills.length > 6 && (
              <span className={styles.skillTag}>+{candidate.skills.length - 6}</span>
            )}
          </div>
        )}
      </div>
      <div className={styles.score}>
        {candidate.status === "scored" && candidate.score !== undefined ? (
          <ScoreGauge score={candidate.score} large showLabel />
        ) : candidate.status === "failed" ? (
          <span className={styles.error}>Failed to process</span>
        ) : (
          <span className={styles.pending}>Scoring…</span>
        )}
      </div>
    </motion.div>
  );
}
