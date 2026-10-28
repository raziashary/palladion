import { api, qs } from './api.js';
import { clear, h, icon } from './dom.js';
import { BASIS_WORDS, KIND_LABEL, citationTitle, evidenceKind, failureText, fmtTime, shortId, toneOf } from './format.js';
import { S, activeCase, emit, modelLabel, persona } from './state.js';

export async function openEvidence(id, hint) {
  S.panelOpen = true;
  S.sections.reading = true;
  document.getElementById('app').classList.remove('no-panel');
  S.evidence = { id, kind: evidenceKind(id, hint), state: 'loading' };
  emit();
  try {
    S.evidence = { ...S.evidence, state: 'ok', data: await api(`/evidence/${encodeURIComponent(id)}` + qs({ case_id: S.caseId })) };
  } catch (error) {
    S.evidence = { ...S.evidence, state: 'error', error: error.message };
  }
  emit();
}

const chip = (text, tone = '') => h('span', { class: `chip ${tone}` }, text);
function kv(pairs) {
  return h('dl', { class: 'kv' }, pairs.filter(([, v]) => v != null && v !== '').flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v)]));
}

function documentView(d) {
  return [
    h('div', { class: 'verified' }, icon('check', 14), 'Original bytes re-checked now, under your current access'),
    kv([['Revision', h('span', { class: 'mono' }, shortId(d.revision_id, 12))], ['Section', String(d.section_id || '').split('/').pop()],
      ['Bytes', d.start_byte != null ? `${d.start_byte} to ${d.end_byte}` : null], ['Index generation', persona()?.roles.includes('admin') ? shortId(d.generation || '', 14) : null]]),
    h('div', {}, h('h3', {}, 'Exact text'), h('div', { class: 'source-text mono' }, d.text || '')),
    h('p', { class: 'hint' }, 'This is a citation: it proves where the words came from, not that they answer the question.'),
  ];
}

function liveView(d) {
  const data = Object.entries(d.data || {});
  return [
    h('div', {}, chip(d.status || 'UNKNOWN', toneOf(d.status)), ' ', d.valid === false ? chip('Too old for a decision', 'amber') : d.valid ? chip('Fresh', 'green') : null),
    kv([['System', d.source_system], ['Reading', String(d.operation || '').replace(/^get_/, '').replace(/_/g, ' ')], ['Read at', fmtTime(d.observed_at)],
      ['Data as of', fmtTime(d.data_as_of)], ['Event time', fmtTime(d.source_event_at)]]),
    data.length ? h('div', {}, h('h3', {}, 'What the system returned'), kv(data.map(([k, v]) => [k.replace(/_/g, ' '), String(v)]))) : null,
    h('p', { class: 'hint' }, 'A reading is a fact at one moment, never permission to act. Ask again to take a new one.'),
  ];
}

function policyView(d) {
  const holder = h('div', {});
  const refs = d.clause_refs || [];
  return [
    h('div', {}, chip(d.status, toneOf(d.status)), ' ', chip('Decision support only', 'blue')),
    kv([['Policy', d.family_id], ['Version', d.version_id], ['Chosen by', BASIS_WORDS[d.time_basis] || d.time_basis], ['As of', fmtTime(d.as_of)]]),
    refs.length ? h('div', {}, h('h3', {}, 'Source clauses'), refs.map((r) => h('button', { class: 'btn small', style: 'margin:0 6px 6px 0', onclick: async () => {
      clear(holder).append(h('span', { class: 'spinner' }));
      try {
        const c = await api(`/evidence/${encodeURIComponent(d.evidence_id)}/clauses/${r.clause_index}` + qs({ case_id: S.caseId, version_id: r.version_id }));
        clear(holder).append(h('div', { class: 'source-text mono' }, c.text), h('p', { class: 'hint' }, `${r.applicability === 'SELECTED' ? 'Selected' : 'Candidate'} clause from ${shortId(c.revision_id, 10)}`));
      } catch (error) { clear(holder).append(h('p', { class: 'hint' }, error.message)); }
    } }, `Read clause ${r.clause_index + 1}${r.applicability === 'UNRESOLVED_CANDIDATE' ? ' (candidate)' : ''}`)), holder) : null,
    h('p', { class: 'hint' }, 'The decision is re-selected each time it is read. If a different version would apply now, or a reading has gone stale, it is refused.'),
  ];
}

function eventView(d) {
  return [chip('No authority', 'gray'), h('p', { class: 'hint' }, 'Remembered context. It is shown so you can see what the agent was told, and it is never evidence.'),
    h('div', { class: 'source-text mono' }, JSON.stringify(d.context || d, null, 2).slice(0, 4000))];
}

function evidenceBody() {
  const e = S.evidence;
  if (!e) return [h('div', { class: 'empty', style: 'padding:30px 10px' }, h('p', { class: 'hint' }, 'Select a citation on an answer to read the exact evidence behind it.'))];
  const head = h('div', {}, h('h3', {}, KIND_LABEL[e.kind] || 'Evidence'), h('span', { class: 'mono hint' }, shortId(e.id, 14)));
  if (e.state === 'loading') return [head, h('div', {}, h('span', { class: 'spinner' }), ' Reading from Palladion…')];
  if (e.state === 'error') return [head, h('div', { class: 'card errorcard' }, `This evidence can’t be read now: ${e.error}. Access, approval or freshness may have changed since the answer was given.`),
    h('button', { class: 'btn', onclick: () => openEvidence(e.id, e.kind) }, 'Try again')];
  const d = e.data;
  const kind = d.kind || e.kind;
  const body = kind === 'DOCUMENT' ? documentView(d) : kind === 'LIVE_OBSERVATION' ? liveView(d) : kind === 'POLICY_DECISION' ? policyView(d) : eventView(d);
  return [head, ...body, h('button', { class: 'btn small', style: 'align-self:flex-start', onclick: () => openEvidence(e.id, e.kind) }, 'Re-check now')];
}

function meter(label, used, max) {
  return h('div', { style: 'margin-bottom:8px' }, h('div', { class: 'hint', style: 'display:flex;justify-content:space-between' }, h('span', {}, label), h('span', {}, `${used} of ${max}`)),
    h('div', { class: 'meter' }, h('i', { style: `width:${Math.min(100, (used / max) * 100)}%` })));
}

function checksBody() {
  const run = S.run;
  if (!run) return [h('p', { class: 'hint', style: 'margin:0' }, 'After an answer: which checks ran, what could not be verified and what was searched.')];
  const r = run.response;
  const status = Object.entries(r.tool_status || {});
  const trace = h('div', {});
  const budget = r.budget || {};
  return [
    h('div', { class: 'evlist' }, status.length ? status.map(([k, v]) => chip(`${k.replace(/_/g, ' ')}: ${v}`, toneOf(v))) : chip('No tools ran', 'gray')),
    (r.verification_failures || []).length ? h('div', { class: 'hint', style: 'color:var(--amber)' }, r.verification_failures.map(failureText).join('; ')) : null,
    budget.main_used != null ? meter('Model calls', budget.main_used, 5) : null,
    budget.critic_used != null ? meter('Independent review calls', budget.critic_used, 3) : null,
    kv([['Independent review', r.review_status], ['Time', run.elapsed != null ? `${run.elapsed} s` : null]]),
    h('p', { class: 'hint', style: 'margin:0' }, r.searched_scope, ' Palladion cannot know whether every company document was supplied, so “not found” never means “does not exist”.'),
    persona()?.roles.includes('admin') && r.trace_id ? h('div', {}, h('button', { class: 'btn small', onclick: async () => {
      clear(trace).append(h('span', { class: 'spinner' }));
      try { const t = await api(`/trace/${r.trace_id}` + qs({ case_id: S.caseId })); clear(trace).append(h('div', { class: 'source-text mono' }, JSON.stringify(t, null, 2).slice(0, 6000))); }
      catch (error) { clear(trace).append(h('p', { class: 'hint' }, error.message)); }
    } }, 'Load developer trace (admin)'), trace) : null,
  ];
}

function evidenceListBody() {
  const items = S.run?.response?.citations || [];
  if (!items.length) return [h('p', { class: 'hint', style: 'margin:0' }, 'The documents, readings and policy decisions behind an answer are listed here.')];
  return items.map((c) => h('button', { class: `nav-item ${S.evidence?.id === c.evidence_id ? 'active' : ''}`, onclick: () => openEvidence(c.evidence_id, c.kind), style: 'padding:5px 8px' },
    icon(evidenceKind(c.evidence_id, c.kind) === 'DOCUMENT' ? 'doc' : evidenceKind(c.evidence_id, c.kind) === 'LIVE_OBSERVATION' ? 'bolt' : 'book', 15),
    h('span', { style: 'flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' }, citationTitle(c)),
    c.status ? chip(c.status, toneOf(c.status)) : null));
}

function caseBody() {
  const c = activeCase();
  const r = S.boot?.runtime;
  return [kv([['Identity', persona()?.id], ['Roles', persona()?.roles.join(', ')], ['Case', c?.id], ['Transaction', c?.transaction_id], ['Product', c ? `${c.product} · ${c.transaction_class}` : null],
    ['Opened', c ? fmtTime(c.opened_at) : null], ['Model', r?.model ? modelLabel(r.model) : 'None (search only)'], ['Session', S.sessionId ? shortId(S.sessionId, 8) : 'New']]),
  h('p', { class: 'hint', style: 'margin:0' }, 'Synthetic data and mock systems only. The agent has four read tools and cannot change anything.')];
}

function section(key, title, body, count) {
  const open = S.sections[key];
  return h('div', { class: 'psec' },
    h('button', { class: 'psec-h', 'aria-expanded': String(open), onclick: () => { S.sections[key] = !S.sections[key]; emit(); } },
      h('span', {}, title), h('span', { style: 'flex:1' }), count != null ? h('span', { class: 'hint' }, count) : null, h('span', { class: open ? '' : 'rot' }, icon('chevron', 14))),
    open ? h('div', { class: 'psec-b' }, body) : null);
}

export function renderPanel(el) {
  clear(el);
  const count = S.run?.response?.citations?.length;
  el.append(h('div', { class: 'panel-body' },
    S.evidence ? section('reading', 'Reading', evidenceBody()) : null,
    section('evidence', 'Evidence', evidenceListBody(), count || null),
    section('checks', 'Checks', checksBody()),
    section('case', 'Case', caseBody())));
}
