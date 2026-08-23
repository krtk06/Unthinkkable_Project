import { expect, test, type Page } from "@playwright/test";

const MATCH = {
  candidate_id: "cand_1",
  score: 8,
  required_coverage: 0.9,
  preferred_coverage: 0.5,
  strengths: ["Four years of Python REST-service experience"],
  gaps: ["Kubernetes experience not found"],
  evidence: [
    {
      claim: "Python REST APIs",
      source: "experience[0].description",
      quote: "Built and operated Python REST services for four years.",
    },
  ],
  uncertainty: [],
  model: { provider: "openai", model: "gpt-4o-mini", prompt_version: "match-v1" },
};

// Focused inputs make Chromium re-scroll them into view on layout, which
// fights programmatic scrolling on small viewports. Release focus before
// interacting with elements far from the last filled field.
async function releaseFocus(page: Page) {
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
}

async function mockApi(page: Page, opts: { statusCallsBeforeScored?: number } = {}) {  let statusCalls = 0;
  const before = opts.statusCallsBeforeScored ?? 1;

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
            },
          ],
        },
      });
    }
    if (route.request().method() === "GET" && path.endsWith("/matches")) {
      return route.fulfill({
        json: { session_id: "sess_e2e", matches: [MATCH], next_cursor: null },
      });
    }
    if (route.request().method() === "GET" && path.startsWith("/v1/candidates/")) {
      return route.fulfill({
        json: {
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
              education: [],
              certifications: [],
              languages: ["English"],
              warnings: [],
            },
          },
          match: MATCH,
        },
      });
    }
    return route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND", message: "nope", details: {} } } });
  });
}

test.describe("full screening flow", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
  });

  test("create session, upload, wait for scoring, inspect evidence, export", async ({ page }) => {
    await page.goto("/");

    // Session setup
    const jdInput = page.getByLabel(/paste the job description/i);
    await jdInput.fill("Must have Python. Nice to have Kubernetes.");
    await page.getByRole("button", { name: "Start session" }).click();
    await releaseFocus(page);
    await expect(page.getByText(/required: python/i)).toBeVisible();

    // Upload
    await page.setInputFiles('input[type="file"]', {
      name: "jane.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 fake"),
    });
    await expect(page.getByText("jane.pdf")).toBeVisible();
    await releaseFocus(page);
    await page.getByRole("button", { name: /upload 1 resume/i }).click();

    // Status settles after polling, then matches load
    await expect(page.getByRole("status").first()).toContainText("1 file");
    const row = page.locator("table tbody tr");
    await expect(row).toHaveCount(1);
    await expect(row.first()).toContainText("8");

    // Detail view with evidence
    await page.getByRole("button", { name: "cand_1" }).click();
    await expect(page.getByRole("region", { name: /candidate cand_1 details/i })).toBeVisible();
    await expect(page.getByText(/strong alignment/i).first()).toBeVisible();
    await page.getByRole("tab", { name: "Evidence" }).click();
    await expect(page.getByText(/built and operated python rest services/i)).toBeVisible();
    await page.getByRole("tab", { name: "Parsed" }).click();
    await expect(page.getByText("Jane Doe")).toBeVisible();

    // Exports
    const [jsonDownload] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Export JSON" }).click(),
    ]);
    expect(jsonDownload.suggestedFilename()).toBe("matches-sess_e2e.json");
    const [csvDownload] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Export CSV" }).click(),
    ]);
    expect(csvDownload.suggestedFilename()).toBe("matches.csv");
  });

  test("filters re-query the API", async ({ page }) => {
    await page.goto("/");
    const jdInput = page.getByLabel(/paste the job description/i);
    await jdInput.fill("Must have Python.");
    await page.getByRole("button", { name: "Start session" }).click();
    await releaseFocus(page);

    let requestedThreshold: string | null = null;
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (url.pathname.endsWith("/matches")) {
        requestedThreshold = url.searchParams.get("threshold");
      }
    });

    await page.getByLabel("Minimum score").fill("9");
    await releaseFocus(page);
    await page.getByRole("button", { name: "Apply filters" }).click();
    expect(requestedThreshold).toBe("9");
  });
});
