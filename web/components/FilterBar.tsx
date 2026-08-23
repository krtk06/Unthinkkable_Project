"use client";

import { useId } from "react";
import styles from "./FilterBar.module.css";

export interface FilterState {
  mode: "threshold" | "top_n";
  threshold: number;
  topN: number;
  minRequiredCoverage: number;
  minExperienceMonths: number | null;
  workMode: string;
  location: string;
  requiredSkillsComplete: "any" | "true" | "false";
}

export const DEFAULT_FILTERS: FilterState = {
  mode: "threshold",
  threshold: 7,
  topN: 10,
  minRequiredCoverage: 0,
  minExperienceMonths: null,
  workMode: "",
  location: "",
  requiredSkillsComplete: "any",
};

interface FilterBarProps {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
  onApply: () => void;
  busy?: boolean;
}

export default function FilterBar({ filters, onChange, onApply, busy = false }: FilterBarProps) {
  const ids = {
    coverage: useId(),
    experience: useId(),
    workMode: useId(),
    location: useId(),
    skillsComplete: useId(),
  };

  function update(patch: Partial<FilterState>) {
    onChange({ ...filters, ...patch });
  }

  return (
    <form
      className={styles.controls}
      onSubmit={(event) => {
        event.preventDefault();
        onApply();
      }}
      aria-label="Match filters"
    >
      <div className={styles.modeToggle} role="group" aria-label="Ranking mode">
        <button type="button" aria-pressed={filters.mode === "threshold"} onClick={() => update({ mode: "threshold" })}>
          Threshold
        </button>
        <button type="button" aria-pressed={filters.mode === "top_n"} onClick={() => update({ mode: "top_n" })}>
          Top N
        </button>
      </div>
      {filters.mode === "threshold" ? (
        <div className={styles.control}>
          <label htmlFor="threshold-input">Minimum score</label>
          <input
            id="threshold-input"
            type="number"
            min={1}
            max={10}
            value={filters.threshold}
            onChange={(event) => update({ threshold: Number(event.target.value) })}
          />
        </div>
      ) : (
        <div className={styles.control}>
          <label htmlFor="topn-input">Top N</label>
          <input
            id="topn-input"
            type="number"
            min={1}
            value={filters.topN}
            onChange={(event) => update({ topN: Number(event.target.value) })}
          />
        </div>
      )}
      <div className={styles.control}>
        <label htmlFor={ids.coverage}>Min required coverage</label>
        <select
          id={ids.coverage}
          value={filters.minRequiredCoverage}
          onChange={(event) => update({ minRequiredCoverage: Number(event.target.value) })}
        >
          <option value={0}>Any</option>
          <option value={0.5}>50%</option>
          <option value={0.75}>75%</option>
          <option value={1}>100%</option>
        </select>
      </div>
      <div className={styles.control}>
        <label htmlFor={ids.experience}>Min experience (months)</label>
        <input
          id={ids.experience}
          type="number"
          min={0}
          value={filters.minExperienceMonths ?? ""}
          placeholder="Any"
          onChange={(event) =>
            update({ minExperienceMonths: event.target.value === "" ? null : Number(event.target.value) })
          }
        />
      </div>
      <div className={styles.control}>
        <label htmlFor={ids.workMode}>Work mode</label>
        <input
          id={ids.workMode}
          type="text"
          value={filters.workMode}
          placeholder="e.g. remote"
          onChange={(event) => update({ workMode: event.target.value })}
        />
      </div>
      <div className={styles.control}>
        <label htmlFor={ids.location}>Location</label>
        <input
          id={ids.location}
          type="text"
          value={filters.location}
          placeholder="e.g. Berlin"
          onChange={(event) => update({ location: event.target.value })}
        />
      </div>
      <div className={styles.control}>
        <label htmlFor={ids.skillsComplete}>Required skills complete</label>
        <select
          id={ids.skillsComplete}
          value={filters.requiredSkillsComplete}
          onChange={(event) =>
            update({ requiredSkillsComplete: event.target.value as FilterState["requiredSkillsComplete"] })
          }
        >
          <option value="any">Any</option>
          <option value="true">Complete</option>
          <option value="false">Incomplete</option>
        </select>
      </div>
      <button className="primaryButton" type="submit" disabled={busy}>
        Apply filters
      </button>
    </form>
  );
}
