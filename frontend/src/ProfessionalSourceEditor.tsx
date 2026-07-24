import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import type { ProfessionalIntelligenceSource } from "./ProfessionalIntelligence";

type SourceUpdate = Pick<
  ProfessionalIntelligenceSource,
  "label" | "url" | "initial_scope" | "enabled"
>;

type Props = {
  source: ProfessionalIntelligenceSource;
  busy: boolean;
  onSave: (sourceId: string, update: SourceUpdate) => Promise<void>;
  onReset: (sourceId: string) => Promise<void>;
};

export function ProfessionalSourceEditor({ source, busy, onSave, onReset }: Props) {
  const [label, setLabel] = useState(source.label);
  const [url, setUrl] = useState(source.url);
  const [initialScope, setInitialScope] = useState(source.initial_scope);
  const [enabled, setEnabled] = useState(source.enabled);

  useEffect(() => {
    setLabel(source.label);
    setUrl(source.url);
    setInitialScope(source.initial_scope);
    setEnabled(source.enabled);
  }, [source]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSave(source.source_id, {
      label: label.trim(),
      url: url.trim(),
      initial_scope: initialScope,
      enabled,
    });
  }

  return (
    <details className="professional-source-editor">
      <summary>Edit approved source</summary>
      <form onSubmit={submit}>
        <label>
          Source label
          <input
            aria-label={`Source label for ${source.source_id}`}
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            required
            maxLength={120}
          />
        </label>
        <label>
          LinkedIn URL
          <input
            aria-label={`LinkedIn URL for ${source.source_id}`}
            type="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            required
          />
        </label>
        <label className="professional-source-checkbox">
          <input
            aria-label={`Initial scope for ${source.source_id}`}
            type="checkbox"
            checked={initialScope}
            onChange={(event) => setInitialScope(event.target.checked)}
          />
          Include in initial supervised scope
        </label>
        <label className="professional-source-checkbox">
          <input
            aria-label={`Enabled for ${source.source_id}`}
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          Enabled for future supervised capture
        </label>
        <div className="professional-source-editor-actions">
          <button type="submit" disabled={busy || !label.trim() || !url.trim()}>
            {busy ? "Saving…" : "Save source"}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => void onReset(source.source_id)}
          >
            Reset verified default
          </button>
        </div>
      </form>
    </details>
  );
}
