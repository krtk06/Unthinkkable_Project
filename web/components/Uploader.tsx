"use client";

import { motion, type Variants } from "framer-motion";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { usePrefersReducedMotion } from "@/lib/hooks";
import { validateBatch, type FileRejection } from "@/lib/validation";
import type { UploadResult } from "@/lib/types";
import styles from "./Uploader.module.css";

const dropzoneVariants: Variants = {
  idle: { scale: 1 },
  dragActive: { scale: 1.02, transition: { duration: 0.2, ease: "easeOut" } },
};

interface UploaderProps {
  sessionId: string | null;
  onUploaded: (result: UploadResult) => void;
}

interface PendingFile {
  file: File;
  state: "waiting" | "uploading" | "uploaded" | "failed";
}

export default function Uploader({ sessionId, onUploaded }: UploaderProps) {
  const [dragActive, setDragActive] = useState(false);
  const [pending, setPending] = useState<PendingFile[]>([]);
  const [rejections, setRejections] = useState<FileRejection[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const prefersReduced = usePrefersReducedMotion();
  const sessionIdRef = useRef(sessionId);
  const onUploadedRef = useRef(onUploaded);
  const drainingRef = useRef(false);

  sessionIdRef.current = sessionId;
  onUploadedRef.current = onUploaded;

  const addFiles = useCallback((incoming: File[]) => {
    if (incoming.length === 0) return;
    const { accepted, rejected } = validateBatch(incoming);
    setPending((current) => [
      ...current,
      ...accepted.map((file) => ({ file, state: "waiting" as const })),
    ]);
    setRejections(rejected);
    setErrorMessage(null);
  }, []);

  function handleDrop(event: React.DragEvent) {
    event.preventDefault();
    setDragActive(false);
    addFiles(Array.from(event.dataTransfer.files));
  }

  useEffect(() => {
    if (!sessionId) return;

    if (drainingRef.current) return;
    const waiting = pending.filter((item) => item.state === "waiting");
    if (waiting.length === 0) return;
    drainingRef.current = true;

    setPending((current) =>
      current.map((item) =>
        item.state === "waiting" ? { ...item, state: "uploading" } : item
      )
    );

    api
      .uploadResumes(
        sessionId,
        waiting.map((item) => item.file)
      )
      .then((result) => {
        setPending((current) =>
          current.map((item) =>
            item.state === "uploading" ? { ...item, state: "uploaded" } : item
          )
        );
        setRejections([]);
        onUploadedRef.current(result);
      })
      .catch((err) => {
        setPending((current) =>
          current.map((item) =>
            item.state === "uploading" ? { ...item, state: "failed" } : item
          )
        );
        setErrorMessage(
          err instanceof ApiError
            ? `${err.code}: ${err.message}`
            : "Upload failed. Check that the API is running."
        );
      })
      .finally(() => {
        drainingRef.current = false;
      });
  }, [sessionId, pending]);

  const uploadedCount = pending.filter((item) => item.state === "uploaded").length;

  return (
    <section aria-labelledby="uploader-title">
      <h2 className="visuallyHidden" id="uploader-title">
        Resume upload
      </h2>
      <motion.div
        className={`${styles.dropzone} ${dragActive ? styles.dropzoneActive : ""}`}
        variants={prefersReduced ? undefined : dropzoneVariants}
        animate={prefersReduced ? undefined : dragActive ? "dragActive" : "idle"}
        onDragOver={(event) => {
          event.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
      >
        <label htmlFor={inputId}>Drop resumes here or</label>{" "}
        <button
          type="button"
          className="linkButton"
          onClick={() => inputRef.current?.click()}
        >
          browse files
        </button>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          multiple
          accept=".pdf,.docx,.txt"
          className="visuallyHidden"
          onChange={(event) => {
            addFiles(Array.from(event.target.files ?? []));
            event.target.value = "";
          }}
        />
        <p>PDF, DOCX, or UTF-8 text. Up to 10 MB per file and 100 per batch.</p>
        {!sessionId && (
          <p className="hintText">
            Upload a job description first — resumes are sent automatically.
          </p>
        )}
      </motion.div>

      {(pending.length > 0 || rejections.length > 0) && (
        <ul className={styles.fileList}>
          {pending.map((item) => (
            <li key={`${item.file.name}-${item.file.size}`} className={styles.fileItem}>
              <span className={styles.fileName}>{item.file.name}</span>
              <span
                className={`${styles.fileState} ${
                  item.state === "uploaded" ? styles.stateOk : item.state === "failed" ? styles.stateError : ""
                }`}
              >
                {item.state === "waiting" && !sessionId
                  ? "waiting for JD"
                  : item.state === "waiting"
                    ? "queued"
                    : item.state === "uploading"
                      ? "uploading…"
                      : item.state === "uploaded"
                        ? "uploaded"
                        : "failed"}
              </span>
            </li>
          ))}
          {rejections.map((rejection, index) => (
            <li
              key={`${rejection.file.name}-${index}`}
              className={styles.fileItem}
              aria-label={`Rejected: ${rejection.message}`}
            >
              <span className={styles.fileName}>{rejection.file.name}</span>
              <span className={`${styles.fileState} ${styles.stateError}`} role="alert">
                {rejection.message}
              </span>
            </li>
          ))}
        </ul>
      )}
      {uploadedCount > 0 && (
        <p className="hintText" role="status">
          {uploadedCount} resume{uploadedCount === 1 ? "" : "s"} uploaded — scoring runs
          automatically.
        </p>
      )}
      {errorMessage && (
        <p role="alert" className="fieldError">
          {errorMessage}
        </p>
      )}
    </section>
  );
}
