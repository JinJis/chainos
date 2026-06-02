/** Deterministic radial layout + sizing/coloring for the macro canvas.
 * Positions are computed once from the full node set and stay fixed as the depth
 * slider fades nodes in/out (the “starfield” effect), so the map never reflows. */
import type { CompanyNode } from './api';

export type Vec3 = [number, number, number];

const RING = 6.5;

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 0xffffffff;
}

export function computeLayout(nodes: CompanyNode[]): Map<string, Vec3> {
  const byTier = new Map<number, CompanyNode[]>();
  for (const n of nodes) {
    const t = n.tier ?? 1;
    (byTier.get(t) ?? byTier.set(t, []).get(t)!).push(n);
  }
  const pos = new Map<string, Vec3>();
  for (const [tier, group] of byTier) {
    group.sort((a, b) => (b.market_cap ?? 0) - (a.market_cap ?? 0));
    const n = group.length;
    const radius = tier === 1 ? 0 : tier * RING;
    group.forEach((node, i) => {
      if (tier === 1 && n > 1) {
        // tier-1 mega caps cluster near the core
        const a = (i / n) * Math.PI * 2;
        const r = 3.2;
        pos.set(node.id, [Math.cos(a) * r, (hash(node.id) - 0.5) * 3, Math.sin(a) * r]);
        return;
      }
      const a = (i / Math.max(1, n)) * Math.PI * 2 + tier * 0.6;
      const jitterY = (hash(node.id) - 0.5) * 4;
      pos.set(node.id, [Math.cos(a) * radius, jitterY, Math.sin(a) * radius]);
    });
  }
  return pos;
}

/** Node sphere radius from market cap (log scale). */
export function nodeRadius(marketCap?: number): number {
  if (!marketCap || marketCap <= 0) return 0.5;
  const l = Math.log10(marketCap); // ~9.6 .. 12.5
  return Math.min(3.2, Math.max(0.45, 0.45 + (l - 9.4) * 0.55));
}

const SECTOR_COLORS: Record<string, string> = {
  Semiconductors: '#4da3ff',
  Foundry: '#46f0c8',
  'Semi Equipment': '#b69bff',
  Software: '#ffcc66',
  Internet: '#ff9d4d',
  Memory: '#4da3ff',
  'Data Center Infra': '#46d18a',
  Servers: '#8a96b8',
  PCB: '#ff5d6c',
  Substrates: '#e0a3ff',
};

export function nodeColor(node: CompanyNode): string {
  return SECTOR_COLORS[node.sector] ?? '#6f7db0';
}
