import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CandidateCard from "@/components/CandidateCard";
import CandidateDetail from "@/components/CandidateDetail";
import JDFileUploader from "@/components/JDFileUploader";
import JobDescriptionForm from "@/components/JobDescriptionForm";
import Uploader from "@/components/Uploader";
import * as api from "@/lib/api";
import type { ParsedCandidate } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  api: {
    createSession: vi.fn(),
    saveJobDescriptionText: vi.fn(),
    uploadJobDescriptionFile: vi.fn(),
    uploadResumes: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    constructor(
      public code: string,
      message: string
    ) {
      super(message);
    }
  },
}));

const mockedApi = vi.mocked(api.api);

function makeFile(name: string, size = 100, type = "application/pdf"): File {
  return new File(["x".repeat(size)], name, { type });
}

function selectFile(input: HTMLInputElement, file: File) {
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function selectFiles(input: HTMLInputElement, files: File[]) {
  Object.defineProperty(input, "files", { value: files, configurable: true });
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

describe("JDFileUploader", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a drop zone with accepted file types", () => {
    render(<JDFileUploader sessionId={null} onSessionCreated={() => undefined} onNormalized={() => undefined} />);
    expect(screen.getByText(/upload files/i)).toBeInTheDocument();
    expect(screen.getByText(/upload job description/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/drop a file here or click to browse/i)).toBeInTheDocument();
  });

  it("validates file extension and rejects unsupported types", async () => {
    render(<JDFileUploader sessionId={null} onSessionCreated={() => undefined} onNormalized={() => undefined} />);
    const input = screen.getByLabelText(/drop a file here or click to browse/i) as HTMLInputElement;
    selectFile(input, makeFile("bad.exe", 100, "application/octet-stream"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unsupported file type");
  });

  it("creates a session and uploads automatically when a valid file is selected", async () => {
    mockedApi.createSession.mockResolvedValue({ session_id: "sess_1" });
    mockedApi.uploadJobDescriptionFile.mockResolvedValue({
      session_id: "sess_1",
      status: "accepted",
      normalized_requirements: {
        title: "Backend Engineer",
        required: [{ name: "Python", type: "skill" }],
        preferred: [],
        responsibilities: [],
        ambiguities: ["'modern stack' is broad; treated as preferred"],
      },
    });
    const onSessionCreated = vi.fn();
    const onNormalized = vi.fn();
    render(<JDFileUploader sessionId={null} onSessionCreated={onSessionCreated} onNormalized={onNormalized} />);

    const input = screen.getByLabelText(/drop a file here or click to browse/i) as HTMLInputElement;
    selectFile(input, makeFile("jd.pdf", 100, "application/pdf"));

    await waitFor(() => {
      expect(onSessionCreated).toHaveBeenCalledWith("sess_1");
    });
    expect(mockedApi.uploadJobDescriptionFile).toHaveBeenCalledWith("sess_1", expect.any(File));
    await waitFor(() => {
      expect(onNormalized).toHaveBeenCalled();
    });
  });

  it("does not require a separate upload step when a session already exists", async () => {
    mockedApi.uploadJobDescriptionFile.mockResolvedValue({
      session_id: "sess_1",
      status: "accepted",
      normalized_requirements: {
        title: "Backend Engineer",
        required: [{ name: "Python", type: "skill" }],
        preferred: [],
        responsibilities: [],
        ambiguities: [],
      },
    });
    const onNormalized = vi.fn();
    render(<JDFileUploader sessionId="sess_1" onSessionCreated={() => undefined} onNormalized={onNormalized} />);

    const input = screen.getByLabelText(/drop a file here or click to browse/i) as HTMLInputElement;
    selectFile(input, makeFile("jd.pdf", 100, "application/pdf"));

    await waitFor(() => {
      expect(onNormalized).toHaveBeenCalled();
    });
    expect(mockedApi.createSession).not.toHaveBeenCalled();
    expect(mockedApi.uploadJobDescriptionFile).toHaveBeenCalledWith("sess_1", expect.any(File));
  });

  it("surfaces an API error without losing the selected file", async () => {
    mockedApi.createSession.mockResolvedValue({ session_id: "sess_1" });
    mockedApi.uploadJobDescriptionFile.mockRejectedValue(
      new api.ApiError("PROVIDER_DOWN", "LLM unavailable", 502)
    );
    render(<JDFileUploader sessionId={null} onSessionCreated={() => undefined} onNormalized={() => undefined} />);

    const input = screen.getByLabelText(/drop a file here or click to browse/i) as HTMLInputElement;
    selectFile(input, makeFile("jd.pdf", 100, "application/pdf"));

    expect(await screen.findByRole("alert")).toHaveTextContent("PROVIDER_DOWN: LLM unavailable");
  });
});

describe("Uploader", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function makeResume(name: string, size = 100): File {
    return new File(["x".repeat(size)], name, { type: "application/pdf" });
  }

  it("waits for a session before uploading and shows a hint", () => {
    render(<Uploader sessionId={null} onUploaded={() => undefined} />);
    expect(screen.getAllByText(/upload resumes/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/upload a job description first/i)).toBeInTheDocument();
  });

  it("lists ready files and rejected validation errors separately", async () => {
    render(<Uploader sessionId={null} onUploaded={() => undefined} />);
    await selectFiles(screen.getByLabelText(/drop resumes here or click to browse/i) as HTMLInputElement, [
      makeResume("good.pdf"),
      makeResume("bad.exe"),
    ]);
    await waitFor(() => {
      expect(screen.getAllByText("good.pdf").length).toBeGreaterThan(0);
    });
    expect(screen.getByText(/only pdf, docx, and utf-8 text files are accepted/i)).toBeInTheDocument();
    expect(screen.queryByText("bad.pdf")).not.toBeInTheDocument();
  });

  it("uploads accepted files automatically once a session exists", async () => {
    mockedApi.uploadResumes.mockResolvedValue({
      session_id: "sess_1",
      batch_id: "batch_1",
      accepted: 1,
      rejected: 0,
      files: [{ candidate_id: "cand_1", job_id: "job_1", status: "uploaded" }],
    });
    const onUploaded = vi.fn();
    render(<Uploader sessionId="sess_1" onUploaded={onUploaded} />);
    selectFiles(screen.getByLabelText(/drop resumes here or click to browse/i) as HTMLInputElement, [makeResume("one.pdf")]);
    await waitFor(() => expect(onUploaded).toHaveBeenCalledTimes(1));
    expect(mockedApi.uploadResumes).toHaveBeenCalledTimes(1);
    const [calledSession, calledFiles, calledKey] = mockedApi.uploadResumes.mock.calls[0]!;
    expect(calledSession).toBe("sess_1");
    expect(calledFiles).toHaveLength(1);
    expect(calledFiles![0]).toBeInstanceOf(File);
    expect(calledKey === undefined || typeof calledKey === "string").toBe(true);
  });

  it("shows an error banner when the API rejects the upload", async () => {
    mockedApi.uploadResumes.mockRejectedValue(new api.ApiError("SESSION_NOT_FOUND", "gone", 404));
    render(<Uploader sessionId="sess_1" onUploaded={() => undefined} />);
    selectFiles(screen.getByLabelText(/drop resumes here or click to browse/i) as HTMLInputElement, [makeResume("one.pdf")]);
    expect(await screen.findByRole("alert")).toHaveTextContent("SESSION_NOT_FOUND: gone");
  });
});

describe("JobDescriptionForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("creates a session and files the pasted job description", async () => {
    const user = userEvent.setup();
    mockedApi.createSession.mockResolvedValue({ session_id: "sess_1" });
    mockedApi.saveJobDescriptionText.mockResolvedValue({
      session_id: "sess_1",
      status: "accepted",
      normalized_requirements: {
        title: "Backend Engineer",
        required: [{ name: "Python", type: "skill" }],
        preferred: [],
        responsibilities: [],
        ambiguities: [],
      },
    });
    const onSessionCreated = vi.fn();
    const onNormalized = vi.fn();
    render(
      <JobDescriptionForm
        sessionId={null}
        onSessionCreated={onSessionCreated}
        onNormalized={onNormalized}
      />
    );

    await user.type(screen.getByLabelText(/role title/i), "Backend Engineer");
    await user.type(screen.getByLabelText(/job description text/i), "Must know Python");
    await user.click(screen.getByRole("button", { name: /file job description/i }));

    await waitFor(() => expect(onSessionCreated).toHaveBeenCalledWith("sess_1"));
    expect(mockedApi.saveJobDescriptionText).toHaveBeenCalledWith(
      "sess_1",
      "Must know Python",
      "Backend Engineer"
    );
    await waitFor(() => expect(onNormalized).toHaveBeenCalled());
  });

  it("rejects an empty description without calling the API", async () => {
    const user = userEvent.setup();
    render(
      <JobDescriptionForm
        sessionId="sess_1"
        onSessionCreated={() => undefined}
        onNormalized={() => undefined}
      />
    );
    await user.click(screen.getByRole("button", { name: /file job description/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a job description");
    expect(mockedApi.saveJobDescriptionText).not.toHaveBeenCalled();
  });
});

const scoredCandidate: ParsedCandidate = {
  candidate_id: "cand_1",
  name: "Jane Doe",
  email: "jane@example.com",
  phone: null,
  location: "Berlin",
  skills: ["Python", "REST"],
  experience_years: 4,
  experience: [
    {
      company: "Acme",
      role: "Backend Engineer",
      start_date: "2021-03",
      end_date: null,
      duration_months: 48,
      description: "Built REST services.",
    },
  ],
  education: [
    { institution: "TU Berlin", degree: "B.Sc.", field: "Computer Science", graduation_date: "2020-07" },
  ],
  status: "scored",
  score: 7.2,
  skills_score: 8.5,
  experience_score: 7,
  education_score: 4.5,
  matching_skills: ["Python", "REST"],
  missing_skills: ["Kubernetes"],
  semantic_similarity: 6.4,
  analysis: "Strong fit with minor gaps.",
  shortlisted: true,
  raw_text: "Jane Doe resume text.",
  filename: "jane.pdf",
};

describe("CandidateCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.confirm = vi.fn(() => true);
  });

  it("renders score, avatar, skill chips, and shortlist badge", () => {
    render(<CandidateCard candidate={scoredCandidate} />);
    expect(screen.getByRole("img", { name: /match score 7\.2/i })).toBeInTheDocument();
    expect(screen.getByText("Jane Doe")).toBeInTheDocument();
    expect(screen.getByText("Shortlisted")).toBeInTheDocument();
    expect(screen.getByText("Key skills")).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("REST")).toBeInTheDocument();
    expect(screen.getByText("Kubernetes")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view details/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /schedule interview/i })).toBeInTheDocument();
  });

  it("hides the shortlist badge when not shortlisted", () => {
    render(<CandidateCard candidate={{ ...scoredCandidate, shortlisted: false }} />);
    expect(screen.queryByText("Shortlisted")).not.toBeInTheDocument();
  });

  it("shows a pending state for unscored candidates without a score", () => {
    render(<CandidateCard candidate={{ ...scoredCandidate, status: "scoring", score: undefined }} />);
    expect(screen.getByText(/scoring…/i)).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /match score 7\.2/i })).not.toBeInTheDocument();
  });

  it("shows an error state for failed candidates", () => {
    render(<CandidateCard candidate={{ ...scoredCandidate, status: "failed" }} />);
    expect(screen.getByText(/failed to process/i)).toBeInTheDocument();
  });

  it("calls onDelete after confirmation via the details modal", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(<CandidateCard candidate={scoredCandidate} onDelete={onDelete} />);
    await user.click(screen.getByRole("button", { name: /view details/i }));
    await user.click(screen.getByRole("button", { name: /delete candidate/i }));
    expect(window.confirm).toHaveBeenCalledOnce();
    expect(onDelete).toHaveBeenCalledWith("cand_1");
  });

  it("does not delete when confirmation is declined", async () => {
    window.confirm = vi.fn(() => false);
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(<CandidateCard candidate={scoredCandidate} onDelete={onDelete} />);
    await user.click(screen.getByRole("button", { name: /view details/i }));
    await user.click(screen.getByRole("button", { name: /delete candidate/i }));
    expect(onDelete).not.toHaveBeenCalled();
  });
});

describe("CandidateDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when closed", () => {
    const { container } = render(
      <CandidateDetail candidate={scoredCandidate} open={false} onClose={() => undefined} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows breakdown, contact, and skills tab content when open", async () => {
    const user = userEvent.setup();
    render(<CandidateDetail candidate={scoredCandidate} open onClose={() => undefined} />);
    expect(screen.getByRole("dialog", { name: /jane doe/i })).toBeInTheDocument();
    expect(screen.getAllByText("7.2").length).toBeGreaterThan(0);
    expect(screen.getByText(/semantic similarity 6\.4\/10/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Experience" }));
    expect(screen.getByText(/experience \(4 yrs detected\)/i)).toBeInTheDocument();
    expect(screen.getByText(/built rest services\./i)).toBeInTheDocument();
  });

  it("switches to the education tab and shows the degree", async () => {
    const user = userEvent.setup();
    render(<CandidateDetail candidate={scoredCandidate} open onClose={() => undefined} />);
    await user.click(screen.getByRole("button", { name: "Education" }));
    expect(screen.getByText(/b\.sc\., computer science @ tu berlin • 2020/i)).toBeInTheDocument();
  });

  it("switches to the raw text tab and shows extracted text", async () => {
    const user = userEvent.setup();
    render(<CandidateDetail candidate={scoredCandidate} open onClose={() => undefined} />);
    await user.click(screen.getByRole("button", { name: /raw resume text/i }));
    expect(screen.getByText(/jane doe resume text\./i)).toBeInTheDocument();
  });

  it("closes on close button and on Escape", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<CandidateDetail candidate={scoredCandidate} open onClose={onClose} />);
    await user.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalledOnce();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
