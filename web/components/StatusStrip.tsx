import { GridPatternCard, GridPatternCardBody } from "./ui/grid-pattern-card";

interface StatusStripProps {
  total: number;
  counts: Record<string, number>;
}

const STAGE_ORDER = ["uploaded", "text_extracted", "parsed", "scored", "failed"];

export default function StatusStrip({ total, counts }: StatusStripProps) {
  return (
    <GridPatternCard>
      <GridPatternCardBody
        className="flex flex-wrap gap-3 items-center"
        role="status"
        aria-label={`Processing status: ${total} files`}
      >
        <span className="inline-flex items-baseline gap-1 font-data text-text">
          <span className="font-medium text-base">{total}</span> files
        </span>
        {STAGE_ORDER.filter((stage) => counts[stage]).map((stage) => (
          <span key={stage} className="inline-flex items-baseline gap-1 font-data text-text-secondary">
            <span className="font-medium text-base">{counts[stage]}</span> {stage.replace("_", " ")}
          </span>
        ))}
        {Object.keys(counts)
          .filter((stage) => !STAGE_ORDER.includes(stage))
          .map((stage) => (
            <span key={stage} className="inline-flex items-baseline gap-1 font-data text-text-secondary">
              <span className="font-medium text-base">{counts[stage]}</span> {stage}
            </span>
          ))}
      </GridPatternCardBody>
    </GridPatternCard>
  );
}