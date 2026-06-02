/** Typed Engine client (via the same-origin proxy) + SSE runner. */

const BASE = '/api/engine';

export interface Theme {
  id: string;
  name: string;
  depth_max: number;
  status: string;
  version: number;
  model_assignment: Record<string, string>;
  seed_tickers: string[];
  context_notes: string | null;
  research_report: string | null;
  published_at: string | null;
  created_at: string;
  staging_counts: { nodes?: number; edges?: number };
  production_counts: { nodes?: number; edges?: number };
  open_tickets: number;
}

export interface Ticket {
  id: string;
  theme_id: string;
  metric: string;
  target_ref: string;
  reason: string;
  priority: number;
  status: string;
  created_at: string;
  payload: Record<string, unknown>;
  locked_value: number | null;
  source_count: number;
}

export interface AgentEvent {
  seq?: number;
  kind: string;
  message: string;
  job_id?: string;
  data?: Record<string, unknown>;
  // Present on kind === 'log' (engine debug/info/warning/error captured during the run).
  level?: string;
  logger?: string;
}

export interface ParsePreview {
  field: string;
  value: number | null;
  span: string;
  extracted_by: string;
  confidence: string;
  found: boolean;
  source_id: string | null;
}

export interface ValidationReport {
  ok: boolean;
  total: number;
  passed: number;
  failed: number;
  failures: { ref: string; kind: string; missing: string[] }[];
}

export interface GraphEdge {
  type: string;
  from: string;
  to: string;
  product_ref?: string;
  allocation_pct?: number;
  confidence?: string;
  source_id?: string;
  [k: string]: unknown;
}

export interface GraphPayload {
  nodes: Record<string, unknown>[];
  edges: GraphEdge[];
}

export interface PublishDiff {
  staging_counts: { nodes: number; edges: number };
  production_counts: { nodes: number; edges: number };
  added_nodes: string[];
  removed_nodes: string[];
  added_edges: number;
  removed_edges: number;
}

export class PublishError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super('publish failed');
  }
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  listThemes: () => fetch(`${BASE}/themes`).then((r) => json<Theme[]>(r)),
  getTheme: (id: string) => fetch(`${BASE}/themes/${id}`).then((r) => json<Theme>(r)),
  createTheme: (body: {
    name: string;
    depth_max: number;
    model_assignment: Record<string, string>;
    seed_tickers: string[];
  }) =>
    fetch(`${BASE}/themes`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    }).then((r) => json<Theme>(r)),
  deleteTheme: (id: string) =>
    fetch(`${BASE}/themes/${id}`, { method: 'DELETE' }).then((r) => json(r)),
  updateTheme: (id: string, body: { research_report: string | null }) =>
    fetch(`${BASE}/themes/${id}`, {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    }).then((r) => json<Theme>(r)),
  listTickets: (themeId: string) =>
    fetch(`${BASE}/tickets?theme_id=${themeId}`).then((r) => json<Ticket[]>(r)),
  attachSource: (ticketId: string, form: FormData) =>
    fetch(`${BASE}/tickets/${ticketId}/attach`, { method: 'POST', body: form }).then((r) =>
      json(r),
    ),
  parseTicket: (ticketId: string) =>
    fetch(`${BASE}/tickets/${ticketId}/parse`, { method: 'POST' }).then((r) =>
      json<ParsePreview>(r),
    ),
  approveTicket: (ticketId: string, value?: number) =>
    fetch(`${BASE}/tickets/${ticketId}/approve`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ value: value ?? null }),
    }).then((r) => json(r)),
  validate: (themeId: string) =>
    fetch(`${BASE}/themes/${themeId}/validate`).then((r) => json<ValidationReport>(r)),
  publishDiff: (themeId: string) =>
    fetch(`${BASE}/themes/${themeId}/publish/diff`).then((r) => json<PublishDiff>(r)),
  publish: async (themeId: string) => {
    const res = await fetch(`${BASE}/themes/${themeId}/publish`, { method: 'POST' });
    const body = await res.json();
    if (!res.ok) throw new PublishError(res.status, body?.detail ?? body);
    return body as { status: string; version: number; production_counts: { nodes: number } };
  },
  stagingGraph: (themeId: string, views?: string[]) => {
    const q = views?.length ? `?${views.map((v) => `views=${v}`).join('&')}` : '';
    return fetch(`${BASE}/themes/${themeId}/staging-graph${q}`).then((r) => json<GraphPayload>(r));
  },
  editEdge: (themeId: string, edge: GraphEdge, updates: Record<string, unknown>) =>
    fetch(`${BASE}/themes/${themeId}/edges/edit`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        type: edge.type,
        from: edge.from,
        to: edge.to,
        product_ref: edge.product_ref ?? null,
        updates,
      }),
    }).then((r) => json(r)),
};

/** Run the agent and invoke `onEvent` for each streamed SSE line. */
export async function runAgent(
  themeId: string,
  onEvent: (ev: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/themes/${themeId}/run`, { method: 'POST', signal });
  if (!res.body) throw new Error('no stream');
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() ?? '';
    for (const part of parts) {
      const line = part.trim();
      if (line.startsWith('data:')) {
        try {
          onEvent(JSON.parse(line.slice(5).trim()) as AgentEvent);
        } catch {
          /* ignore keep-alive */
        }
      }
    }
  }
}
