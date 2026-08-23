"use client";

import { motion, type Variants } from "framer-motion";
import type { Match } from "@/lib/types";
import { usePrefersReducedMotion } from "@/lib/hooks";
import ScoreGauge, { formatCoverage } from "./ScoreGauge";
import styles from "./MatchTable.module.css";

const staggerContainer: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.04 },
  },
};

const rowVariants: Variants = {
  hidden: { opacity: 0, x: -8 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.3, ease: "easeOut" } },
};

interface MatchTableProps {
  matches: Match[];
  loading: boolean;
  hasSession: boolean;
  selectedCandidateId: string | null;
  onSelect: (candidateId: string) => void;
}

export default function MatchTable({
  matches,
  loading,
  hasSession,
  selectedCandidateId,
  onSelect,
}: MatchTableProps) {
  const prefersReduced = usePrefersReducedMotion();

  if (loading) {
    return (
      <p className={styles.loading} role="status">
        Loading matches…
      </p>
    );
  }
  if (!hasSession) {
    return (
      <p className={styles.empty}>Start a session and upload resumes to see ranked matches.</p>
    );
  }
  if (matches.length === 0) {
    return (
      <p className={styles.empty}>
        No matches yet. Candidates appear here after scoring completes, or adjust filters to widen
        the shortlist.
      </p>
    );
  }

  return (
    <motion.table
      className={styles.table}
      variants={prefersReduced ? undefined : staggerContainer}
      initial={prefersReduced ? undefined : "hidden"}
      animate={prefersReduced ? undefined : "visible"}
    >
      <caption className="visuallyHidden">
        Ranked candidates by score descending, then required coverage
      </caption>
      <thead>
        <tr>
          <th scope="col">#</th>
          <th scope="col">
            <span className={styles.sortHeader}>
              Score <span className={styles.sortArrow} aria-hidden="true">▼</span>
              <span className="visuallyHidden">(sorted descending)</span>
            </span>
          </th>
          <th scope="col">
            <span className={styles.sortHeader}>
              Required coverage <span className={styles.sortArrow} aria-hidden="true">▼</span>
              <span className="visuallyHidden">(secondary sort, descending)</span>
            </span>
          </th>
          <th scope="col">Preferred coverage</th>
          <th scope="col">Candidate</th>
          <th scope="col">Top strength</th>
        </tr>
      </thead>
      <tbody>
        {matches.map((match, index) => (
          <motion.tr
            key={match.candidate_id}
            variants={prefersReduced ? undefined : rowVariants}
            style={
              match.candidate_id === selectedCandidateId ? { background: "var(--surface)" } : undefined
            }
          >
            <td className={styles.rankCell}>{index + 1}</td>
            <td>
              <ScoreGauge score={match.score} />
            </td>
            <td className={styles.coverage}>{formatCoverage(match.required_coverage)}</td>
            <td className={styles.coverage}>{formatCoverage(match.preferred_coverage)}</td>
            <td>
              <button
                type="button"
                className={styles.rowButton}
                onClick={() => onSelect(match.candidate_id)}
                aria-expanded={match.candidate_id === selectedCandidateId}
              >
                {match.candidate_id}
              </button>
            </td>
            <td>{match.strengths[0] ?? "—"}</td>
          </motion.tr>
        ))}
      </tbody>
    </motion.table>
  );
}
