import styles from "./StatusStrip.module.css";

interface StatusStripProps {
  total: number;
  counts: Record<string, number>;
}

const STAGE_ORDER = ["uploaded", "text_extracted", "parsed", "scored", "failed"];

export default function StatusStrip({ total, counts }: StatusStripProps) {
  return (
    <div className={styles.strip} role="status" aria-label={`Processing status: ${total} files`}>
      <span className={styles.count}>
        <span className={styles.countValue}>{total}</span> files
      </span>
      {STAGE_ORDER.filter((stage) => counts[stage]).map((stage) => (
        <span key={stage} className={styles.count}>
          <span className={styles.countValue}>{counts[stage]}</span> {stage.replace("_", " ")}
        </span>
      ))}
      {Object.keys(counts)
        .filter((stage) => !STAGE_ORDER.includes(stage))
        .map((stage) => (
          <span key={stage} className={styles.count}>
            <span className={styles.countValue}>{counts[stage]}</span> {stage}
          </span>
        ))}
    </div>
  );
}
