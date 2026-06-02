'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type GraphEdge } from '../lib/api';

const CONF = ['verified', 'derived', 'estimated'];
const CONF_COLOR: Record<string, string> = {
  verified: 'var(--ok)',
  derived: 'var(--gold)',
  estimated: '#ff9d4d',
};

/** Lightweight graph editor: tune the confidence on staged supply flows. */
export function FlowsEditor({ themeId }: { themeId: string }) {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ['staging', themeId, 'supply'],
    queryFn: () => api.stagingGraph(themeId, ['supply']),
  });

  const edit = useMutation({
    mutationFn: ({ edge, updates }: { edge: GraphEdge; updates: Record<string, unknown> }) =>
      api.editEdge(themeId, edge, updates),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['staging', themeId, 'supply'] }),
  });

  const edges = (data?.edges ?? []).filter((e) => e.type === 'SUPPLIES');

  return (
    <section className="panel">
      <h3 style={{ marginTop: 0 }}>
        Staged supply flows{' '}
        <span className="dim" style={{ fontSize: 13 }}>
          ({edges.length})
        </span>
      </h3>
      <div style={{ maxHeight: 320, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
          <thead>
            <tr className="dim" style={{ textAlign: 'left' }}>
              <th style={{ padding: '4px 6px' }}>flow</th>
              <th>product</th>
              <th>alloc%</th>
              <th>confidence</th>
            </tr>
          </thead>
          <tbody>
            {edges.map((e, i) => (
              <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                <td className="mono" style={{ padding: '4px 6px' }}>
                  {e.from} → {e.to}
                </td>
                <td className="dim">{e.product_ref ?? '—'}</td>
                <td>{typeof e.allocation_pct === 'number' ? e.allocation_pct : '—'}</td>
                <td>
                  <select
                    value={e.confidence ?? 'derived'}
                    onChange={(ev) =>
                      edit.mutate({ edge: e, updates: { confidence: ev.target.value } })
                    }
                    style={{
                      width: 120,
                      color: CONF_COLOR[e.confidence ?? 'derived'],
                      padding: '3px 6px',
                    }}
                  >
                    {CONF.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
