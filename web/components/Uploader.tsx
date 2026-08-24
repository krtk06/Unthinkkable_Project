"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { validateBatch, type FileRejection } from "@/lib/validation";
import type { UploadResult } from "@/lib/types";
import { FileUpload } from "./ui/file-upload";
import { GridPatternCard, GridPatternCardBody } from "./ui/grid-pattern-card";
import { ShiningText } from "./ui/shining-text";
import { motion } from "framer-motion";
import styles from "./Uploader.module.css";

interface UploaderProps {
  sessionId: string | null;
  onUploaded: (result: UploadResult) => void;
}

interface PendingFile {
  file: File;
  state: "waiting" | "uploading" | "uploaded" | "failed";
}

export default function Uploader({ sessionId, onUploaded }: UploaderProps) {
  const [pending, setPending] = useState<PendingFile[]>([]);
  const [rejections, setRejections] = useState<FileRejection[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
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

  return (
    <GridPatternCard className="flex flex-col">
      <GridPatternCardBody className="flex flex-col flex-1 p-0">
        <div className="flex items-start justify-between gap-2 p-5 pb-2">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-zinc-200">Upload Resumes</h2>
            <p className="mt-0.5 text-xs text-zinc-500">Drag or drop resume files here (PDF, DOCX) or click to upload.</p>
          </div>
          <span className="rounded bg-zinc-900 px-1.5 py-0.5 font-data text-[10px] tracking-widest text-zinc-500 ring-1 ring-white/[0.06]">RESUMES · BATCH</span>
        </div>

        <div className="flex-1 px-3 pb-3">
          <div className="rounded-xl border border-dashed border-white/10 bg-zinc-900/30">
            <FileUpload onChange={addFiles} multiple accept=".pdf,.docx,.txt" />
          </div>
        </div>

        {(pending.length > 0 || rejections.length > 0) && (
          <motion.ul
            className={`${styles.fileList} mx-5 mb-2`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            {pending.map((item) => (
              <motion.li
                key={`${item.file.name}-${item.file.size}`}
                className={styles.fileItem}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
              >
                <span className={styles.fileName}>{item.file.name}</span>
                <span
                  className={`${styles.fileState} ${
                    item.state === "uploaded" ? styles.stateOk : item.state === "failed" ? styles.stateError : ""
                  }`}
                >
                  {item.state === "waiting" && !sessionId ? (
                    <ShiningText text="waiting for JD" className="text-xs" />
                  ) : item.state === "waiting" ? (
                    "queued"
                  ) : item.state === "uploading" ? (
                    <ShiningText text="uploading…" className="text-xs" />
                  ) : item.state === "uploaded" ? (
                    "uploaded"
                  ) : (
                    "failed"
                  )}
                </span>
              </motion.li>
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
          </motion.ul>
        )}

        <div className="px-5 pb-4 space-y-1">
          {errorMessage && (
            <p role="alert" className="fieldError text-sm">
              {errorMessage}
            </p>
          )}
          <p className="text-xs text-text-secondary">
            Resumes are sent automatically after a job description is provided.
          </p>
          {!sessionId && (
            <p className="hintText text-xs">
              Upload a job description first — resumes are sent automatically.
            </p>
          )}
        </div>
      </GridPatternCardBody>
    </GridPatternCard>
  );
}
