import { api } from './api.js';
import { clear, h, icon, toast } from './dom.js';
import { openEvidence } from './evidence.js';
import { S } from './state.js';

const MODES = [['reranked', 'Best (re-reads the top results)'], ['hybrid', 'Keywords and meaning'], ['lexical', 'Keywords only'], ['dense', 'Meaning only']];

export async function renderSearch(host) {
  const results = h('div', { style: 'margin-top:8px' });
  const query = h('input', { type: 'text', placeholder: 'Search the approved documents of this case…', 'aria-label': 'Search query' });
  const mode = h('select', { 'aria-label': 'Search mode', style: 'width:auto' }, MODES.map(([v, l]) => h('option', { value: v }, l)));

  async function run() {
    if (!query.value.trim()) return;
    clear(results).append(h('span', { class: 'spinner' }), ' Searching…');
    try {
      const r = await api('/search', { method: 'POST', body: { case_id: S.caseId, query: query.value, mode: mode.value, limit: 10 } });
      clear(results).append(
        h('div', { class: 'foot', style: 'border:0;margin:0 0 10px;padding:0' }, h('span', { class: 'chip' }, `${r.passages.length} passages`),
          h('span', { class: 'chip' }, `${Math.round(r.elapsed_ms)} ms`), h('span', { class: `chip ${r.excluded?.NOT_ELIGIBLE ? 'amber' : ''}` }, `${r.excluded?.NOT_ELIGIBLE ?? 0} excluded as not eligible`),
          ...(r.warnings || []).map((w) => h('span', { class: 'chip amber' }, w.replace(/_/g, ' ').toLowerCase()))),
        h('p', { class: 'hint' }, 'Excluded means found by the search but dropped by the checks: not approved, expired, replaced, or not yours to read.'),
        h('div', { class: 'passages' }, r.passages.map((p, i) => h('button', { class: 'passage', onclick: () => openEvidence(p.citation_id) },
          h('div', { class: 'path mono' }, `${i + 1}. ${String(p.section_id).split('/').pop()}`), h('p', {}, p.text.replace(/\s+/g, ' ')))),
        r.passages.length ? null : h('p', { class: 'hint' }, 'Nothing matched in the searched sources. That does not mean no such document exists.')));
    } catch (error) { clear(results); toast(error.message, 'error'); }
  }
  query.addEventListener('keydown', (e) => { if (e.key === 'Enter') run(); });
  host.append(h('div', { class: 'scroll' }, h('div', { class: 'page' }, h('h1', {}, 'Search documents'),
    h('p', { class: 'lead' }, 'Retrieval only, with no model. Every result was re-checked against its original file, approval, validity dates and your access. Select a result to read it in the side panel.'),
    h('div', { class: 'searchbar' }, query, mode, h('button', { class: 'btn primary', onclick: run }, icon('search', 14), ' Search')), results)));
  setTimeout(() => query.focus());
}
