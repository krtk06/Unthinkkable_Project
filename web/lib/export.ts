import type { Match } from "./types";

function triggerDownload(content: string, mimeType: string, filename: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function csvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

export function exportJson(matches: Match[], sessionId: string) {
  triggerDownload(
    JSON.stringify({ session_id: sessionId, matches }, null, 2),
    "application/json",
    `matches-${sessionId}.json`
  );
}

export function exportCsv(matches: Match[]) {
  const header = [
    "candidate_id",
    "score",
    "required_coverage",
    "preferred_coverage",
    "strengths",
    "gaps",
    "uncertainty",
  ];
  const rows = matches.map((match) =>
    [
      match.candidate_id,
      String(match.score),
      String(match.required_coverage),
      String(match.preferred_coverage),
      match.strengths.join(" | "),
      match.gaps.join(" | "),
      match.uncertainty.join(" | "),
    ]
      .map(csvCell)
      .join(",")
  );
  triggerDownload([header.join(","), ...rows].join("\n"), "text/csv", "matches.csv");
}
