'use client';

import { SparkIcon } from './Icons';

export default function Suggestions({
  suggestions,
  disabled,
  onPick,
}: {
  suggestions: string[];
  disabled: boolean;
  onPick: (text: string) => void;
}) {
  if (!suggestions.length) return null;
  return (
    <details className="suggest" open>
      <summary>
        <span className="caret">▸</span>
        <span className="suggest-cap">Suggested</span>
        <span className="cnt">{suggestions.length}</span>
      </summary>
      <div className="suggest-list">
        {suggestions.map((s, i) => (
          <button className="pill" key={i} disabled={disabled} onClick={() => onPick(s)}>
            <span className="pico">
              <SparkIcon size={13} />
            </span>
            {s}
          </button>
        ))}
      </div>
    </details>
  );
}
