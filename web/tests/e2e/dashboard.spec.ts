import { expect, test, type Page } from "@playwright/test";

const CANDIDATE = {
  candidate_id: "cand_1",
  resume: {
    filename: "jane.pdf",
    content_type: "application/pdf",
    size_bytes: 1024,
    checksum: "abc123",
    status: "scored",
    parsed_json: {
      schema_version: "1.0",
      candidate: {
        name: "Jane Doe",
        contact: { email: "jane@example.com", phone: null, url: null },
        location: "Berlin",
      },
      skills: ["Python", "REST"],
      experience: [
        {
          company: "Acme",
          role: "Backend Engineer",
          start_date: "2021-03",
          end_date: null,
          duration_months: 48,
          description: "Built and operated Python REST services for four years.",
        },
      ],
      education: [
        {
          institution: "TU Berlin",
          degree: "B.Sc.",
          field: "Computer Science",
          graduation_date: "2020-07",
        },
      ],
      certifications: [],
      languages: ["English"],
      warnings: [],
    },
  },
  match: {
    candidate_id: "cand_1",
    score: 8,
    skills_score: 8,
    experience_score: 10,
    education_score: 4,
    matching_skills: ["Python", "REST"],
    missing_skills: ["Kubernetes"],
    semantic_similarity: 6.4,
    analysis: "The candidate is a strong fit.",
    shortlisted: true,
    model: { provider: "openai", model: "gpt-4o-mini", prompt_version: "match-v1" },
  },
};

async function mockApi(page: Page, opts: { statusCallsBeforeScored?: number } = {}) {
  const before = opts.statusCallsBeforeScored ?? 1;
  let statusCalls = 0;

  await page.route("**/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (route.request().method() === "POST" && path === "/v1/sessions") {
      return route.fulfill({ json: { session_id: "sess_e2e" } });
    }
    if (route.request().method() === "POST" && path.endsWith("/job-description")) {
      return route.fulfill({
        status: 202,
        json: {
          session_id: "sess_e2e",
          status: "accepted",
          normalized_requirements: {
            title: "Backend Engineer",
            required: [{ name: "Python", type: "skill" }],
            preferred: [{ name: "Kubernetes", type: "skill" }],
            responsibilities: [],
            ambiguities: [],
          },
        },
      });
    }
    if (route.request().method() === "POST" && path.endsWith("/job-description/file")) {
      return route.fulfill({
        status: 202,
        json: {
          session_id: "sess_e2e",
          status: "accepted",
          normalized_requirements: {
            title: "Backend Engineer",
            required: [{ name: "Python", type: "skill" }],
            preferred: [{ name: "Kubernetes", type: "skill" }],
            responsibilities: [],
            ambiguities: [],
          },
        },
      });
    }
    if (route.request().method() === "POST" && path.endsWith("/resumes")) {
      return route.fulfill({
        status: 202,
        json: {
          session_id: "sess_e2e",
          batch_id: "batch_1",
          accepted: 1,
          rejected: 0,
          files: [{ candidate_id: "cand_1", job_id: "job_1", status: "uploaded" }],
        },
      });
    }
    if (route.request().method() === "GET" && path.endsWith("/status")) {
      statusCalls += 1;
      const pending = statusCalls <= before;
      return route.fulfill({
        json: {
          session_id: "sess_e2e",
          total: 1,
          counts: pending ? { uploaded: 1 } : { scored: 1 },
          files: [
            {
              candidate_id: "cand_1",
              filename: "jane.pdf",
              status: pending ? "uploaded" : "scored",
              error_code: null,
              skills_count: pending ? 0 : 2,
            },
          ],
        },
      });
    }
    if (route.request().method() === "GET" && path.startsWith("/v1/candidates/")) {
      return route.fulfill({ json: CANDIDATE });
    }
    return route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND", message: "nope", details: {} } } });
  });
}

test.describe("full screening flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("srs_token", "test-token");
    });
    await mockApi(page);
  });

  test("upload JD and resume, wait for scoring, see candidate card, export", async ({ page }) => {
    await page.goto("/");

    // Job description is filed via pasted text
    await page.getByLabel(/role title/i).fill("Backend Engineer");
    await page.getByLabel(/job description text/i).fill("Must know Python and REST APIs.");
    await page.getByRole("button", { name: /file job description/i }).click();
    await expect(page.getByText(/required: python/i)).toBeVisible();

    // Resumes auto-upload once the session exists
    const resumeInput = page.getByLabel(/drop resumes here or/i);
    await resumeInput.setInputFiles({
      name: "jane.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 fake"),
    });

    // Candidate card appears with name, education, skills, and score
    await expect(page.getByText("Jane Doe")).toBeVisible();
    await expect(page.getByText(/b\.sc\., computer science/i)).toBeVisible();
    await expect(page.getByText("Python", { exact: true })).toBeVisible();
    await expect(page.getByText("8", { exact: true }).first()).toBeVisible();

    // Exports
    const [jsonDownload] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Export JSON" }).click(),
    ]);
    expect(jsonDownload.suggestedFilename()).toBe("candidates-sess_e2e.json");
    const [csvDownload] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Export CSV" }).click(),
    ]);
    expect(csvDownload.suggestedFilename()).toBe("candidates.csv");
  });

  test("shows a waiting hint before any files are added", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/no candidates yet/i)).toBeVisible();
  });
});
