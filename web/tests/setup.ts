import { afterEach, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

afterEach(() => {
  // jsdom lacks URL.createObjectURL; restore any test stubs between tests.
  vi.restoreAllMocks();
});
