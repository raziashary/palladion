import { api } from './api.js';
import { clear, h, icon, toast } from './dom.js';
import { OPERATOR_WORDS, fmtDay, policySentences, toneOf } from './format.js';
import { S, persona } from './state.js';

const STEPS = ['Basics', 'Source', 'Facts', 'Rules', 'Review'];
const today = () => new Date().toISOString().slice(0, 10);
const field = (label, control, hint) => h('div', { class: 'field' }, h('label', {}, label), control, hint ? h('span', { class: 'hint' }, hint) : null);

function blankDraft() {
  return { version_id: '', family_id: '', case_ids: [S.caseId], time_basis: '', domain_event: '', valid_from: today(), valid_to: '', clauses: [], facts: [], rules: [], default_outcome: '' };
}

export async function renderPolicies(host) {
  const me = persona();
  const meta = await api('/policies/meta');
  const page = h('div', { class: 'page' });
  const listHost = h('div');
  const wizardHost = h('div');
  host.append(h('div', { class: 'scroll' }, page));

  async function refresh() {
    clear(listHost);
    try {
      const { policies } = await api(`/policies?case_id=${encodeURIComponent(S.caseId)}`);
      families = [...new Set(policies.map((p) => p.family_id))];
      listHost.append(policies.length ? h('div', { class: 'list' }, policies.map((p) => card(p, policies))) : h('div', { class: 'card' }, 'No policies are registered for this case yet.'));
    } catch (error) {
      listHost.append(h('div', { class: 'card' }, error.status === 403 ? `Policies are managed by administrators. ${me.id} can’t view them: switch identity (bottom left) to admin-a.` : error.message));
    }
  }
  let families = [];

  function card(p, all) {
    const rivals = all.filter((o) => o.family_id === p.family_id && o.state === 'APPROVED' && o.version_id !== p.version_id);
    const detail = h('details', {}, h('summary', { class: 'hint', style: 'cursor:pointer' }, 'In plain words'), h('ul', { class: 'summary' }, policySentences(p).map((s) => h('li', {}, s))));
    const predecessor = h('select', { style: 'width:auto' }, rivals.map((r) => h('option', { value: r.version_id }, r.version_id)));
    const when = h('input', { type: 'date', value: p.valid_from.slice(0, 10), style: 'width:auto' });
    const reason = h('input', { type: 'text', placeholder: 'Why does it replace the other one?' });
    const replace = rivals.length && p.state === 'APPROVED' && !p.supersedes.length ? h('details', {}, h('summary', { class: 'hint', style: 'cursor:pointer' }, 'This version replaces another'),
      h('div', { class: 'row', style: 'margin-top:8px;align-items:end' }, field('Replaces', predecessor), field('From', when), field('Reason', reason),
        h('button', { class: 'btn small', onclick: async () => {
          try { await api(`/policies/${p.version_id}/supersede`, { method: 'POST', body: { case_id: S.caseId, predecessor_version_id: predecessor.value, valid_from: when.value, reason: reason.value } }); toast('Replacement recorded'); refresh(); }
          catch (error) { toast(error.message, 'error'); }
        } }, 'Record replacement'))) : null;
    return h('div', { class: 'item-card', style: 'align-items:flex-start' }, icon('book', 22),
      h('div', { class: 'grow' }, h('div', { class: 'name' }, p.family_id, h('span', { class: 'hint' }, `  ${p.version_id}`)),
        h('div', { class: 'sub' }, `From ${fmtDay(p.valid_from)}${p.valid_to ? ' to ' + fmtDay(p.valid_to) : ''} · ${p.rules.length} rule${p.rules.length === 1 ? '' : 's'} · ${p.clauses.length} source clause${p.clauses.length === 1 ? '' : 's'}`),
        p.supersedes.length ? h('div', { class: 'sub' }, `Replaces ${p.supersedes.join(', ')}`) : null, p.superseded_by.length ? h('div', { class: 'sub' }, `Replaced by ${p.superseded_by.join(', ')}`) : null,
        detail, replace),
      h('div', { style: 'display:flex;flex-direction:column;gap:6px;align-items:flex-end' }, h('span', { class: `chip ${toneOf(p.state)}` }, p.state),
        p.state === 'APPROVED' ? h('button', { class: 'btn danger small', onclick: async () => { if (!confirm('Revoke this policy version? It stops being selected immediately; the audit trail keeps it.')) return;
          try { await api(`/policies/${p.version_id}/revoke`, { method: 'POST', body: { case_id: S.caseId } }); toast('Revoked'); refresh(); } catch (error) { toast(error.message, 'error'); } } }, 'Revoke') : null));
  }

  // The wizard ---------------------------------------------------------------------------------------------------------

  function wizard() {
    const d = blankDraft();
    let step = 0;
    let problems = [];
    const body = h('div');
    const nav = h('div', { style: 'display:flex;justify-content:space-between;margin-top:14px' });
    const bar = h('div', { class: 'wsteps' });
    const root = h('div', { class: 'wizard', id: 'wizard' }, h('div', { style: 'display:flex;justify-content:space-between' }, h('h2', {}, 'New policy'),
      h('button', { class: 'icon-btn', 'aria-label': 'Close', onclick: () => clear(wizardHost) }, icon('x'))), bar, body, nav);

    const redraw = () => {
      clear(bar).append(...STEPS.map((s, i) => h('span', { class: `wstep ${i === step ? 'on' : i < step ? 'done' : ''}` }, `${i + 1}. ${s}`)));
      clear(body).append(...[basics, source, facts, rules, review][step]());
      clear(nav).append(h('button', { class: 'btn', disabled: step === 0, onclick: () => { step--; redraw(); } }, 'Back'),
        step < STEPS.length - 1 ? h('button', { class: 'btn primary', id: 'next', onclick: () => { step++; redraw(); } }, 'Next') : h('button', { class: 'btn primary', id: 'register', disabled: !me.can_approve, onclick: register }, me.can_approve ? 'Register policy' : 'Switch to admin-a to register'));
    };

    function basics() {
      const family = h('input', { type: 'text', id: 'family', value: d.family_id, list: 'families', placeholder: 'e.g. REVERSAL.CHECK', oninput: (e) => { d.family_id = e.target.value; if (!d.version_id || d.version_id === auto) { auto = d.family_id ? `${d.family_id}-v1` : ''; d.version_id = auto; version.value = auto; } } });
      let auto = '';
      const version = h('input', { type: 'text', id: 'version', value: d.version_id, oninput: (e) => { d.version_id = e.target.value; } });
      const eventName = h('input', { type: 'text', value: d.domain_event, placeholder: 'e.g. dispute_submitted', oninput: (e) => { d.domain_event = e.target.value; } });
      const eventField = field('Event name', eventName, 'Must match a named event on the case.');
      eventField.hidden = d.time_basis !== 'DOMAIN_EVENT_AT';
      return [h('datalist', { id: 'families' }, families.map((f) => h('option', { value: f }))),
        h('div', { class: 'row' }, field('Policy name', family, 'Use an existing name to add a new version of that policy.'), field('Version ID', version, 'Unique. Filled in for you.')),
        h('div', { class: 'label', style: 'margin:4px 0 8px' }, 'Which date decides when this policy applies?'),
        ...meta.time_bases.map((b) => h('label', { class: `radio-card ${d.time_basis === b.id ? 'on' : ''}`, 'data-basis': b.id },
          h('input', { type: 'radio', name: 'basis', checked: d.time_basis === b.id, onchange: () => { d.time_basis = b.id; redraw(); } }), h('span', {}, b.label, h('small', {}, b.help)))),
        eventField,
        h('div', { class: 'row' }, field('Applies from', h('input', { type: 'date', value: d.valid_from, oninput: (e) => { d.valid_from = e.target.value; } })),
          field('Until (optional)', h('input', { type: 'date', value: d.valid_to, oninput: (e) => { d.valid_to = e.target.value; } }), 'Leave empty for no end date.'))];
    }

    function source() {
      const q = h('input', { type: 'text', placeholder: 'Search the approved documents for the clause this policy comes from…', id: 'clause-query' });
      const found = h('div', { class: 'passages', style: 'margin-top:10px' });
      const chosen = h('div');
      const drawChosen = () => clear(chosen).append(d.clauses.length ? h('div', {}, h('h3', { class: 'label', style: 'margin:14px 0 6px' }, 'Source clauses'), d.clauses.map((c, i) => h('div', { class: 'subcard' },
        h('div', { style: 'display:flex;justify-content:space-between' }, h('b', {}, `Clause ${i + 1}`), h('button', { class: 'icon-btn', 'aria-label': 'Remove clause', onclick: () => { d.clauses.splice(i, 1); drawChosen(); } }, icon('x', 14))),
        h('p', { class: 'hint', style: 'margin:4px 0 0' }, c.preview)))) : h('p', { class: 'hint' }, 'The policy’s rules must trace to exact approved text. Pick at least one passage.'));
      const search = async () => {
        if (!q.value.trim()) return;
        clear(found).append(h('span', { class: 'spinner' }));
        try {
          const r = await api('/search', { method: 'POST', body: { case_id: S.caseId, query: q.value, mode: 'reranked', limit: 6 } });
          clear(found).append(...r.passages.map((p) => h('div', { class: 'passage', style: 'display:flex;gap:10px;align-items:center' }, h('div', { style: 'flex:1;min-width:0' }, h('div', { class: 'path mono' }, String(p.section_id).split('/').pop()), h('p', {}, p.text.replace(/\s+/g, ' '))),
            h('button', { class: 'btn small', onclick: () => { if (!d.clauses.some((c) => c.sha256 === p.sha256)) d.clauses.push({ revision_id: p.revision_id, section_id: p.section_id, start_byte: p.start_byte, end_byte: p.end_byte, sha256: p.sha256, preview: p.text.replace(/\s+/g, ' ').slice(0, 220) }); drawChosen(); } }, 'Use as source'))));
          if (!r.passages.length) found.append(h('p', { class: 'hint' }, 'Nothing matched. Try other words.'));
        } catch (error) { clear(found); toast(error.message, 'error'); }
      };
      q.addEventListener('keydown', (e) => { if (e.key === 'Enter') search(); });
      drawChosen();
      return [h('div', { class: 'searchbar' }, q, h('button', { class: 'btn', onclick: search }, 'Search')), found, chosen];
    }

    function facts() {
      const rows = h('div');
      const draw = () => clear(rows).append(...d.facts.map((f, i) => {
        const op = meta.operations[f.operation];
        return h('div', { class: 'subcard' }, h('div', { class: 'row' },
          field('System', h('select', { onchange: (e) => { f.operation = e.target.value; const first = meta.operations[f.operation].fields[0]; f.field = first.name; f.type = first.type; f.name = first.name; f.max_age_seconds = meta.operations[f.operation].max_age; draw(); } },
            Object.entries(meta.operations).map(([k, v]) => h('option', { value: k, selected: k === f.operation }, v.label)))),
          field('Reading', h('select', { onchange: (e) => { f.field = e.target.value; f.name = e.target.value; f.type = op.fields.find((x) => x.name === f.field).type; } }, op.fields.map((x) => h('option', { value: x.name, selected: x.name === f.field }, x.label)))),
          field('Name in rules', h('input', { type: 'text', value: f.name, oninput: (e) => { f.name = e.target.value; } })),
          field('Fresh within (minutes)', h('input', { type: 'number', min: 1, max: 1440, value: Math.round(f.max_age_seconds / 60), oninput: (e) => { f.max_age_seconds = Math.round(Number(e.target.value) * 60); } }))),
        h('button', { class: 'btn danger small', onclick: () => { d.facts.splice(i, 1); draw(); } }, 'Remove'));
      }));
      draw();
      return [h('p', { class: 'hint', style: 'margin-top:0' }, 'Facts are live readings the rules compare, such as the settlement state. Palladion reads them itself, and the agent can only point at readings it took. Skip this step if the policy needs none.'),
        rows, h('button', { class: 'btn', id: 'add-fact', onclick: () => { const o = meta.operations.get_settlement_status; d.facts.push({ name: 'settlement_state', operation: 'get_settlement_status', field: 'settlement_state', type: 'enum', allowed_values: [], max_age_seconds: o.max_age }); draw(); } }, 'Add a fact')];
    }

    function rules() {
      const rows = h('div');
      const factOf = (name) => d.facts.find((f) => f.name === name);
      const valuesOf = (f) => (f && f.type === 'enum' ? meta.operations[f.operation].fields.find((x) => x.name === f.field).values : null);
      const draw = () => clear(rows).append(...d.rules.map((r, i) => h('div', { class: 'subcard' },
        h('div', { class: 'row' }, field('Rule name', h('input', { type: 'text', value: r.id, oninput: (e) => { r.id = e.target.value; } })),
          field('When', h('select', { onchange: (e) => { r.match = e.target.value; } }, [['all', 'all of these are true'], ['any', 'any of these is true']].map(([v, l]) => h('option', { value: v, selected: r.match === v }, l))))),
        ...r.conditions.map((c, j) => {
          const f = factOf(c.fact); const values = valuesOf(f);
          return h('div', { class: 'cond' },
            h('select', { 'aria-label': 'Fact', onchange: (e) => { c.fact = e.target.value; c.value = ''; draw(); } }, h('option', { value: '' }, 'Choose a fact'), d.facts.map((x) => h('option', { value: x.name, selected: x.name === c.fact }, x.name.replace(/_/g, ' ')))),
            h('select', { 'aria-label': 'Comparison', onchange: (e) => { c.operator = e.target.value; } }, Object.entries(OPERATOR_WORDS).filter(([k]) => meta.operators[f?.type || 'enum'].includes(k)).map(([k, l]) => h('option', { value: k, selected: c.operator === k }, l))),
            values ? h('select', { 'aria-label': 'Value', onchange: (e) => { c.value = e.target.value; } }, h('option', { value: '' }, 'Choose'), values.map((v) => h('option', { value: v, selected: c.value === v }, v)))
              : h('input', { type: 'text', 'aria-label': 'Value', value: c.value, oninput: (e) => { c.value = e.target.value; } }),
            h('button', { class: 'icon-btn', 'aria-label': 'Remove condition', onclick: () => { r.conditions.splice(j, 1); draw(); } }, icon('x', 14)));
        }),
        h('button', { class: 'btn small', onclick: () => { r.conditions.push({ fact: d.facts[0]?.name || '', operator: 'eq', value: '' }); draw(); } }, 'Add a condition'),
        h('div', { class: 'row', style: 'margin-top:10px' }, field('Then the outcome is', h('input', { type: 'text', value: r.outcome, placeholder: 'e.g. FOLLOW_INVESTIGATION_SOP', oninput: (e) => { r.outcome = e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, '_'); e.target.value = r.outcome; } })),
          field('Because of source clause', h('select', { onchange: (e) => { r.clause_index = Number(e.target.value); } }, d.clauses.map((c, k) => h('option', { value: k, selected: r.clause_index === k }, `Clause ${k + 1}: ${c.preview.slice(0, 50)}…`))))),
        h('button', { class: 'btn danger small', onclick: () => { d.rules.splice(i, 1); draw(); } }, 'Remove rule'))));
      draw();
      return [h('p', { class: 'hint', style: 'margin-top:0' }, 'Each rule says: when these facts hold, this is the outcome. Outcomes are labels for people, such as FOLLOW_INVESTIGATION_SOP. They never authorise a payment.'),
        rows, h('button', { class: 'btn', id: 'add-rule', onclick: () => { d.rules.push({ id: `rule-${d.rules.length + 1}`, match: 'all', conditions: [{ fact: d.facts[0]?.name || '', operator: 'eq', value: '' }], outcome: '', clause_index: 0 }); draw(); } }, 'Add a rule'),
        h('div', { class: 'field', style: 'margin-top:16px' }, h('label', {}, 'If no rule matches, the outcome is'), h('input', { type: 'text', id: 'default-outcome', value: d.default_outcome, placeholder: 'e.g. ESCALATE', oninput: (e) => { d.default_outcome = e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, '_'); e.target.value = d.default_outcome; } }))];
    }

    function review() {
      const list = h('ul', { class: 'summary' }, policySentences({ ...d, required_facts: d.facts }).map((s) => h('li', {}, s)));
      const out = h('div');
      api('/policies/validate', { method: 'POST', body: d }).then((r) => { problems = r.problems; clear(out).append(r.ok ? h('p', { class: 'verified' }, icon('check', 14), 'Ready to register.') : h('ul', { class: 'problems', id: 'problems' }, r.problems.map((p) => h('li', {}, p.message)))); });
      return [h('p', { class: 'hint', style: 'margin-top:0' }, 'This is exactly what Palladion will apply. Read it as a colleague would.'), list, d.clauses.length ? h('p', { class: 'hint' }, `Based on ${d.clauses.length} approved source clause${d.clauses.length === 1 ? '' : 's'}.`) : null, out];
    }

    async function register(event) {
      event.target.disabled = true;
      try {
        const r = await api('/policies', { method: 'POST', body: d });
        toast(`${r.version_id} registered`); clear(wizardHost); await refresh();
      } catch (error) {
        event.target.disabled = false;
        const list = error.data?.error?.problems;
        if (list) { step = STEPS.length - 1; redraw(); } else toast(error.message, 'error');
      }
    }
    redraw();
    return root;
  }

  page.append(h('div', { style: 'display:flex;justify-content:space-between;align-items:flex-start;gap:12px' }, h('div', {}, h('h1', {}, 'Policies'),
    h('p', { class: 'lead' }, `Rules that Palladion applies in plain code for ${S.caseId}, each tied to approved source text. The agent can run a policy but never write or change one.`)),
  h('button', { class: 'btn primary', id: 'new-policy', onclick: () => clear(wizardHost).append(wizard()) }, icon('plus', 14), ' New policy')), wizardHost, listHost);
  await refresh();
}
