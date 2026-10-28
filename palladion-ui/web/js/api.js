import { sseParser } from './format.js';

const HEADERS = { 'X-Palladion-UI': '1', 'Content-Type': 'application/json' };

export class ApiError extends Error {
  constructor(message, status, code, data) { super(message); this.status = status; this.code = code; this.data = data; }
}

export async function api(path, { method = 'GET', body } = {}) {
  let response;
  try {
    response = await fetch('/api' + path, { method, headers: HEADERS, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError('The UI server is not reachable.', 0, 'OFFLINE');
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(data?.error?.message || data?.detail || response.statusText, response.status, data?.error?.code, data);
  return data;
}

export const qs = (params) => '?' + new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== '')).toString();

// POST /api/chat and call onEvent(name, data) for every server-sent event, as it arrives.
export async function streamChat(body, onEvent, signal) {
  const response = await fetch('/api/chat', { method: 'POST', headers: HEADERS, body: JSON.stringify(body), signal });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(data?.error?.message || response.statusText, response.status, data?.error?.code);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parse = sseParser();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    for (const [name, data] of parse(decoder.decode(value, { stream: true }))) onEvent(name, data);
  }
}
