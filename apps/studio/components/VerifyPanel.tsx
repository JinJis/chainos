'use client';

import { useMutation } from '@tanstack/react-query';
import { api, type ValidationReport } from '../lib/api';

/** Publish-readiness: runs the validation gate and shows unmet items. */
export function VerifyPanel({ themeId }: { themeId: string }) {
  const validate = useMutation<ValidationReport>({ mutationFn: () => api.validate(themeId) });
  const report = validate.data;

  return (
    <section className="panel">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h3 style={{ margin: 0 }}>Publish readiness</h3>
        <button onClick={() => validate.mutate()} disabled={validate.isPending}>
          {validate.isPending ? 'Validating…' : 'Run validation gate'}
        </button>
      </div>
      <p className="dim" style={{ fontSize: 12 }}>
        Every exposed figure must carry source_id + base_date + next_update.
      </p>
      {report && (
        <div>
          <div
            className="badge"
            style={{
              borderColor: report.ok ? 'var(--ok)' : 'var(--danger)',
              color: report.ok ? 'var(--ok)' : 'var(--danger)',
            }}
          >
            {report.ok ? '✓ PASS' : '✗ BLOCKED'} — {report.passed}/{report.total} figures verified
          </div>
          {report.failures.length > 0 && (
            <ul style={{ marginTop: 10, fontSize: 12 }} className="mono">
              {report.failures.slice(0, 12).map((f, i) => (
                <li key={i} style={{ color: 'var(--danger)', marginBottom: 3 }}>
                  {f.ref} — missing {f.missing.join(', ')}
                </li>
              ))}
              {report.failures.length > 12 && (
                <li className="dim">+{report.failures.length - 12} more…</li>
              )}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
