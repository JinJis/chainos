'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useRef, useState } from 'react';
import { api, runAgent, type AgentEvent, type ParsePreview, type Ticket } from '../../../lib/api';
import { VerifyPanel } from '../../../components/VerifyPanel';
import { FlowsEditor } from '../../../components/FlowsEditor';

const KIND_COLOR: Record<string, string> = {
  start: 'var(--dim)',
  research: 'var(--accent)',
  deep: '#b69bff',
  persist: 'var(--ok)',
  gaps: 'var(--gold)',
  done: 'var(--ok)',
  error: 'var(--danger)',
  job: 'var(--dim)',
};

export default function ThemeConsole({ params }: { params: { id: string } }) {
  const themeId = params.id;
  const qc = useQueryClient();
  const { data: theme } = useQuery({
    queryKey: ['theme', themeId],
    queryFn: () => api.getTheme(themeId),
    refetchInterval: 4000,
  });
  const { data: tickets } = useQuery({
    queryKey: ['tickets', themeId],
    queryFn: () => api.listTickets(themeId),
    refetchInterval: 4000,
  });

  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [running, setRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  async function onRun() {
    setEvents([]);
    setRunning(true);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      await runAgent(
        themeId,
        (ev) => setEvents((prev) => [...prev, ev]),
        ctrl.signal,
      );
    } catch (e) {
      setEvents((prev) => [...prev, { kind: 'error', message: String(e) }]);
    } finally {
      setRunning(false);
      qc.invalidateQueries({ queryKey: ['theme', themeId] });
      qc.invalidateQueries({ queryKey: ['tickets', themeId] });
    }
  }

  return (
    <div className="grid" style={{ gap: 20 }}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <div>
          <Link href="/" className="dim">
            ← Themes
          </Link>
          <h1 style={{ margin: '6px 0' }}>{theme?.name ?? '…'}</h1>
          <div className="dim" style={{ fontSize: 13 }}>
            status <b>{theme?.status}</b> · depth {theme?.depth_max} · staging{' '}
            {theme?.staging_counts.nodes ?? 0} nodes / {theme?.staging_counts.edges ?? 0} flows ·
            production {theme?.production_counts.nodes ?? 0} nodes
          </div>
        </div>
        <div className="row">
          <button className="primary" onClick={onRun} disabled={running}>
            {running ? '⏳ Running…' : '▶ Run Agent'}
          </button>
          {running && (
            <button onClick={() => abortRef.current?.abort()}>Stop</button>
          )}
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1.2fr 1fr', alignItems: 'start' }}>
        <section className="panel">
          <h3 style={{ marginTop: 0 }}>Agent console</h3>
          <div
            className="mono"
            style={{
              background: '#04060c',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: 12,
              height: 360,
              overflow: 'auto',
              fontSize: 12.5,
            }}
          >
            {events.length === 0 && (
              <div className="dim">
                Press “Run Agent” to discover constituents, draft the value-chain skeleton, save
                it to Staging, and raise Need-Fact tickets.
              </div>
            )}
            {events.map((ev, i) => (
              <div key={i} style={{ marginBottom: 4 }}>
                <span style={{ color: KIND_COLOR[ev.kind] ?? 'var(--text)' }}>
                  [{ev.kind}]
                </span>{' '}
                {ev.message}
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <h3 style={{ marginTop: 0 }}>
            Need-Fact inbox{' '}
            <span className="dim" style={{ fontSize: 13 }}>
              ({tickets?.filter((t) => t.status === 'open').length ?? 0} open)
            </span>
          </h3>
          <div className="grid" style={{ gap: 10 }}>
            {tickets?.length === 0 && <p className="dim">No tickets yet.</p>}
            {tickets?.map((t) => <TicketCard key={t.id} ticket={t} themeId={themeId} />)}
          </div>
        </section>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', alignItems: 'start' }}>
        <VerifyPanel themeId={themeId} />
        <FlowsEditor themeId={themeId} />
      </div>
    </div>
  );
}

function TicketCard({ ticket, themeId }: { ticket: Ticket; themeId: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<ParsePreview | null>(null);
  const attach = useMutation({
    mutationFn: (form: FormData) => api.attachSource(ticket.id, form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tickets', themeId] });
      setOpen(false);
    },
  });
  const parse = useMutation({
    mutationFn: () => api.parseTicket(ticket.id),
    onSuccess: (p) => setPreview(p),
  });
  const approve = useMutation({
    mutationFn: () => api.approveTicket(ticket.id, preview?.value ?? undefined),
    onSuccess: () => {
      setPreview(null);
      qc.invalidateQueries({ queryKey: ['tickets', themeId] });
      qc.invalidateQueries({ queryKey: ['staging', themeId, 'supply'] });
    },
  });

  return (
    <div
      style={{
        border: '1px solid var(--border)',
        borderRadius: 8,
        padding: 10,
        opacity: ticket.status === 'resolved' ? 0.5 : 1,
      }}
    >
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <b className="mono" style={{ fontSize: 12 }}>
          ⚠ {ticket.metric}
        </b>
        <span className="badge" style={{ borderColor: 'var(--gold)', color: 'var(--gold)' }}>
          P{ticket.priority}
        </span>
      </div>
      <div className="dim" style={{ fontSize: 12, margin: '4px 0' }}>
        {ticket.target_ref} — {ticket.reason}
      </div>
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <span className="dim" style={{ fontSize: 12 }}>
          {ticket.source_count} source(s)
          {ticket.locked_value != null && (
            <span style={{ color: 'var(--ok)' }}> · locked {ticket.locked_value}</span>
          )}
        </span>
        {ticket.status === 'open' && (
          <button onClick={() => setOpen((o) => !o)} style={{ padding: '4px 10px', fontSize: 12 }}>
            {open ? 'Cancel' : '+ Attach evidence'}
          </button>
        )}
        {ticket.status === 'open' && ticket.source_count > 0 && (
          <button
            onClick={() => parse.mutate()}
            disabled={parse.isPending}
            style={{ padding: '4px 10px', fontSize: 12 }}
          >
            {parse.isPending ? 'Parsing…' : '🔍 Parse (MEDIUM)'}
          </button>
        )}
      </div>
      {preview && (
        <div
          style={{
            marginTop: 8,
            padding: 8,
            borderRadius: 6,
            border: '1px solid var(--border)',
            background: '#04060c',
            fontSize: 12,
          }}
        >
          <div className="mono">
            extracted <b style={{ color: 'var(--ok)' }}>{String(preview.value)}</b> for{' '}
            {preview.field} — span “{preview.span}”
          </div>
          <div className="dim">by {preview.extracted_by}</div>
          <button
            className="primary"
            onClick={() => approve.mutate()}
            disabled={approve.isPending || !preview.found}
            style={{ marginTop: 6, padding: '4px 12px', fontSize: 12 }}
          >
            {approve.isPending ? 'Locking…' : '✓ Approve & lock to source'}
          </button>
        </div>
      )}
      {open && (
        <form
          style={{ marginTop: 8 }}
          className="grid"
          onSubmit={(e) => {
            e.preventDefault();
            attach.mutate(new FormData(e.currentTarget));
          }}
        >
          <select name="type" defaultValue="filing">
            <option value="filing">filing</option>
            <option value="IR">IR</option>
            <option value="report">report</option>
            <option value="news">news</option>
          </select>
          <input name="publisher" placeholder="Publisher (e.g. TSMC 10-Q)" />
          <input name="as_of_date" placeholder="As-of (e.g. 26 Q1 filing)" defaultValue="26 Q1 filing" />
          <textarea name="content_text" placeholder="Paste the relevant disclosure text / number…" rows={3} />
          <input type="file" name="file" />
          <button className="primary" type="submit" disabled={attach.isPending}>
            {attach.isPending ? 'Uploading…' : 'Submit to ticket'}
          </button>
        </form>
      )}
    </div>
  );
}
