"use client";

import { motion, type Variants } from "framer-motion";
import { useCallback, useId, useRef, useState } from "react";
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

type UploadPhase = "idle" | "uploading" | "done" | "error";

export default function Uploader({ sessionId, onUploaded }: UploaderProps) {
  const [dragActive, setDragActive] = useState(false);
  const [pending, setPending] = useState<File[]>([]);
  const [rejections, setRejections] = useState<FileRejection[]>([]);
  const [phase, setPhase] = useState<UploadPhase>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const prefersReduced = usePrefersReducedMotion();

  const addFiles = useCallback((incoming: File[]) => {
    if (incoming.length === 0) return;
    const { accepted, rejected } = validateBatch(incoming);
    setPending((current) => [...current, ...accepted]);
    setRejections(rejected);
    setPhase("idle");
    setErrorMessage(null);
  }, []);

  function handleDrop(event: React.DragEvent) {
    event.preventDefault();
    setDragActive(false);
    addFiles(Array.from(event.dataTransfer.files));
  }

  async function handleUpload() {
    if (!sessionId || pending.length === 0) return;
    setPhase("uploading");
    setErrorMessage(null);
    try {
      const result = await api.uploadResumes(sessionId, pending);
      setPhase("done");
      onUploaded(result);
      setPending([]);
      setRejections([]);
    } catch (err) {
      setPhase("error");
      setErrorMessage(
        err instanceof ApiError ? `${err.code}: ${err.message}` : "Upload failed. Check that the API is running."
      );
    }
  }

  const disabled = !sessionId || pending.length === 0 || phase === "uploading";

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
          disabled={!sessionId}
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
      </motion.div>

      {(pending.length > 0 || rejections.length > 0) && (
        <>
          <ul className={styles.fileList}>
            {pending.map((file) => (
              <li key={`${file.name}-${file.size}`} className={styles.fileItem}>
                <span className={styles.fileName}>{file.name}</span>
                <span className={`${styles.fileState} ${styles.stateOk}`}>ready</span>
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
          <button className="primaryButton" type="button" onClick={handleUpload} disabled={disabled}>
            {phase === "uploading" ? "Uploading…" : `Upload ${pending.length} resume${pending.length === 1 ? "" : "s"}`}
          </button>
        </>
      )}
      {phase === "error" && errorMessage && (
        <p role="alert" className="fieldError">
          {errorMessage}
        </p>
      )}
      {!sessionId && (
        <p className="hintText">Start a session with a job description to enable uploads.</p>
      )}
    </section>
  );
}
