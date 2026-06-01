/**
 * Chainos design tokens. Dark-mode first (the Terminal is a dark 3D space).
 * Confidence colors are shared so Studio and Terminal render trust identically.
 */
export const colors = {
  bg: '#05070d',
  bgPanel: '#0b0f1a',
  bgElevated: '#121829',
  border: '#1d2640',
  text: '#e6ecff',
  textDim: '#8a96b8',
  accent: '#4da3ff',
  gold: '#ffcc66', // revenue-flow particles
  neon: '#46f0c8', // product laser
  danger: '#ff5d6c',
  ok: '#46d18a',
} as const;

/** Confidence → color/icon, surfaced in both Studio and the Terminal UI. */
export const confidenceStyle = {
  verified: { color: '#46d18a', icon: '✓', label: 'Verified', dashed: false },
  derived: { color: '#ffcc66', icon: '≈', label: 'Derived', dashed: true },
  estimated: { color: '#ff9d4d', icon: '?', label: 'Estimated', dashed: true },
} as const;

export type Confidence = keyof typeof confidenceStyle;

/** Predict overlay colors (Ghost Node aurora). */
export const predict = {
  expand: '#4da3ff', // faint blue aurora — beneficiary
  contract: '#ff5d6c', // faint red — hurt
} as const;
