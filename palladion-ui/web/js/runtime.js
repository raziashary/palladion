import { api } from './api.js';
import { h, icon, popup, toast } from './dom.js';
import { S, emit, modelLabel } from './state.js';

let timer = null;

export function runtimeChip() {
  const r = S.boot?.runtime;
  if (!r) return { tone: 'gray', text: 'Checking…' };
  if (r.state === 'starting') return { tone: 'amber', text: 'Starting…', spin: true };
  if (r.state === 'error') return { tone: 'red', text: 'Runtime error' };
  if (r.state === 'ready') return r.model ? { tone: 'green', text: modelLabel(r.model) } : { tone: 'blue', text: 'Search only' };
  return { tone: 'gray', text: r.api ? 'Palladion running' : 'Palladion stopped' };
}

export async function refreshRuntime() {
  try { S.boot.runtime = await api('/runtime'); } catch { /* keep the last known state */ }
  emit();
  clearTimeout(timer);
  timer = setTimeout(refreshRuntime, S.boot?.runtime?.state === 'starting' ? 1500 : 15000);
}

async function choose(model, close) {
  close();
  try {
    S.boot.runtime = await api('/runtime/model', { method: 'POST', body: { model } });
    emit();
    clearTimeout(timer);
    timer = setTimeout(refreshRuntime, 1200);
    toast(model ? `Starting ${modelLabel(model)}…` : 'Switching to search only…');
  } catch (error) {
    toast(error.message, 'error');
  }
}

export function openModelMenu(anchor, above = true) {
  const r = S.boot.runtime;
  const rows = [{ id: null, label: 'Search only', help: 'No model. Questions run a document search and show the passages.' },
    ...S.boot.models.map((m) => ({ id: m.id, label: m.label, help: 'Runs the Palladion agent with this Groq model.' }))];
  const { menu, close } = popup(anchor, [
    h('div', { class: 'note' }, 'Choosing a model enables live calls to Groq and restarts Palladion (10 to 20 seconds). Nothing falls back silently.'),
    ...rows.map((row) => h('button', { class: 'item', role: 'menuitemradio', 'aria-checked': String((r.model ?? null) === row.id && r.state === 'ready'), onclick: () => choose(row.id, close) },
      icon(row.id ? 'cpu' : 'search', 16), h('span', {}, row.label, h('small', {}, row.help)))),
    r.error ? h('div', { class: 'note', style: 'color:var(--red);border:0' }, r.error) : null,
  ], { above });
  menu.style.minWidth = '300px';
}
