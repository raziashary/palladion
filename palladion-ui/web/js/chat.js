import { ApiError, api, qs, streamChat } from './api.js';
import { loadSessions } from './app.js';
import { $, clear, h, icon, toast } from './dom.js';
import { openEvidence } from './evidence.js';
import { KIND_LABEL, citationTitle, disposition, evidenceKind, failureText, fmtTime, gap, partsOf, toneOf } from './format.js';
import { chatHelp } from './help.js';
import { openModelMenu, runtimeChip } from './runtime.js';
import { S, emit, modelLabel } from './state.js';

const SUGGESTIONS = [
  'What does our procedure say when a customer reports a debit but the merchant has not confirmed receipt?',
  'Can I reverse this payment?',
  'Which procedure applies to a transaction from June 2025?',
  'What is our procedure for ATM cash withdrawal disputes?',
];

// One assistant answer. It is filled in piece by piece while streaming, or all at once for a saved conversation.
function answerView() {
  const root = h('div', { class: 'msg assistant' });
  const steps = h('details', { class: 'steps', open: true });
  const stepList = h('ol');
  const label = h('span', {}, 'Working…');
  steps.append(h('summary', {}, h('span', { class: 'spinner' }), label), stepList);
  const card = h('div', { class: 'card', hidden: true });
  const verdict = h('div', { class: 'verdict' });
  card.append(verdict);
  root.append(steps, card);
  const sections = {};
  const text = {};
  const numbers = new Map();
  const log = { verdict: '', claimIds: [], gaps: [], evidence: [] };
  let count = 0;

  const number = (id) => { if (!numbers.has(id)) numbers.set(id, ++count); return numbers.get(id); };
  const section = (key, title, content) => {
    if (!sections[key]) { sections[key] = h('div', { class: 'sect' }, h('h3', {}, title), content); card.append(sections[key]); }
    return sections[key];
  };
  const textNode = (id, el) => { const node = document.createTextNode(''); el.append(node); text[id] = node; el.classList.add('caret'); return node; };

  async function copySummary() {
    const lines = [`Palladion answer for ${S.caseId}: ${log.verdict}`, text.answer?.data || '', '', 'Verified:',
      ...log.claimIds.map((id) => `- ${text[id]?.data}`), '', 'Still needed before anyone acts:', ...log.gaps.map((g) => `- ${g}`),
      '', 'Evidence: ' + (log.evidence.join('; ') || 'none'), 'Decision support only. Not an authorisation to move money.'];
    try { await navigator.clipboard.writeText(lines.join(String.fromCharCode(10))); toast('Summary copied. Paste it into your own review process.'); }
    catch { toast('Copying is blocked in this browser.', 'error'); }
  }

  function refs(ids) {
    return h('span', { class: 'refs' }, ids.map((id) => h('button', { class: 'ref', title: `Open evidence ${id}`, onclick: () => openEvidence(id) }, `E${number(id)}`)));
  }

  function part(p) {
    card.hidden = false;
    if (p.type === 'disposition') {
      const d = disposition(p.value);
      log.verdict = d.label;
      verdict.append(h('span', { class: `badge ${d.tone}` }, h('span', { class: 'dot' }), d.label),
        p.review_status === 'PASS' ? h('span', { class: 'chip green' }, 'Independently reviewed') : p.review_status ? h('span', { class: 'chip amber' }, `Review: ${String(p.review_status).toLowerCase()}`) : null,
        h('span', { class: 'hint' }, d.help));
    } else if (p.type === 'answer') {
      const el = h('p', { class: 'answer' }); card.append(el); textNode(p.id, el); if (p.text) text[p.id].data = p.text;
    } else if (p.type === 'claim') {
      const body = section('claims', 'What is verified', h('ul', { class: 'claims' })).querySelector('ul');
      const span = h('span');
      body.append(h('li', { class: 'claim' }, h('span', { class: 'n' }, icon('check', 12)), h('div', {}, span, refs(p.evidence_ids || []))));
      textNode(p.id, span); if (p.text) text[p.id].data = p.text;
      log.claimIds.push(p.id);
    } else if (p.type === 'hypothesis') {
      const el = h('div', { class: 'hyp' }, h('b', {}, 'Unverified'));
      const span = h('span'); el.append(span);
      section('hyp', 'A possibility, not a finding', h('div')).querySelector('div').append(el);
      textNode(p.id, span); if (p.text) text[p.id].data = p.text;
    } else if (p.type === 'gap') {
      const g = gap(p.value, p.origin);
      section('gaps', 'Before anyone acts', h('div', { class: 'gaps' })).querySelector('.gaps').append(
        h('div', { class: 'gap' }, h('span', { class: 'box' }), h('div', { style: 'flex:1' }, g.title, g.detail ? h('small', {}, g.detail) : null),
          p.value === 'authorized_human_review' ? h('button', { class: 'btn small', title: 'Palladion names no approver; use your own process', onclick: copySummary }, 'Copy summary for reviewer') : null));
      log.gaps.push(g.title);
    } else if (p.type === 'citation') {
      const c = p.citation;
      section('evidence', 'Evidence', h('div', { class: 'evlist' })).querySelector('.evlist').append(
        h('button', { class: 'evcard', onclick: () => openEvidence(c.evidence_id, c.kind) }, h('b', { class: 'mono' }, `E${number(c.evidence_id)}`),
          h('span', {}, citationTitle(c), h('small', {}, ' ' + (KIND_LABEL[evidenceKind(c.evidence_id, c.kind)] || '')),
            c.observed_at ? h('small', { style: 'display:block' }, `read ${fmtTime(c.observed_at)}${c.data_as_of ? ' · data as of ' + fmtTime(c.data_as_of) : ''}`) : null),
          c.status ? h('span', { class: `chip ${toneOf(c.status)}` }, c.status) : null));
      log.evidence.push(`E${number(c.evidence_id)} ${citationTitle(c)}`);
    } else if (p.type === 'meta') {
      const foot = h('div', { class: 'foot' });
      for (const [k, v] of Object.entries(p.tool_status || {})) foot.append(h('span', { class: `chip ${toneOf(v)}` }, `${k.replace(/_/g, ' ')}: ${v}`));
      if ((p.verification_failures || []).length) card.append(h('div', { class: 'gap', style: 'margin-top:12px' }, h('span', { class: 'box' }),
        h('div', {}, p.verification_failures.map(failureText).join('; '), h('small', {}, 'Facts that depend on it are unverified. That is not the same as “no data”.'))));
      card.append(foot, h('div', { class: 'scope-note' }, p.searched_scope || '', ' Palladion cannot tell whether every company document was supplied.'));
    }
  }

  return {
    el: root,
    step(s) { stepList.append(h('li', {}, s.label, s.detail ? h('span', { class: 'hint' }, ` · ${s.detail}`) : null)); },
    tick(seconds) { label.textContent = `Working… ${seconds.toFixed(0)} s`; },
    part,
    delta(d) { if (text[d.id]) text[d.id].data += d.text; },
    search(result, elapsed) {
      card.hidden = false; card.append(h('div', { class: 'verdict' }, h('span', { class: 'badge blue' }, 'Search only'),
        h('span', { class: 'hint' }, 'No model was used. These are the passages Palladion would give the agent, each re-checked against its original file.')));
      const passages = h('div', { class: 'passages', style: 'margin-top:12px' });
      for (const p of result.passages || []) passages.append(h('button', { class: 'passage', onclick: () => openEvidence(p.citation_id) },
        h('div', { class: 'path mono' }, String(p.section_id).split('/').pop()), h('p', {}, p.text.replace(/\s+/g, ' '))));
      if (!(result.passages || []).length) passages.append(h('p', { class: 'hint' }, 'Nothing in the searched sources matched. That does not mean no such document exists.'));
      card.append(passages, h('div', { class: 'foot' }, h('span', { class: 'chip' }, `${(result.passages || []).length} passages`),
        h('span', { class: 'chip' }, `${result.excluded?.NOT_ELIGIBLE ?? 0} excluded as not eligible`), elapsed ? h('span', { class: 'chip' }, `${elapsed} s`) : null));
    },
    error(message) { card.hidden = false; card.classList.add('errorcard'); card.append(h('p', { style: 'margin:0' }, message)); },
    finish(elapsed) {
      Object.values(text).forEach((n) => n.parentElement?.classList.remove('caret'));
      stepList.children.length ? (label.textContent = `Worked for ${Number(elapsed || 0).toFixed(0)} s · ${stepList.children.length} step${stepList.children.length === 1 ? '' : 's'}`) : steps.remove();
      steps.querySelector('.spinner')?.remove(); steps.open = false;
    },
    full(response, meta) { partsOf(response).forEach(part); this.finish(meta?.elapsed); steps.remove(); },
  };
}

export async function renderChat(host, { id }) {
  let messages = [];
  if (id) {
    try { messages = (await api(`/sessions/${id}`)).messages; } catch (error) { toast(error.message, 'error'); location.hash = '#/chat'; return; }
    S.sessionId = id;
    const last = [...messages].reverse().find((m) => m.kind === 'agent');
    S.run = last ? { response: last.response, model: last.model, elapsed: last.elapsed } : null;
  } else { S.run = null; S.sessionId = null; }

  const thread = h('div', { class: 'thread' });
  const scroll = h('div', { class: 'scroll' }, thread);
  const input = h('textarea', { rows: 1, placeholder: 'Ask about a case, a procedure or a policy…', 'aria-label': 'Your question' });
  const send = h('button', { class: 'send', title: 'Send', 'aria-label': 'Send', disabled: true }, icon('send', 15));
  const modelBtn = h('button', { class: 'pill', id: 'model-pill', title: 'Choose the model', onclick: (e) => openModelMenu(e.currentTarget, true) });
  const refreshModel = () => { const c = runtimeChip(); clear(modelBtn).append(icon('cpu', 14), c.text, icon('chevron', 12)); };
  refreshModel();
  let controller = null;

  const toBottom = () => { scroll.scrollTop = scroll.scrollHeight; };
  const paint = (m) => {
    if (m.role === 'user') return thread.append(h('div', { class: 'msg user' }, m.text));
    const view = answerView();
    if (m.kind === 'agent') view.full(m.response, m);
    else if (m.kind === 'search') view.search(m.result, m.elapsed);
    else view.error(m.error?.message || 'This turn failed.');
    thread.append(view.el);
  };
  const empty = () => h('div', { class: 'empty' }, h('div', { class: 'logo' }, icon('shield', 24)), h('h1', {}, 'What would you like to check?'),
    h('p', { class: 'lead' }, 'Answers come with the evidence behind each claim, and say plainly what could not be verified.'),
    h('div', { class: 'suggestions' }, SUGGESTIONS.map((q) => h('button', { onclick: () => { input.value = q; input.focus(); sync(); } }, q))));
  thread.append(chatHelp(messages.length > 0));
  if (messages.length) messages.forEach(paint); else thread.append(empty());

  async function ask(question) {
    if (S.busy || !question.trim() || !S.caseId) return;
    S.busy = true; sync();
    thread.querySelector('.empty')?.remove();
    thread.append(h('div', { class: 'msg user' }, question));
    const view = answerView();
    thread.append(view.el); toBottom();
    let elapsed = 0;
    const meta = { response: null };
    controller = new AbortController();
    try {
      await streamChat({ case_id: S.caseId, session_id: S.sessionId, query: question }, (name, data) => {
        if (name === 'start') {
          S.sessionId = data.session_id; meta.model = data.model;
          history.replaceState(null, '', `#/chat/${data.session_id}`); document.getElementById('new-session')?.classList.remove('active');
        } else if (name === 'progress') view.step(data);
        else if (name === 'tick') view.tick(data.elapsed);
        else if (name === 'part') { view.part(data); if (data.type === 'meta') { meta.response = { ...meta.response, ...data, disposition: meta.disposition }; } if (data.type === 'disposition') meta.disposition = data.value; }
        else if (name === 'delta') view.delta(data);
        else if (name === 'search') view.search(data, elapsed);
        else if (name === 'error') view.error(data.message);
        else if (name === 'done') elapsed = data.elapsed;
        toBottom();
      }, controller.signal);
    } catch (error) {
      if (error.name !== 'AbortError') { view.error(error instanceof ApiError ? error.message : 'The connection was interrupted.'); }
      else view.error('Stopped. Palladion may still finish this request on its side.');
    } finally {
      view.finish(elapsed);
      if (meta.response) { S.run = { response: meta.response, model: meta.model, elapsed }; S.panelTab = S.panelTab; }
      S.busy = false; controller = null; sync();
      await loadSessions(); emit(); toBottom();
    }
  }

  function sync() {
    send.disabled = !S.busy && !input.value.trim();
    send.classList.toggle('stop', S.busy);
    clear(send).append(icon(S.busy ? 'stop' : 'send', 15));
    send.title = send.ariaLabel = S.busy ? 'Stop' : 'Send';
    input.disabled = S.busy && false;
    input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 200) + 'px';
    refreshModel();
  }
  input.addEventListener('input', sync);
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); const q = input.value; if (!S.busy) { input.value = ''; ask(q); } } });
  send.addEventListener('click', () => { if (S.busy) { controller?.abort(); return; } const q = input.value; input.value = ''; ask(q); });

  const composer = h('div', { class: 'composer-wrap' },
    h('div', { class: 'composer' }, input,
      h('div', { class: 'composer-row' }, h('span', { class: 'pill', title: 'The agent has four read tools and no way to change anything.' }, icon('lock', 14), 'Read-only agent'),
        modelBtn, h('span', { class: 'spacer' }), send)),
    h('div', { class: 'disclaimer' }, 'Synthetic data only. Answers are decision support, never authorisation to move money.'));
  host.append(scroll, composer);
  sync(); toBottom();
  if (!S.caseId) thread.append(h('div', { class: 'card errorcard' }, 'This identity is not a member of any case.'));
  setTimeout(() => input.focus());
  const stop = () => controller?.abort();
  return stop;
}
