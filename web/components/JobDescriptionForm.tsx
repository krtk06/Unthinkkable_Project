"use client";

import { useId, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { NormalizedRequirements } from "@/lib/types";
import styles from "./SessionSetup.module.css";

interface JobDescriptionFormProps {
  sessionId: string | null;
  onSessionCreated: (sessionId: string) => void;
}

export default function JobDescriptionForm({ sessionId, onSessionCreated }: JobDescriptionFormProps) {
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [normalized, setNormalized] = useState<NormalizedRequirements | null>(null);
  const [busy, setBusy] = useState(false);
  const textareaId = useId();

  async function handleSubmit() {
    if (text.trim().length === 0) {
      setError("Enter a job description first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let currentSessionId = sessionId;
      if (!currentSessionId) {
        const created = await api.createSession();
        currentSessionId = created.session_id;
        onSessionCreated(currentSessionId);
      }
      const result = await api.saveJobDescription(currentSessionId, text.trim());
      setNormalized(result.normalized_requirements);
    } catch (err) {
      setError(err instanceof ApiError ? `${err.code}: ${err.message}` : "Could not save the job description. Check that the API is running.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={styles.card} aria-labelledby="jd-form-title">
      <h2 className={styles.cardTitle} id="jd-form-title">
        Job description
      </h2>
      <div>
        <label className={styles.label} htmlFor={textareaId}>
          Paste the job description
        </label>
        <textarea
          id={textareaId}
          className={styles.textarea}
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            if (error) setError(null);
          }}
          placeholder="Include must-have and nice-to-have requirements…"
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${textareaId}-error` : undefined}
        />
        {error && (
          <p className={styles.fieldError} id={`${textareaId}-error`} role="alert">
            {error}
          </p>
        )}
      </div>
      <button className={styles.primaryButton} onClick={handleSubmit} disabled={busy} type="button">
        {busy ? "Normalizing…" : sessionId ? "Replace job description" : "Start session"}
      </button>
      {normalized && (
        <dl className={styles.normalized}>
          {normalized.title && <dt className={styles.normalizedTitle}>{normalized.title}</dt>}
          <dd>
            Required: {normalized.required.map((r) => r.name).join(", ") || "none stated"} ·
            Preferred: {normalized.preferred.map((r) => r.name).join(", ") || "none stated"}
          </dd>
          {normalized.ambiguities.length > 0 && (
            <dd className={styles.ambiguity}>
              Ambiguous items were treated as preferred — review before scoring.
              <ul>
                {normalized.ambiguities.map((ambiguity) => (
                  <li key={ambiguity}>{ambiguity}</li>
                ))}
              </ul>
            </dd>
          )}
        </dl>
      )}
    </section>
  );
}
