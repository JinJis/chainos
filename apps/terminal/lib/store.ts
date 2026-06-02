'use client';

import { create } from 'zustand';
import { FLOW_VIEWS } from '@chainos/graph-schema';

export type FlowView = (typeof FLOW_VIEWS)[number];

interface CanvasState {
  themeId: string | null;
  setThemeId: (id: string) => void;

  depth: number;
  setDepth: (d: number) => void;

  views: FlowView[];
  toggleView: (v: FlowView) => void;

  selectedId: string | null;
  select: (id: string | null) => void;

  hoveredId: string | null;
  hover: (id: string | null) => void;

  // Product "neon laser": highlight the customers a chosen product flows into.
  laser: { product: string; customers: string[] } | null;
  setLaser: (l: { product: string; customers: string[] } | null) => void;

  lang: 'en' | 'ko';
  setLang: (l: 'en' | 'ko') => void;

  predict: boolean;
  togglePredict: () => void;
}

export const useCanvas = create<CanvasState>((set) => ({
  themeId: null,
  setThemeId: (id) => set({ themeId: id }),

  depth: 3,
  setDepth: (d) => set({ depth: d }),

  views: ['supply'],
  toggleView: (v) =>
    set((s) => ({
      views: s.views.includes(v) ? s.views.filter((x) => x !== v) : [...s.views, v],
    })),

  selectedId: null,
  select: (id) => set({ selectedId: id, laser: null }),

  hoveredId: null,
  hover: (id) => set({ hoveredId: id }),

  laser: null,
  setLaser: (l) => set({ laser: l }),

  lang: 'en',
  setLang: (l) => set({ lang: l }),

  predict: false,
  togglePredict: () => set((s) => ({ predict: !s.predict })),
}));
