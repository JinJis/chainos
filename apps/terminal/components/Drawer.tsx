'use client';

import { confidenceStyle, type Confidence } from '@chainos/ui';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { useT } from '../lib/i18n';
import { useCanvas } from '../lib/store';

function fmtUSD(v?: number): string {
  if (!v) return '—';
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${v}`;
}

function ConfidenceDot({ c }: { c?: string }) {
  const style = confidenceStyle[(c ?? 'derived') as Confidence] ?? confidenceStyle.derived;
  return (
    <span title={style.label} style={{ color: style.color, fontSize: 11 }}>
      {style.icon} {style.label}
    </span>
  );
}

/** Deterministic price sparkline (delayed feed placeholder). */
function Sparkline({ seed }: { seed: string }) {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  const pts: number[] = [];
  let v = 50;
  for (let i = 0; i < 32; i++) {
    h = (h * 1103515245 + 12345) & 0x7fffffff;
    v += ((h % 100) / 100 - 0.48) * 8;
    v = Math.max(8, Math.min(92, v));
    pts.push(v);
  }
  const up = pts[pts.length - 1]! >= pts[0]!;
  const d = pts
    .map((p, i) => `${(i / 31) * 140},${36 - (p / 100) * 36}`)
    .join(' ');
  return (
    <svg width={140} height={36} style={{ display: 'block' }}>
      <polyline
        points={d}
        fill="none"
        stroke={up ? 'var(--ok)' : 'var(--danger)'}
        strokeWidth={1.5}
      />
    </svg>
  );
}

export function Drawer() {
  const t = useT();
  const themeId = useCanvas((s) => s.themeId);
  const selectedId = useCanvas((s) => s.selectedId);
  const select = useCanvas((s) => s.select);
  const laser = useCanvas((s) => s.laser);
  const setLaser = useCanvas((s) => s.setLaser);

  const { data: detail } = useQuery({
    queryKey: ['detail', themeId, selectedId],
    queryFn: () => api.companyDetail(themeId!, selectedId!),
    enabled: !!themeId && !!selectedId,
  });

  if (!selectedId) return null;
  const c = detail?.company;

  return (
    <div
      className="hud glass"
      style={{
        top: 0,
        right: 0,
        height: '100vh',
        width: 380,
        borderRadius: 0,
        borderLeft: '1px solid var(--border)',
        padding: 20,
        overflowY: 'auto',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{c?.name ?? selectedId}</div>
          <div className="dim mono" style={{ fontSize: 12 }}>
            {c?.ticker} · {c?.exchange} · {c?.country} · tier {c?.tier}
          </div>
        </div>
        <button
          className="toggle"
          onClick={() => select(null)}
          style={{ padding: '2px 9px' }}
        >
          ✕
        </button>
      </div>

      {/* Trust badge */}
      <div
        className="glass"
        style={{ padding: '8px 10px', marginTop: 12, fontSize: 12, borderRadius: 8 }}
      >
        📊 {t('baseDate')}: <b>{c?.base_date ?? '—'}</b>
        <br />
        <span className="dim">
          {t('nextUpdate')}: {c?.next_update ?? '—'}
        </span>
      </div>

      {/* Price + market cap */}
      <div className="row" style={{ marginTop: 14, justifyContent: 'space-between' }}>
        <div>
          <div className="dim" style={{ fontSize: 11 }}>
            {t('priceDelayed')}
          </div>
          {c && <Sparkline seed={c.ticker} />}
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="dim" style={{ fontSize: 11 }}>
            {t('marketCap')}
          </div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>{fmtUSD(c?.market_cap)}</div>
        </div>
      </div>

      {/* Divisions → products */}
      <h4 style={{ marginBottom: 6, marginTop: 18 }}>{t('divisions')}</h4>
      {detail?.divisions.map((d) => (
        <div
          key={d.division.id}
          style={{ borderLeft: '2px solid var(--border)', paddingLeft: 10, marginBottom: 10 }}
        >
          <div style={{ fontWeight: 600 }}>
            {d.division.name}{' '}
            {d.division.revenue_share != null && (
              <span className="dim" style={{ fontSize: 12 }}>
                · {d.division.revenue_share}% rev
              </span>
            )}
          </div>
          {d.products.map((p) => {
            const customers = (detail?.customers ?? []).filter(
              (cust) => cust.edge.product_ref === p.name,
            );
            const active = laser?.product === p.name;
            return (
              <div
                key={p.id}
                style={{
                  marginTop: 6,
                  padding: 8,
                  borderRadius: 8,
                  border: `1px solid ${active ? 'var(--neon)' : 'var(--border)'}`,
                  background: active ? 'rgba(70,240,200,0.08)' : 'transparent',
                }}
              >
                <div className="row" style={{ justifyContent: 'space-between' }}>
                  <b>{p.name}</b>
                  <button
                    className="toggle"
                    style={{ padding: '2px 8px', fontSize: 11 }}
                    onClick={() =>
                      setLaser(
                        active
                          ? null
                          : { product: p.name, customers: customers.map((x) => x.id) },
                      )
                    }
                  >
                    {t('showFlow')}
                  </button>
                </div>
                <div className="dim" style={{ fontSize: 12 }}>
                  {p.category} · {t('revenue')} {fmtUSD(p.revenue)}
                  {p.margin != null && ` · ${t('margin')} ${p.margin}%`}
                </div>
                {customers.length > 0 && (
                  <div style={{ fontSize: 12, marginTop: 4 }}>
                    <span className="dim">{t('keyCustomers')}: </span>
                    {customers.map((cust, i) => (
                      <span key={cust.id}>
                        {i > 0 && ', '}
                        {cust.name}{' '}
                        <span className="dim">({cust.edge.allocation_pct}%)</span>{' '}
                        <ConfidenceDot c={cust.edge.confidence} />
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ))}

      {/* Customers (company-level) */}
      {detail && detail.customers.length > 0 && (
        <>
          <h4 style={{ marginBottom: 6, marginTop: 14 }}>{t('keyCustomers')}</h4>
          {detail.customers.map((cust) => (
            <div
              key={cust.id}
              className="row"
              style={{ justifyContent: 'space-between', fontSize: 13, padding: '3px 0' }}
            >
              <span>{cust.name}</span>
              <span className="dim">
                {cust.edge.product_ref} · {cust.edge.allocation_pct}%
              </span>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
