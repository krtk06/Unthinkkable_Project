import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import JDFileUploader from "@/components/JDFileUploader";
import Uploader from "@/components/Uploader";
import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    createSession: vi.fn(),
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
    expect(screen.getByText(/drop a job description here or/i)).toBeInTheDocument();
    expect(screen.getByText(/pdf, docx, or txt/i)).toBeInTheDocument();
  });

  it("validates file extension and rejects unsupported types", async () => {
    render(<JDFileUploader sessionId={null} onSessionCreated={() => undefined} onNormalized={() => undefined} />);
    const input = screen.getByLabelText(/drop a job description file or click to browse/i) as HTMLInputElement;
    selectFile(input, makeFile("bad.exe", 100, "application/octet-stream"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unsupported file type");
  });

  it("shows file info and remove button after selecting a valid file", async () => {
    render(<JDFileUploader sessionId={null} onSessionCreated={() => undefined} onNormalized={() => undefined} />);
    const input = screen.getByLabelText(/drop a job description file or click to browse/i) as HTMLInputElement;
    selectFile(input, makeFile("jd.pdf", 1024, "application/pdf"));
    expect(await screen.findByText("jd.pdf")).toBeInTheDocument();
    expect(screen.getByText(/remove/i)).toBeInTheDocument();
  });

  it("creates a session, uploads the file, and reports normalized requirements", async () => {
    const user = userEvent.setup();
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

    const input = screen.getByLabelText(/drop a job description file or click to browse/i) as HTMLInputElement;
    selectFile(input, makeFile("jd.pdf", 100, "application/pdf"));
    await user.click(await screen.findByRole("button", { name: /analyze/i }));

    await waitFor(() => {
      expect(onSessionCreated).toHaveBeenCalledWith("sess_1");
    });
    expect(mockedApi.uploadJobDescriptionFile).toHaveBeenCalledWith("sess_1", expect.any(File));
    await waitFor(() => {
      expect(onNormalized).toHaveBeenCalled();
    });
  });

  it("surfaces an API error without losing the selected file", async () => {
    const user = userEvent.setup();
    mockedApi.createSession.mockResolvedValue({ session_id: "sess_1" });
    mockedApi.uploadJobDescriptionFile.mockRejectedValue(
      new api.ApiError("PROVIDER_DOWN", "LLM unavailable", 502)
    );
    render(<JDFileUploader sessionId={null} onSessionCreated={() => undefined} onNormalized={() => undefined} />);

    const input = screen.getByLabelText(/drop a job description file or click to browse/i) as HTMLInputElement;
    selectFile(input, makeFile("jd.pdf", 100, "application/pdf"));
    await user.click(await screen.findByRole("button", { name: /analyze/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("PROVIDER_DOWN: LLM unavailable");
    expect(screen.getByText("jd.pdf")).toBeInTheDocument();
  });
});

describe("Uploader", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function makeResume(name: string, size = 100): File {
    return new File(["x".repeat(size)], name, { type: "application/pdf" });
  }

  it("disables browsing before a session exists and shows a hint", () => {
    render(<Uploader sessionId={null} onUploaded={() => undefined} />);
    expect(screen.getByRole("button", { name: /browse files/i })).toBeDisabled();
    expect(screen.getByText(/start a session with a job description/i)).toBeInTheDocument();
  });

  it("lists ready files and rejected validation errors separately", async () => {
    const user = userEvent.setup();
    render(<Uploader sessionId="sess_1" onUploaded={() => undefined} />);
    await user.click(screen.getByRole("button", { name: /browse files/i }));
    selectFiles(screen.getByLabelText(/drop resumes here or/i) as HTMLInputElement, [
      makeResume("good.pdf"),
      makeResume("bad.exe"),
    ]);
    expect(screen.getByText("good.pdf")).toBeInTheDocument();
    expect(screen.getByText(/only pdf, docx, and utf-8 text files are accepted/i)).toBeInTheDocument();
    expect(screen.queryByText("bad.pdf")).not.toBeInTheDocument();
  });

  it("uploads accepted files and reports the batch result", async () => {
    const user = userEvent.setup();
    mockedApi.uploadResumes.mockResolvedValue({
      session_id: "sess_1",
      batch_id: "batch_1",
      accepted: 1,
      rejected: 0,
      files: [{ candidate_id: "cand_1", job_id: "job_1", status: "uploaded" }],
    });
    const onUploaded = vi.fn();
    render(<Uploader sessionId="sess_1" onUploaded={onUploaded} />);
    await user.click(screen.getByRole("button", { name: /browse files/i }));
    selectFiles(screen.getByLabelText(/drop resumes here or/i) as HTMLInputElement, [makeResume("one.pdf")]);
    await user.click(screen.getByRole("button", { name: /upload 1 resume/i }));
    await waitFor(() => expect(onUploaded).toHaveBeenCalledTimes(1));
    expect(mockedApi.uploadResumes).toHaveBeenCalledTimes(1);
    const [calledSession, calledFiles, calledKey] = mockedApi.uploadResumes.mock.calls[0]!;
    expect(calledSession).toBe("sess_1");
    expect(calledFiles).toHaveLength(1);
    expect(calledFiles![0]).toBeInstanceOf(File);
    expect(calledKey === undefined || typeof calledKey === "string").toBe(true);
  });

  it("shows an error banner when the API rejects the upload", async () => {
    const user = userEvent.setup();
    mockedApi.uploadResumes.mockRejectedValue(new api.ApiError("SESSION_NOT_FOUND", "gone", 404));
    render(<Uploader sessionId="sess_1" onUploaded={() => undefined} />);
    await user.click(screen.getByRole("button", { name: /browse files/i }));
    selectFiles(screen.getByLabelText(/drop resumes here or/i) as HTMLInputElement, [makeResume("one.pdf")]);
    await user.click(screen.getByRole("button", { name: /upload 1 resume/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("SESSION_NOT_FOUND: gone");
  });
});
