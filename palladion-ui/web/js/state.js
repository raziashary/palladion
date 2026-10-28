// One shared, plain object. Views read it and call emit() when something that other views show has changed.
export const S = {
  boot: null,          // /api/bootstrap
  caseId: null,
  sessions: [],        // sessions of the active case
  sessionId: null,
  panelTab: 'evidence',
  panelOpen: innerWidth >= 1100,
  sidebarOpen: innerWidth >= 760,
  evidence: null,      // what the right panel shows: {id, kind, state: 'loading'|'ok'|'error', data, error}
  run: null,           // details of the latest answer: {response, model, elapsed}
  busy: false,
  sections: { reading: true, evidence: true, checks: true, case: false },
};

const listeners = new Set();
export const onChange = (fn) => { listeners.add(fn); return () => listeners.delete(fn); };
export const emit = () => listeners.forEach((fn) => fn());

export const persona = () => S.boot?.persona;
export const activeCase = () => S.boot?.cases.find((c) => c.id === S.caseId);
export const modelLabel = (id) => S.boot?.models.find((m) => m.id === id)?.label || id;

export function remember(key, value) { try { localStorage.setItem(`pui.${key}`, value); } catch { /* private mode */ } }
export function recall(key) { try { return localStorage.getItem(`pui.${key}`); } catch { return null; } }
