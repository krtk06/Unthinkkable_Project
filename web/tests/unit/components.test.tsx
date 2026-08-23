import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import JobDescriptionForm from "@/components/JobDescriptionForm";
import Uploader from "@/components/Uploader";
import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    createSession: vi.fn(),
    saveJobDescription: vi.fn(),
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

describe("JobDescriptionForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a validation error when submitted without text", async () => {
    const user = userEvent.setup();
    render(<JobDescriptionForm sessionId={null} onSessionCreated={() => undefined} />);
    await user.click(screen.getByRole("button", { name: "Start session" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter a job description first."
    );
    expect(mockedApi.createSession).not.toHaveBeenCalled();
  });

  it("creates a session, normalizes the JD, and shows ambiguities", async () => {
    const user = userEvent.setup();
    mockedApi.createSession.mockResolvedValue({ session_id: "sess_1" });
    mockedApi.saveJobDescription.mockResolvedValue({
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
    render(<JobDescriptionForm sessionId={null} onSessionCreated={onSessionCreated} />);

    await user.type(screen.getByLabelText(/paste the job description/i), "Must have Python");
    await user.click(screen.getByRole("button", { name: "Start session" }));

    await waitFor(() => {
      expect(onSessionCreated).toHaveBeenCalledWith("sess_1");
    });
    expect(mockedApi.saveJobDescription).toHaveBeenCalledWith("sess_1", "Must have Python");
    expect(
      await screen.findByText(/treated as preferred — review before scoring/i)
    ).toBeInTheDocument();
  });

  it("surfaces an API error without losing the entered text", async () => {
    const user = userEvent.setup();
    mockedApi.createSession.mockRejectedValue(new api.ApiError("PROVIDER_DOWN", "LLM unavailable", 502));
    render(<JobDescriptionForm sessionId={null} onSessionCreated={() => undefined} />);
    await user.type(screen.getByLabelText(/paste the job description/i), "Backend role");
    await user.click(screen.getByRole("button", { name: "Start session" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("PROVIDER_DOWN: LLM unavailable");
  });
});

describe("Uploader", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function makeFile(name: string, size = 100): File {
    return new File(["x".repeat(size)], name, { type: "application/pdf" });
  }

  function uploadToInput(input: HTMLInputElement, files: File[]) {
    Object.defineProperty(input, "files", { value: files, configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
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
    uploadToInput(screen.getByLabelText(/drop resumes here or/i), [
      makeFile("good.pdf"),
      makeFile("bad.exe"),
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
    uploadToInput(screen.getByLabelText(/drop resumes here or/i), [makeFile("one.pdf")]);
    await user.click(screen.getByRole("button", { name: /upload 1 resume/i }));
    await waitFor(() => expect(onUploaded).toHaveBeenCalledTimes(1));
    expect(mockedApi.uploadResumes).toHaveBeenCalledTimes(1);
    const [calledSession, calledFiles, calledKey] = mockedApi.uploadResumes.mock.calls[0]!;
    expect(calledSession).toBe("sess_1");
    expect(calledFiles).toHaveLength(1);
    expect(calledFiles![0]).toBeInstanceOf(File);
    // Browsers send a generated Idempotency-Key; jsdom has no crypto.randomUUID.
    expect(calledKey === undefined || typeof calledKey === "string").toBe(true);
  });

  it("shows an error banner when the API rejects the upload", async () => {
    const user = userEvent.setup();
    mockedApi.uploadResumes.mockRejectedValue(new api.ApiError("SESSION_NOT_FOUND", "gone", 404));
    render(<Uploader sessionId="sess_1" onUploaded={() => undefined} />);
    await user.click(screen.getByRole("button", { name: /browse files/i }));
    uploadToInput(screen.getByLabelText(/drop resumes here or/i), [makeFile("one.pdf")]);
    await user.click(screen.getByRole("button", { name: /upload 1 resume/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("SESSION_NOT_FOUND: gone");
  });
});
