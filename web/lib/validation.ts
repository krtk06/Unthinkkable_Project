export const MAX_FILE_BYTES = 10 * 1024 * 1024;
export const MAX_BATCH_FILES = 100;
export const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt"] as const;

export type FileErrorCode =
  | "UNSUPPORTED_FILE_TYPE"
  | "FILE_TOO_LARGE"
  | "EMPTY_FILE"
  | "BATCH_TOO_LARGE";

export interface FileRejection {
  file: File;
  code: FileErrorCode;
  message: string;
}

export interface ValidationResult {
  accepted: File[];
  rejected: FileRejection[];
}

function extensionOf(filename: string): string {
  const index = filename.lastIndexOf(".");
  return index === -1 ? "" : filename.slice(index).toLowerCase();
}

export function validateFile(file: File): FileRejection | null {
  if (!ALLOWED_EXTENSIONS.includes(extensionOf(file.name) as (typeof ALLOWED_EXTENSIONS)[number])) {
    return {
      file,
      code: "UNSUPPORTED_FILE_TYPE",
      message: `${file.name}: only PDF, DOCX, and UTF-8 text files are accepted`,
    };
  }
  if (file.size === 0) {
    return { file, code: "EMPTY_FILE", message: `${file.name}: file is empty` };
  }
  if (file.size > MAX_FILE_BYTES) {
    return { file, code: "FILE_TOO_LARGE", message: `${file.name}: files must be 10 MB or smaller` };
  }
  return null;
}

export function validateBatch(files: File[]): ValidationResult {
  const accepted: File[] = [];
  const rejected: FileRejection[] = [];
  for (const file of files) {
    const rejection = validateFile(file);
    if (rejection) rejected.push(rejection);
    else if (accepted.length < MAX_BATCH_FILES) accepted.push(file);
    else
      rejected.push({
        file,
        code: "BATCH_TOO_LARGE",
        message: `${file.name}: a batch may contain at most ${MAX_BATCH_FILES} files`,
      });
  }
  return { accepted, rejected };
}
