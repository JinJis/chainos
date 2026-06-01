/**
 * Canonical Chainos knowledge-graph spec — THE single source of truth.
 *
 * Both the Zod validators / TS types (./build.ts) and the generated Python
 * Pydantic mirror (../gen/gen-python.ts) are derived from this object. Edit the
 * graph contract HERE and nowhere else; run `pnpm --filter @chainos/graph-schema gen`
 * to regenerate the Python side. See PRD §5 and CLAUDE.md §5.
 */

export const CONFIDENCE = ['verified', 'derived', 'estimated'] as const;
export const SOURCE_TYPE = ['filing', 'IR', 'report', 'news'] as const;
export const SUPPLY_DIRECTION = ['upstream', 'downstream'] as const;

/** Field primitive types understood by both the TS and Python generators. */
export type FieldType =
  | 'string'
  | 'number'
  | 'int'
  | 'boolean'
  | 'enum:confidence'
  | 'enum:source_type'
  | 'enum:supply_direction';

export interface FieldSpec {
  type: FieldType;
  optional?: boolean;
  /** Marks a value as quantitative — the validation gate requires trust meta for it. */
  quantitative?: boolean;
  doc?: string;
}

export interface EntitySpec {
  /** Neo4j label / relationship type. */
  label: string;
  doc: string;
  fields: Record<string, FieldSpec>;
}

export interface EdgeSpec extends EntitySpec {
  from: string;
  to: string;
  /** A quantitative edge MUST carry trust meta + a SOURCED_FROM link before publish. */
  quantitative: boolean;
}

/** Trust metadata attached to every quantitative value (PRD §5.3, CLAUDE.md §1). */
export const TRUST_FIELDS: Record<string, FieldSpec> = {
  base_date: { type: 'string', doc: 'As-of date of the figure, e.g. "26 Q1 filing".' },
  next_update: { type: 'string', doc: 'When the figure will next be refreshed.' },
  confidence: { type: 'enum:confidence', doc: 'verified | derived | estimated.' },
};

export const NODE_SPECS: Record<string, EntitySpec> = {
  Theme: {
    label: 'Theme',
    doc: 'Industry / theme, e.g. "AI Data Centers".',
    fields: {
      id: { type: 'string' },
      name: { type: 'string' },
      depth_max: { type: 'int' },
      version: { type: 'int' },
      published_at: { type: 'string', optional: true },
    },
  },
  Company: {
    label: 'Company',
    doc: 'A listed company. Node size in the Terminal binds to market_cap.',
    fields: {
      id: { type: 'string' },
      ticker: { type: 'string' },
      name: { type: 'string' },
      country: { type: 'string' },
      exchange: { type: 'string' },
      sector: { type: 'string' },
      tier: { type: 'int', doc: 'Depth level in the value chain (1 = mega-cap).' },
      market_cap: { type: 'number', optional: true, quantitative: true, doc: 'Live market cap.' },
      base_date: { type: 'string' },
      next_update: { type: 'string' },
    },
  },
  Division: {
    label: 'Division',
    doc: 'A business unit, e.g. Samsung DS.',
    fields: {
      id: { type: 'string' },
      name: { type: 'string' },
      parent_company: { type: 'string' },
      revenue_share: { type: 'number', optional: true, quantitative: true, doc: '% of company revenue.' },
    },
  },
  Product: {
    label: 'Product',
    doc: 'A product / service, e.g. HBM3E 12-Hi.',
    fields: {
      id: { type: 'string' },
      name: { type: 'string' },
      category: { type: 'string' },
      unit_price: { type: 'number', optional: true, quantitative: true },
      revenue: { type: 'number', optional: true, quantitative: true },
      margin: { type: 'number', optional: true, quantitative: true },
    },
  },
  Source: {
    label: 'Source',
    doc: 'Evidence backing a figure. Every number links to one via SOURCED_FROM.',
    fields: {
      id: { type: 'string' },
      type: { type: 'enum:source_type' },
      url: { type: 'string' },
      publisher: { type: 'string' },
      as_of_date: { type: 'string' },
      confidence: { type: 'enum:confidence' },
    },
  },
};

export const EDGE_SPECS: Record<string, EdgeSpec> = {
  HAS_DIVISION: {
    label: 'HAS_DIVISION',
    doc: 'Company owns a division.',
    from: 'Company',
    to: 'Division',
    quantitative: false,
    fields: {},
  },
  PRODUCES: {
    label: 'PRODUCES',
    doc: 'Division produces a product.',
    from: 'Division',
    to: 'Product',
    quantitative: false,
    fields: {
      capacity: { type: 'string', optional: true },
      yield: { type: 'number', optional: true, quantitative: true },
    },
  },
  SUPPLIES: {
    label: 'SUPPLIES',
    doc: 'Supply relationship (product flow) between two companies.',
    from: 'Company',
    to: 'Company',
    quantitative: true,
    fields: {
      product_ref: { type: 'string' },
      allocation_pct: { type: 'number', quantitative: true },
      direction: { type: 'enum:supply_direction', optional: true },
    },
  },
  REVENUE_FLOW: {
    label: 'REVENUE_FLOW',
    doc: 'Flow of revenue / money between two companies.',
    from: 'Company',
    to: 'Company',
    quantitative: true,
    fields: {
      amount: { type: 'number', quantitative: true },
      currency: { type: 'string' },
      period: { type: 'string' },
      share_pct: { type: 'number', optional: true, quantitative: true },
    },
  },
  INVESTS_IN: {
    label: 'INVESTS_IN',
    doc: 'Equity stake / CAPEX from one company into another.',
    from: 'Company',
    to: 'Company',
    quantitative: true,
    fields: {
      stake_pct: { type: 'number', optional: true, quantitative: true },
      amount: { type: 'number', optional: true, quantitative: true },
    },
  },
  COMPETES_WITH: {
    label: 'COMPETES_WITH',
    doc: 'Competition between two companies (undirected in meaning).',
    from: 'Company',
    to: 'Company',
    quantitative: false,
    fields: {
      overlap_score: { type: 'number', optional: true },
    },
  },
  SOURCED_FROM: {
    label: 'SOURCED_FROM',
    doc: 'Links any numeric edge/value to its evidence Source.',
    from: 'Edge',
    to: 'Source',
    quantitative: false,
    fields: {
      extracted_value: { type: 'string', doc: 'Exact span/value extracted.' },
      extracted_by: { type: 'string', doc: 'Model id that extracted it.' },
    },
  },
};

/** Flow-filter views available in the Terminal (PRD §7 Step 2). */
export const FLOW_VIEWS = ['supply', 'revenue', 'investment', 'cost', 'rnd'] as const;

/** Maps each Terminal flow view to the edge types it surfaces. */
export const FLOW_VIEW_EDGES: Record<(typeof FLOW_VIEWS)[number], string[]> = {
  supply: ['SUPPLIES'],
  revenue: ['REVENUE_FLOW'],
  investment: ['INVESTS_IN'],
  cost: ['SUPPLIES'],
  rnd: ['PRODUCES'],
};
