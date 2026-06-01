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
  select: (id) => set({ selectedId: id }),

  hoveredId: null,
  hover: (id) => set({ hoveredId: id }),

  predict: false,
  togglePredict: () => set((s) => ({ predict: !s.predict })),
}));
