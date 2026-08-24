import type { ParsedCandidate } from "./types";

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

function highestEducation(candidate: ParsedCandidate): string {
  const sorted = [...candidate.education].sort((a, b) =>
    (a.graduation_date ?? "").localeCompare(b.graduation_date ?? "")
  );
  const top = sorted[sorted.length - 1];
  if (!top) return "";
  return [top.degree, top.field, top.institution].filter(Boolean).join(", ");
}

export function exportJson(candidates: ParsedCandidate[], sessionId: string) {
  const rows = candidates.map((candidate) => ({
    candidate_id: candidate.candidate_id,
    name: candidate.name,
    score: candidate.score ?? null,
    highest_education: highestEducation(candidate),
    skills: candidate.skills,
    experience_years: candidate.experience_years,
    location: candidate.location,
    status: candidate.status,
  }));
  triggerDownload(
    JSON.stringify({ session_id: sessionId, candidates: rows }, null, 2),
    "application/json",
    `candidates-${sessionId}.json`
  );
}

export function exportCsv(candidates: ParsedCandidate[]) {
  const header = [
    "candidate_id",
    "name",
    "score",
    "highest_education",
    "skills",
    "experience_years",
    "location",
    "status",
  ];
  const rows = candidates.map((candidate) =>
    [
      candidate.candidate_id,
      candidate.name ?? "",
      String(candidate.score ?? ""),
      highestEducation(candidate),
      candidate.skills.join(" | "),
      String(candidate.experience_years),
      candidate.location ?? "",
      candidate.status,
    ]
      .map(csvCell)
      .join(",")
  );
  triggerDownload([header.join(","), ...rows].join("\n"), "text/csv", "candidates.csv");
}
