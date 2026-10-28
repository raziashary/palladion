import { api, qs } from './api.js';
import { renderChat } from './chat.js';
import { $, clear, h, icon, popup, toast } from './dom.js';
import { openEvidence, renderPanel } from './evidence.js';
import { ago } from './format.js';
import { renderIngest } from './ingest.js';
import { renderPolicies } from './policies.js';
import { openModelMenu, refreshRuntime, runtimeChip } from './runtime.js';
import { renderSearch } from './search.js';
import { S, emit, onChange, persona, recall, remember } from './state.js';

const route = () => {
  const [, view = 'chat', id = null] = location.hash.split('/');
  return { view: ['chat', 'search', 'ingest', 'policies'].includes(view) ? view : 'chat', id };
};

export async function loadSessions() {
  if (!S.caseId) { S.sessions = []; return; }
  try { S.sessions = (await api('/sessions' + qs({ case_id: S.caseId }))).sessions; } catch { S.sessions = []; }
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  remember('theme', theme);
}

// Sidebar ------------------------------------------------------------------------------------------------------------

function navItem(view, label, glyph) {
  const current = route();
  return h('a', { class: `nav-item ${current.view === view && !(view === 'chat' && current.id) ? 'active' : ''}`, href: `#/${view}` }, icon(glyph), label);
}

function renderSidebar() {
  const side = clear($('#sidebar'));
  const me = persona();
  const current = route();
  side.append(
    h('div', { class: 'brand' }, h('span', { class: 'logo' }, icon('shield', 14)), 'Palladion'),
    h('a', { class: `nav-item ${current.view === 'chat' && !current.id ? 'active' : ''}`, href: '#/chat', id: 'new-session' }, icon('plus'), 'New session'),
    navItem('search', 'Search documents', 'search'),
    navItem('ingest', 'Ingestion', 'upload'),
    navItem('policies', 'Policies', 'book'),
    h('div', { class: 'nav-sep' }),
    h('div', { class: 'nav-title' }, h('span', {}, S.caseId ? `Sessions · ${S.caseId}` : 'Sessions')),
    h('div', { class: 'sessions' }, S.sessions.length
      ? S.sessions.map((s) => h('a', { class: `session ${s.id === S.sessionId ? 'active' : ''}`, href: `#/chat/${s.id}`, title: s.title },
        s.title, h('small', {}, `${ago(s.updated_at)} · ${s.message_count} message${s.message_count === 1 ? '' : 's'}`)))
      : h('div', { class: 'hint', style: 'padding:6px 14px' }, 'No sessions yet. Ask a question to start one.')),
    h('div', { class: 'sidebar-foot' },
      h('button', { class: 'who', id: 'persona-btn', 'aria-label': 'Switch identity', onclick: (e) => personaMenu(e.currentTarget) },
        h('span', { class: 'avatar' }, me.id[0].toUpperCase()), h('span', { style: 'min-width:0' }, h('b', {}, me.id), h('small', {}, me.roles.join(', ')))),
      h('button', { class: 'icon-btn', title: 'Toggle light and dark', 'aria-label': 'Toggle theme', onclick: () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark') }, icon('sun'))),
  );
}

function personaMenu(anchor) {
  const { close } = popup(anchor, [
    h('div', { class: 'note' }, 'Acting as a demo identity. Palladion decides what each one may see and do.'),
    ...S.boot.personas.map((p) => h('button', { class: 'item', role: 'menuitemradio', 'aria-checked': String(p.id === persona().id), onclick: async () => {
      close();
      await api('/persona', { method: 'POST', body: { persona: p.id } });
      await boot(true);
    } }, h('span', { class: 'avatar', style: 'width:22px;height:22px;font-size:11px' }, p.id[0].toUpperCase()),
    h('span', {}, p.id, h('small', {}, `${p.roles.join(', ')} · ${p.tenant_id}${p.can_approve ? ' · can approve' : p.can_upload ? ' · can upload' : ''}`)))),
  ], { above: true });
}

// Top bar -----------------------------------------------------------------------------------------------------------

const TITLES = { chat: 'Chat', search: 'Search documents', ingest: 'Ingestion', policies: 'Policies' };

function renderTopbar() {
  const bar = clear($('#topbar'));
  const { view, id } = route();
  const chip = runtimeChip();
  const session = S.sessions.find((s) => s.id === id);
  bar.append(
    h('button', { class: 'icon-btn', title: 'Show or hide the sidebar', 'aria-label': 'Toggle sidebar', onclick: () => { S.sidebarOpen = !S.sidebarOpen; applyLayout(); } }, icon('sidebar')),
    h('div', { class: 'title' }, view === 'chat' && session ? session.title : TITLES[view]),
    S.boot.cases.length > 1 ? h('select', { 'aria-label': 'Case', onchange: async (e) => { S.caseId = e.target.value; remember('case', S.caseId); S.sessionId = null; await loadSessions(); location.hash = '#/chat'; emit(); } },
      S.boot.cases.map((c) => h('option', { value: c.id, selected: c.id === S.caseId }, `${c.id} · ${c.transaction_id}`))) : h('span', { class: 'chip' }, S.caseId || 'No case'),
    h('button', { class: `chip ${chip.tone}`, id: 'runtime-chip', title: 'Choose the model', onclick: (e) => openModelMenu(e.currentTarget, false) },
      chip.spin ? h('span', { class: 'spinner' }) : h('span', { class: 'dot' }), chip.text),
    h('button', { class: 'icon-btn', title: 'Show or hide evidence', 'aria-label': 'Toggle evidence panel', onclick: () => { S.panelOpen = !S.panelOpen; applyLayout(); } }, icon('panel')));
}

function applyLayout() {
  $('#app').classList.toggle('no-sidebar', !S.sidebarOpen);
  $('#app').classList.toggle('no-panel', !S.panelOpen);
}

// Router ------------------------------------------------------------------------------------------------------------

let disposeView = null;

async function renderRoute() {
  const { view, id } = route();
  if (view === 'chat') S.sessionId = id;
  renderSidebar();
  renderTopbar();
  disposeView?.();
  const host = clear($('#view'));
  const draw = { chat: renderChat, search: renderSearch, ingest: renderIngest, policies: renderPolicies }[view];
  disposeView = (await draw(host, { id })) || null;
  renderPanel($('#panel'));
}

async function boot(reload = false) {
  const as = new URLSearchParams(location.search).get('as'); // deep link: ?as=admin-a signs in as that demo identity
  if (as && !reload) await api('/persona', { method: 'POST', body: { persona: as } }).catch(() => null);
  S.boot = await api('/bootstrap');
  if (!S.boot.cases.some((c) => c.id === S.caseId)) {
    const saved = recall('case');
    S.caseId = S.boot.cases.find((c) => c.id === saved)?.id || S.boot.cases[0]?.id || null;
  }
  await loadSessions();
  if (reload) { S.evidence = null; S.run = null; location.hash = '#/chat'; }
  await renderRoute();
  applyLayout();
  const open = new URLSearchParams(location.search).get('open'); // deep link: ?open=<evidence id> shows it in the panel
  if (open) await openEvidence(open);
}

onChange(() => { if (S.boot) { renderTopbar(); renderSidebar(); renderPanel($('#panel')); } });
window.addEventListener('hashchange', () => { if (S.boot) renderRoute(); });

setTheme(recall('theme') || 'dark');
boot().then(refreshRuntime).catch((error) => {
  clear($('#view')).append(h('div', { class: 'empty' }, h('h1', {}, 'Palladion UI could not start'), h('p', { class: 'lead' }, error.message)));
  toast(error.message, 'error');
});
