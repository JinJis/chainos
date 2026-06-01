'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, PublishError, type ValidationReport } from '../lib/api';

/** Publish console: diff preview + gated deploy to Production (explicit action). */
export function PublishPanel({ themeId }: { themeId: string }) {
  const qc = useQueryClient();
  const { data: diff } = useQuery({
    queryKey: ['diff', themeId],
    queryFn: () => api.publishDiff(themeId),
    refetchInterval: 5000,
  });

  const publish = useMutation({
    mutationFn: () => api.publish(themeId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['theme', themeId] });
      qc.invalidateQueries({ queryKey: ['diff', themeId] });
    },
  });

  const blocked =
    publish.error instanceof PublishError
      ? (publish.error.detail as ValidationReport)
      : null;

  return (
    <section className="panel">
      <h3 style={{ marginTop: 0 }}>🚀 Publish console</h3>
      <p className="dim" style={{ fontSize: 12 }}>
        Staging → Production is a deliberate, gated sync. The Terminal reads Production only.
      </p>
      {diff && (
        <div className="mono" style={{ fontSize: 12.5, marginBottom: 10 }}>
          <div>
            staging {diff.staging_counts.nodes} nodes / {diff.staging_counts.edges} flows
          </div>
          <div className="dim">
            production {diff.production_counts.nodes} nodes / {diff.production_counts.edges} flows
          </div>
          <div style={{ color: 'var(--ok)' }}>
            +{diff.added_nodes.length} nodes, +{diff.added_edges} flows
          </div>
          {diff.removed_nodes.length + diff.removed_edges > 0 && (
            <div style={{ color: 'var(--danger)' }}>
              −{diff.removed_nodes.length} nodes, −{diff.removed_edges} flows
            </div>
          )}
        </div>
      )}

      <button
        className="primary"
        onClick={() => publish.mutate()}
        disabled={publish.isPending}
      >
        {publish.isPending ? 'Publishing…' : '🚀 Validate & Publish to Production'}
      </button>

      {publish.isSuccess && (
        <div className="badge" style={{ marginLeft: 10, borderColor: 'var(--ok)', color: 'var(--ok)' }}>
          ✓ Published v{publish.data.version} — {publish.data.production_counts.nodes} nodes live
        </div>
      )}

      {blocked && (
        <div style={{ marginTop: 10 }}>
          <div className="badge" style={{ borderColor: 'var(--danger)', color: 'var(--danger)' }}>
            ✗ BLOCKED by validation gate — {blocked.failed} unmet
          </div>
          <ul className="mono" style={{ fontSize: 12, marginTop: 8 }}>
            {blocked.failures.slice(0, 8).map((f, i) => (
              <li key={i} style={{ color: 'var(--danger)' }}>
                {f.ref} — missing {f.missing.join(', ')}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
