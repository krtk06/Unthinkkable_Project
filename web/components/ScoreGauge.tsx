import { useMemo } from "react";
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
  large?: boolean;
  showLabel?: boolean;
}

export default function ScoreGauge({ score, large = false, showLabel = false }: ScoreGaugeProps) {
  const clamped = Math.max(1, Math.min(10, Math.round(score)));
  const band = useMemo(() => bandForScore(clamped), [clamped]);
  const bandClass = styles[`band${band.key.charAt(0).toUpperCase()}${band.key.slice(1)}`];

  return (
    <span className={styles.wrap} title={`Score ${clamped}/10 — ${band.label}`}>
      <span className={`${styles.gauge} ${large ? styles.gaugeLarge : ""}`} aria-hidden="true">
        {Array.from({ length: 10 }, (_, index) => (
          <span
            key={index}
            className={styles.gaugeSegment}
            style={index < clamped ? { background: `var(--band-${band.key})` } : undefined}
          />
        ))}
      </span>
      <strong className={`${styles.scoreValue} ${bandClass}`}>
        {clamped}
        <span aria-hidden="true">/10</span>
        <span className="visuallyHidden"> out of 10</span>
      </strong>
      {showLabel && (
        <>
          {" "}
          <span className={`${styles.bandLabel} ${bandClass}`}>{band.label}</span>
        </>
      )}
    </span>
  );
}
