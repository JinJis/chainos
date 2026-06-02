'use client';

import { FLOW_VIEWS } from '@chainos/graph-schema';
import { useCanvas, type FlowView } from '../lib/store';
import { useT, type StringKey } from '../lib/i18n';
import type { ThemeRef } from '../lib/api';

const VIEW_KEY: Record<FlowView, StringKey> = {
  supply: 'supplyChain',
  revenue: 'revenueFlow',
  investment: 'investment',
  cost: 'cost',
  rnd: 'rnd',
};

export function Hud({
  theme,
  themes,
  nodeCount,
  visibleCount,
}: {
  theme: ThemeRef | null;
  themes: ThemeRef[];
  nodeCount: number;
  visibleCount: number;
}) {
  const { depth, setDepth, views, toggleView, predict, togglePredict, setThemeId, lang, setLang } =
    useCanvas();
  const t = useT();
  const depthMax = theme?.depth_max ?? 3;

  return (
    <>
      {/* Top-left: theme + counts */}
      <div className="hud" style={{ top: 16, left: 16 }}>
        <div className="glass" style={{ padding: '12px 16px' }}>
          <div style={{ fontSize: 18, fontWeight: 700 }}>
            ⛓ {theme?.name ?? 'Chainos'}{' '}
            {theme && <span className="dim" style={{ fontSize: 12 }}>v{theme.version}</span>}
          </div>
          <div className="dim" style={{ fontSize: 12, marginTop: 2 }}>
            {visibleCount}/{nodeCount} {t('companies')} · {t('depth')} {depth}
          </div>
          {themes.length > 1 && (
            <select
              value={theme?.id}
              onChange={(e) => setThemeId(e.target.value)}
              style={{
                marginTop: 8,
                background: 'transparent',
                color: 'var(--text)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '4px 8px',
                fontSize: 12,
              }}
            >
              {themes.map((t) => (
                <option key={t.id} value={t.id} style={{ color: '#000' }}>
                  {t.name}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Top-center: flow-view toggles */}
      <div className="hud" style={{ top: 16, left: '50%', transform: 'translateX(-50%)' }}>
        <div className="glass" style={{ padding: 8, display: 'flex', gap: 6 }}>
          {FLOW_VIEWS.map((v) => (
            <button
              key={v}
              className={`toggle ${views.includes(v) ? 'on' : ''}`}
              onClick={() => toggleView(v)}
            >
              {t(VIEW_KEY[v])}
            </button>
          ))}
        </div>
      </div>

      {/* Top-right: language + Predict switch */}
      <div className="hud" style={{ top: 16, right: 16, display: 'flex', gap: 8 }}>
        <button
          className="toggle"
          style={{ padding: '8px 12px', fontSize: 13 }}
          onClick={() => setLang(lang === 'en' ? 'ko' : 'en')}
        >
          {lang === 'en' ? '한국어' : 'EN'}
        </button>
        <button
          className={`toggle ${predict ? 'on' : ''}`}
          style={{ padding: '8px 16px', fontSize: 13 }}
          onClick={togglePredict}
        >
          ✨ {t('predict')} {predict ? 'ON' : 'OFF'}
        </button>
      </div>

      {/* Bottom-center: depth slider */}
      <div className="hud" style={{ bottom: 28, left: '50%', transform: 'translateX(-50%)' }}>
        <div
          className="glass"
          style={{ padding: '10px 18px', display: 'flex', gap: 14, alignItems: 'center' }}
        >
          <span className="dim" style={{ fontSize: 12 }}>
            Depth
          </span>
          <input
            type="range"
            min={1}
            max={depthMax}
            step={1}
            value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}
            style={{ width: 220 }}
          />
          <span className="mono" style={{ width: 18 }}>
            {depth}
          </span>
        </div>
      </div>

      {/* Bottom-left: disclaimer */}
      <div className="hud" style={{ bottom: 16, left: 16 }}>
        <div className="disclaimer glass" style={{ padding: '6px 10px', maxWidth: 320 }}>
          {t('notAdvice')}
        </div>
      </div>
    </>
  );
}
