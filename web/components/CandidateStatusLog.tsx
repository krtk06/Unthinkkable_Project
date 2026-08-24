import type { SessionStatus } from "@/lib/types";
import { GridPatternCard, GridPatternCardBody } from "./ui/grid-pattern-card";

interface CandidateStatusLogProps {
  status: SessionStatus | null;
}

function describe(file: {
  filename: string | null;
  status: string | null;
  skills_count?: number;
  error_code: string | null;
}): string {
  const name = file.filename ?? "unnamed file";
  switch (file.status) {
    case "parsed":
    case "scored":
    case "scoring":
    case "score_failed": {
      const skillText =
        file.skills_count === 1 ? "1 skill found" : `${file.skills_count ?? 0} skills found`;
      return `${name} - parsed (${skillText})`;
    }
    case "failed":
      return `${name} - failed (${file.error_code ?? "unknown error"})`;
    case "uploaded":
      return `${name} - uploaded`;
    case "text_extracted":
      return `${name} - extracting text`;
    case "processing":
      return `${name} - processing`;
    case "queued":
    default:
      return `${name} - queued`;
  }
}

export default function CandidateStatusLog({ status }: CandidateStatusLogProps) {
  if (!status) return null;

  const total = status.total;
  const files = status.files;

  return (
    <GridPatternCard>
      <GridPatternCardBody className="space-y-2">
        <p className="text-sm font-medium text-text">
          {total} candidate{total === 1 ? "" : "s"}
        </p>
        {files.length > 0 && (
          <ul className="space-y-1 max-h-56 overflow-y-auto">
            {files.map((file) => (
              <li key={file.candidate_id} className="text-xs text-text-secondary">
                {describe(file)}
              </li>
            ))}
          </ul>
        )}
      </GridPatternCardBody>
    </GridPatternCard>
  );
}