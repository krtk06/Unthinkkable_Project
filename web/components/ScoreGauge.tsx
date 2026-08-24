"use client";

import { animate } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { usePrefersReducedMotion } from "@/lib/hooks";
import styles from "./ScoreGauge.module.css";

export type BandKey = "absent" | "limited" | "partial" | "strong" | "exceptional";

export function bandForScore(score: number): { key: BandKey; label: string } {
  if (score <= 2) return { key: "absent", label: "No credible evidence" };
  if (score <= 4) return { key: "limited", label: "Limited alignment" };
  if (score <= 6) return { key: "partial", label: "Partial alignment" };
  if (score <= 8) return { key: "strong", label: "Strong alignment" };
  if (score === 9) return { key: "exceptional", label: "Very strong alignment" };
  return { key: "exceptional", label: "Exceptional alignment" };
}

export function formatCoverage(value: number): string {
  return `${Math.round(value * 100)}%`;
}

interface ScoreGaugeProps {
  score: number;
  showLabel?: boolean;
}

const RADIUS = 40;
const STROKE = 9;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export default function ScoreGauge({ score, showLabel = false }: ScoreGaugeProps) {
  const value = Math.max(0, Math.min(10, score));
  const band = useMemo(() => bandForScore(value), [value]);
  const offset = CIRCUMFERENCE - (value / 10) * CIRCUMFERENCE;

  // Start at the real value so the first paint is correct; later
  // prop changes tween from the currently shown number.
  const [displayScore, setDisplayScore] = useState(value);
  const shownRef = useRef(value);
  const prefersReduced = usePrefersReducedMotion();

  useEffect(() => {
    if (prefersReduced || shownRef.current === value) {
      shownRef.current = value;
      setDisplayScore(value);
      return;
    }
    const controls = animate(shownRef.current, value, {
      duration: 0.6,
      ease: "easeOut",
      onUpdate: (latest) => {
        shownRef.current = latest;
        setDisplayScore(latest);
      },
    });
    return () => controls.stop();
  }, [value, prefersReduced]);

  return (
    <span className={styles.wrap} title={`Score ${value.toFixed(1)}/10 — ${band.label}`}>
      <svg
        className={styles.gauge}
        viewBox="0 0 96 96"
        role="img"
        aria-label={`Match score ${value.toFixed(1)} out of 10`}
      >
        <circle cx="48" cy="48" r={RADIUS} className={styles.track} />
        <circle
          cx="48"
          cy="48"
          r={RADIUS}
          className={styles.progress}
          stroke={`var(--color-band-${band.key})`}
          strokeWidth={STROKE}
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          transform="rotate(-90 48 48)"
          strokeLinecap="round"
          fill="none"
        />
        <text x="48" y="44" dominantBaseline="middle" textAnchor="middle" className={styles.scoreValue}>
          {displayScore.toFixed(1)}
          <tspan className={styles.fraction}> / 10</tspan>
        </text>
        <text x="48" y="61" dominantBaseline="middle" textAnchor="middle" className={styles.matchLabel}>
          Match
        </text>
      </svg>
      {showLabel && <span className={`${styles.bandLabel} ${styles[`band${band.key.charAt(0).toUpperCase()}${band.key.slice(1)}`]}`}>{band.label}</span>}
    </span>
  );
}
