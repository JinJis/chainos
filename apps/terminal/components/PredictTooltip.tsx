'use client';

import type { PredictPayload } from '../lib/api';
import { useCanvas } from '../lib/store';

/** Insight tooltip for the Predict overlay: hovering an expanding/contracting node
 * reveals the predicted move, its news basis, and the engine that analyzed it. */
export function PredictTooltip({ predict }: { predict: PredictPayload | null }) {
  const hoveredId = useCanvas((s) => s.hoveredId);
  const on = useCanvas((s) => s.predict);
  if (!on || !predict) return null;
  const node = hoveredId ? predict.nodes[hoveredId] : null;

  return (
    <div className="hud" style={{ bottom: 28, right: 16, width: 320 }}>
      <div className="glass" style={{ padding: 14 }}>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <b style={{ fontSize: 13 }}>✨ Predict</b>
          <span className="dim" style={{ fontSize: 11 }}>
            {predict.news_count} news · {predict.links} links
          </span>
        </div>
        {!node && (
          <div className="dim" style={{ fontSize: 12, marginTop: 6 }}>
            Nodes pulse blue (beneficiary) or red (hurt). Hover one for the basis.
          </div>
        )}
        {node && (
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 15, fontWeight: 700 }}>
              {node.name}{' '}
              <span
                style={{
                  color: node.direction === 'contract' ? 'var(--danger)' : 'var(--accent)',
                }}
              >
                {node.expected_delta_pct >= 0 ? '+' : ''}
                {node.expected_delta_pct}% short-term momentum
              </span>
            </div>
            <ul style={{ fontSize: 12, paddingLeft: 16, marginTop: 6 }}>
              {node.evidence.slice(0, 3).map((e, i) => (
                <li key={i} style={{ marginBottom: 4 }}>
                  <span className="dim">{e.source}:</span> {e.headline}
                  <div style={{ color: e.polarity >= 0 ? 'var(--ok)' : 'var(--danger)' }}>
                    → {e.reason}
                  </div>
                </li>
              ))}
            </ul>
            <div className="dim" style={{ fontSize: 11, marginTop: 4 }}>
              analyzed by the {node.engine} engine · momentum simulation, not a forecast
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
