/** Terminal data layer — reads PRODUCTION via the same-origin proxy. */

const BASE = '/api/engine';

export interface CompanyNode {
  id: string;
  label: 'Company';
  name: string;
  ticker: string;
  country: string;
  exchange: string;
  sector: string;
  tier: number;
  market_cap?: number;
  base_date?: string;
  next_update?: string;
}

export interface FlowEdge {
  type: string;
  from: string;
  to: string;
  product_ref?: string;
  allocation_pct?: number;
  amount?: number;
  confidence?: string;
  base_date?: string;
  next_update?: string;
  extracted_value?: string;
  extracted_by?: string;
}

export interface MacroGraph {
  nodes: CompanyNode[];
  edges: FlowEdge[];
}

export interface ThemeRef {
  id: string;
  name: string;
  version: number;
  depth_max: number;
}

export interface CompanyDetail {
  company: CompanyNode;
  divisions: {
    division: { id: string; name: string; revenue_share?: number };
    products: { id: string; name: string; category: string; revenue?: number; margin?: number }[];
  }[];
  customers: { id: string; name: string; edge: FlowEdge }[];
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  themes: () => fetch(`${BASE}/terminal/themes`).then((r) => json<ThemeRef[]>(r)),
  macroGraph: (themeId: string) =>
    fetch(`${BASE}/terminal/graph/${themeId}`).then((r) => json<MacroGraph>(r)),
  companyDetail: (themeId: string, companyId: string) =>
    fetch(`${BASE}/terminal/companies/${themeId}/${companyId}`).then((r) =>
      json<CompanyDetail>(r),
    ),
};
