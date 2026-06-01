'use client';

import { FLOW_VIEW_EDGES } from '@chainos/graph-schema';
import { useQuery } from '@tanstack/react-query';
import dynamic from 'next/dynamic';
import { useEffect, useMemo } from 'react';
import { api } from '../lib/api';
import { computeLayout } from '../lib/layout';
import { useCanvas } from '../lib/store';
import { Hud } from '../components/Hud';

// R3F cannot server-render; load the canvas client-only.
const Scene = dynamic(() => import('../components/Scene').then((m) => m.Scene), { ssr: false });

export default function TerminalPage() {
  const { themeId, setThemeId, depth, views } = useCanvas();

  const { data: themes } = useQuery({ queryKey: ['themes'], queryFn: api.themes });

  useEffect(() => {
    if (!themeId && themes && themes.length > 0) setThemeId(themes[0]!.id);
  }, [themes, themeId, setThemeId]);

  const { data: graph, isLoading } = useQuery({
    queryKey: ['macro', themeId],
    queryFn: () => api.macroGraph(themeId!),
    enabled: !!themeId,
  });

  const positions = useMemo(() => computeLayout(graph?.nodes ?? []), [graph]);
  const tierOf = useMemo(() => {
    const m = new Map<string, number>();
    graph?.nodes.forEach((n) => m.set(n.id, n.tier ?? 1));
    return m;
  }, [graph]);

  const visibleEdges = useMemo(() => {
    if (!graph) return [];
    const types = new Set(views.flatMap((v) => FLOW_VIEW_EDGES[v] ?? []));
    return graph.edges.filter(
      (e) =>
        types.has(e.type) &&
        (tierOf.get(e.from) ?? 9) <= depth &&
        (tierOf.get(e.to) ?? 9) <= depth,
    );
  }, [graph, views, depth, tierOf]);

  const visibleCount = useMemo(
    () => (graph?.nodes ?? []).filter((n) => (n.tier ?? 1) <= depth).length,
    [graph, depth],
  );

  const theme = themes?.find((t) => t.id === themeId) ?? null;

  return (
    <main>
      {graph && (
        <div className="canvas-root">
          <Scene nodes={graph.nodes} positions={positions} edges={visibleEdges} />
        </div>
      )}
      <Hud
        theme={theme}
        themes={themes ?? []}
        nodeCount={graph?.nodes.length ?? 0}
        visibleCount={visibleCount}
      />
      {(isLoading || !themeId) && (
        <div
          className="hud"
          style={{ inset: 0, display: 'grid', placeItems: 'center' }}
        >
          <div className="glass" style={{ padding: '20px 28px' }}>
            {!themeId && themes?.length === 0
              ? 'No published themes yet. Publish one in Studio.'
              : 'Loading value chain…'}
          </div>
        </div>
      )}
    </main>
  );
}
