'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';

/**
 * Research document panel — the entry point of the (simplified) build flow:
 *  1) Copy the generated research brief → run it in the Gemini Deep Research UI.
 *  2) Paste / upload the result here and Save.
 *  3) Run Agent → the DEEP model structures THIS document into the graph + tickets.
 */
export function ResearchPanel({ themeId }: { themeId: string }) {
  const qc = useQueryClient();
  const { data: brief } = useQuery({
    queryKey: ['brief', themeId],
    queryFn: () => api.researchBrief(themeId),
  });
  const { data: research } = useQuery({
    queryKey: ['research', themeId],
    queryFn: () => api.getResearch(themeId),
  });

  const [report, setReport] = useState('');
  const [showBrief, setShowBrief] = useState(false);
  const [copied, setCopied] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (research) setReport(research.report);
  }, [research]);

  const save = useMutation({
    mutationFn: () => api.saveResearch(themeId, report),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['research', themeId] });
      qc.invalidateQueries({ queryKey: ['theme', themeId] });
    },
  });

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) setReport(await file.text());
  }

  function copyBrief() {
    if (brief?.brief) {
      navigator.clipboard?.writeText(brief.brief);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }

  const saved = research?.chars ?? 0;
  const dirty = report !== (research?.report ?? '');

  return (
    <section className="panel">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline' }}>
        <h3 style={{ marginTop: 0 }}>
          ① Research document{' '}
          {saved > 0 && (
            <span className="badge" style={{ borderColor: 'var(--ok)', color: 'var(--ok)' }}>
              {saved.toLocaleString()} chars saved
            </span>
          )}
        </h3>
        <button className="toggle" onClick={() => setShowBrief((v) => !v)}>
          {showBrief ? 'Hide' : 'Show'} research brief
        </button>
      </div>
      <p className="dim" style={{ fontSize: 12, marginTop: 0 }}>
        Run the brief in the Gemini Deep Research UI, then paste/upload the result here and
        Save. Run Agent structures <i>this</i> document into the graph (DEEP) and raises
        Need-Fact tickets for the gaps.
      </p>

      {showBrief && (
        <div style={{ marginBottom: 12 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="dim" style={{ fontSize: 12 }}>
              Copy this into Gemini Deep Research →
            </span>
            <button onClick={copyBrief} style={{ padding: '3px 10px', fontSize: 12 }}>
              {copied ? '✓ Copied' : 'Copy prompt'}
            </button>
          </div>
          <textarea
            readOnly
            value={brief?.brief ?? ''}
            rows={8}
            className="mono"
            style={{ marginTop: 6, fontSize: 11.5, background: '#04060c' }}
          />
        </div>
      )}

      <textarea
        value={report}
        onChange={(e) => setReport(e.target.value)}
        rows={10}
        placeholder="Paste the Gemini Deep Research output here (or upload a .txt/.md file)…"
        className="mono"
        style={{ fontSize: 12 }}
      />
      <div className="row" style={{ marginTop: 10, gap: 10 }}>
        <button onClick={() => fileRef.current?.click()}>📎 Upload .txt / .md</button>
        <input
          ref={fileRef}
          type="file"
          accept=".txt,.md,.markdown,text/plain"
          onChange={onFile}
          style={{ display: 'none' }}
        />
        <button
          className="primary"
          onClick={() => save.mutate()}
          disabled={save.isPending || !dirty}
        >
          {save.isPending ? 'Saving…' : dirty ? '💾 Save document' : 'Saved'}
        </button>
        <span className="dim" style={{ fontSize: 12 }}>
          {report.length.toLocaleString()} chars
        </span>
      </div>
    </section>
  );
}
