import { describe, expect, it } from "vitest";
import { validateBatch, validateFile } from "@/lib/validation";

function makeFile(name: string, size: number, type = "application/pdf"): File {
  const file = new File(["x".repeat(Math.max(size, 1))], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

describe("validateFile", () => {
  it("accepts pdf, docx, and txt files within limits", () => {
    expect(validateFile(makeFile("a.pdf", 100))).toBeNull();
    expect(validateFile(makeFile("b.docx", 100))).toBeNull();
    expect(validateFile(makeFile("c.txt", 100, "text/plain"))).toBeNull();
  });

  it("rejects unsupported extensions", () => {
    const rejection = validateFile(makeFile("virus.exe", 100));
    expect(rejection?.code).toBe("UNSUPPORTED_FILE_TYPE");
  });

  it("rejects empty files", () => {
    const rejection = validateFile(makeFile("empty.pdf", 0));
    expect(rejection?.code).toBe("EMPTY_FILE");
  });

  it("rejects files over 10 MB", () => {
    const rejection = validateFile(makeFile("big.pdf", 10 * 1024 * 1024 + 1));
    expect(rejection?.code).toBe("FILE_TOO_LARGE");
  });
});

describe("validateBatch", () => {
  it("separates accepted and rejected files", () => {
    const result = validateBatch([makeFile("ok.pdf", 10), makeFile("bad.exe", 10)]);
    expect(result.accepted).toHaveLength(1);
    expect(result.rejected).toHaveLength(1);
    expect(result.rejected[0]?.code).toBe("UNSUPPORTED_FILE_TYPE");
  });

  it("caps the batch at 100 accepted files", () => {
    const files = Array.from({ length: 105 }, (_, i) => makeFile(`r${i}.pdf`, 10));
    const result = validateBatch(files);
    expect(result.accepted).toHaveLength(100);
    expect(result.rejected.filter((r) => r.code === "BATCH_TOO_LARGE")).toHaveLength(5);
  });
});
