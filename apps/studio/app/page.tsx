'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useState } from 'react';
import { api, type Theme } from '../lib/api';

const TIERS = ['RESEARCH', 'DEEP', 'MEDIUM', 'LOW'] as const;

function StatusBadge({ status }: { status: string }) {
  const color =
    status === 'published'
      ? 'var(--ok)'
      : status === 'staged'
        ? 'var(--gold)'
        : status === 'building'
          ? 'var(--accent)'
          : 'var(--dim)';
  return (
    <span className="badge" style={{ borderColor: color, color }}>
      {status}
    </span>
  );
}

export default function Dashboard() {
  const qc = useQueryClient();
  const { data: themes, isLoading } = useQuery({ queryKey: ['themes'], queryFn: api.listThemes });

  const [name, setName] = useState('AI Data Centers');
  const [depth, setDepth] = useState(3);
  const [assignment, setAssignment] = useState<Record<string, string>>({
    RESEARCH: 'google',
    DEEP: 'google',
    MEDIUM: 'google',
    LOW: 'google',
  });

  const create = useMutation({
    mutationFn: () =>
      api.createTheme({ name, depth_max: depth, model_assignment: assignment, seed_tickers: [] }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['themes'] }),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteTheme(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['themes'] }),
  });

  return (
    <div className="grid" style={{ gap: 24 }}>
      <section className="panel">
        <h2 style={{ marginTop: 0 }}>New Theme</h2>
        <div className="grid" style={{ gridTemplateColumns: '2fr 1fr', alignItems: 'end' }}>
          <label>
            <div className="dim">Industry / theme</div>
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label>
            <div className="dim">Depth (1–N)</div>
            <input
              type="number"
              min={1}
              max={6}
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
            />
          </label>
        </div>

        <div style={{ marginTop: 14 }}>
          <div className="dim" style={{ marginBottom: 6 }}>
            Model assignment (per tier)
          </div>
          <div className="row" style={{ flexWrap: 'wrap' }}>
            {TIERS.map((tier) => (
              <label key={tier} style={{ width: 160 }}>
                <div className="mono" style={{ fontSize: 12 }}>
                  {tier}
                </div>
                <select
                  value={assignment[tier]}
                  onChange={(e) => setAssignment((a) => ({ ...a, [tier]: e.target.value }))}
                >
                  <option value="anthropic">Anthropic</option>
                  <option value="google">Google</option>
                </select>
              </label>
            ))}
          </div>
        </div>

        <div style={{ marginTop: 16 }}>
          <button
            className="primary"
            onClick={() => create.mutate()}
            disabled={create.isPending || !name.trim()}
          >
            {create.isPending ? 'Creating…' : '+ Create Theme'}
          </button>
        </div>
      </section>

      <section>
        <h2>Themes</h2>
        {isLoading && <p className="dim">Loading…</p>}
        <div className="grid">
          {themes?.map((t: Theme) => (
            <div
              key={t.id}
              className="panel row"
              style={{ justifyContent: 'space-between' }}
            >
              <div>
                <div className="row">
                  <Link href={`/themes/${t.id}`} style={{ fontSize: 16, fontWeight: 600 }}>
                    {t.name}
                  </Link>
                  <StatusBadge status={t.status} />
                </div>
                <div className="dim" style={{ fontSize: 12, marginTop: 4 }}>
                  depth {t.depth_max} · staging {t.staging_counts.nodes ?? 0} nodes /{' '}
                  {t.staging_counts.edges ?? 0} flows · production{' '}
                  {t.production_counts.nodes ?? 0} nodes · {t.open_tickets} open tickets
                </div>
              </div>
              <button className="danger" onClick={() => remove.mutate(t.id)}>
                Delete
              </button>
            </div>
          ))}
          {themes?.length === 0 && <p className="dim">No themes yet — create one above.</p>}
        </div>
      </section>
    </div>
  );
}
