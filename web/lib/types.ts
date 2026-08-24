export interface ModelMetadata {
  provider: string;
  model: string;
  prompt_version: string;
}

export interface Match {
  candidate_id: string;
  score: number;
  skills_score: number;
  experience_score: number;
  education_score: number;
  matching_skills: string[];
  missing_skills: string[];
  semantic_similarity: number;
  analysis: string;
  shortlisted: boolean;
  model: ModelMetadata;
}

export interface Requirement {
  name: string;
  type: "skill" | "experience" | "education" | "certification" | "constraint";
  minimum?: string | null;
}

export interface NormalizedRequirements {
  title?: string | null;
  summary?: string | null;
  required: Requirement[];
  preferred: Requirement[];
  responsibilities: string[];
  ambiguities: string[];
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

export interface AcceptedFile {
  candidate_id: string;
  job_id: string;
  status: string;
}

export interface RejectedFile {
  filename: string;
  status: "failed";
  error: { code: string; message: string; details: Record<string, unknown> };
}

export interface UploadResult {
  session_id: string;
  batch_id: string;
  accepted: number;
  rejected: number;
  files: (AcceptedFile | RejectedFile)[];
}

export interface StatusFile {
  candidate_id: string;
  filename: string | null;
  status: string | null;
  error_code: string | null;
  skills_count?: number;
}

export interface SessionStatus {
  session_id: string;
  total: number;
  counts: Record<string, number>;
  files: StatusFile[];
}

export interface MatchesPage {
  session_id: string;
  matches: Match[];
  next_cursor: string | null;
}

export interface ExperienceRecord {
  company: string | null;
  role: string | null;
  start_date: string | null;
  end_date: string | null;
  duration_months: number | null;
  description: string;
  evidence?: string[];
}

export interface EducationRecord {
  institution: string | null;
  degree: string | null;
  field: string | null;
  graduation_date: string | null;
}

export interface CertificationRecord {
  name: string;
  issuer: string | null;
  date: string | null;
}

export interface ExtractedResume {
  schema_version: string;
  candidate: {
    name: string | null;
    contact: { email: string | null; phone: string | null; url: string | null };
    location: string | null;
  };
  skills: string[];
  experience: ExperienceRecord[];
  education: EducationRecord[];
  certifications: CertificationRecord[];
  languages: string[];
  warnings: string[];
}

export interface CandidateDetail {
  candidate_id: string;
  id?: string;
  resume: {
    filename?: string | null;
    content_type?: string | null;
    size_bytes?: number | null;
    checksum?: string | null;
    storage_uri?: string | null;
    status?: string | null;
    error_code?: string | null;
    parsed_json?: ExtractedResume | null;
    created_at?: string | null;
    updated_at?: string | null;
    [key: string]: unknown;
  };
  match?: Match | Record<string, unknown> | null;
  [key: string]: unknown;
}

export interface ParsedCandidate {
  candidate_id: string;
  name: string | null;
  email: string | null;
  phone: string | null;
  location: string | null;
  skills: string[];
  experience_years: number;
  experience: ExperienceRecord[];
  education: EducationRecord[];
  status: "parsed" | "scoring" | "scored" | "failed";
  score?: number;
  skills_score?: number;
  experience_score?: number;
  education_score?: number;
  matching_skills?: string[];
  missing_skills?: string[];
  semantic_similarity?: number;
  analysis?: string;
  shortlisted?: boolean;
  filename?: string | null;
}
