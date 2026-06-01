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
  source_count: number;
}

export interface AgentEvent {
  seq?: number;
  kind: string;
  message: string;
  job_id?: string;
  data?: Record<string, unknown>;
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
  listTickets: (themeId: string) =>
    fetch(`${BASE}/tickets?theme_id=${themeId}`).then((r) => json<Ticket[]>(r)),
  attachSource: (ticketId: string, form: FormData) =>
    fetch(`${BASE}/tickets/${ticketId}/attach`, { method: 'POST', body: form }).then((r) =>
      json(r),
    ),
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
