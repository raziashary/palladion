import { api } from './api.js';
import { clear, h, icon, toast } from './dom.js';
import { settingsHelp } from './help.js';
import { S, emit } from './state.js';

const DEFAULTS = { rerank: true, critic: true, memory: true, critic_searches: 2, tool_budget: 8, persistent_search: true };
const CHIP = { on: ['On', 'green'], off: ['Off', 'gray'], locked: ['Always on', 'blue'], unavailable: ['Not available here', 'gray'] };
const CRITIC_WARNING = 'Turning the independent critic off puts Palladion in its measurement mode, which it says is not a serving mode.\n\n'
  + 'The final gate still runs, but it cannot see a review, so it will withhold policy-based and operational claims. '
  + 'Every answer will be marked as made in experiment mode.\n\nTurn it off?';

async function waitUntilSettled() {
  for (let i = 0; i < 90; i++) {
    S.boot.runtime = await api('/runtime');
    emit();
    if (S.boot.runtime.state !== 'starting') return S.boot.runtime;
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
  return S.boot.runtime;
}

export async function renderSettings(host) {
  let power = await api('/power');
  let draft = { ...power.options };
  const page = h('div', { class: 'page', id: 'settings-page' });
  const body = h('div');
  const bar = h('div', { class: 'applybar', hidden: true });
  host.append(h('div', { class: 'scroll' }, page), bar);

  const dirty = () => JSON.stringify(draft) !== JSON.stringify(power.options);
  const hasModel = () => Boolean(power.model);

  function toggle(item) {
    const on = draft[item.key];
    const blocked = item.id === 'critic' && !hasModel();
    return h('button', { class: `switch ${on ? 'on' : ''}`, role: 'switch', 'aria-checked': String(on), 'aria-label': item.label, id: `sw-${item.id}`,
      disabled: blocked, title: blocked ? 'Needs a model: start one from the top bar first' : null,
      onclick: () => {
        if (item.id === 'critic' && on && !confirm(CRITIC_WARNING)) return;
        draft[item.key] = !on; draw();
      } }, h('i'));
  }

  function number(item) {
    const set = (delta) => { draft[item.key] = Math.min(item.max, Math.max(item.min, draft[item.key] + delta)); draw(); };
    return h('div', { class: 'num', id: `num-${item.id}` },
      h('button', { class: 'btn small', 'aria-label': `Less ${item.label}`, disabled: draft[item.key] <= item.min, onclick: () => set(-1) }, '−'),
      h('b', {}, draft[item.key]),
      h('button', { class: 'btn small', 'aria-label': `More ${item.label}`, disabled: draft[item.key] >= item.max, onclick: () => set(1) }, '+'));
  }

  function row(item) {
    const [label, tone] = CHIP[item.state] || ['', 'gray'];
    const changed = item.key && draft[item.key] !== power.options[item.key];
    const lowered = item.key && draft[item.key] !== DEFAULTS[item.key];
    return h('div', { class: `setrow ${item.state}`, 'data-id': item.id },
      h('div', { class: 'setmain' },
        h('div', { class: 'settitle' }, item.state === 'locked' ? icon('lock', 14) : null, item.label, h('span', { class: `chip ${tone}` }, label),
          item.experiment ? h('span', { class: 'chip amber' }, 'Experiment mode when off') : null, changed ? h('span', { class: 'chip accent' }, 'Changed, not applied') : null),
        h('p', { class: 'hint' }, item.detail),
        item.effect ? h('p', { class: `setfx ${lowered ? 'on' : ''}` }, item.effect) : null),
      item.control === 'toggle' ? toggle(item) : item.control === 'number' ? number(item) : null);
  }

  function draw() {
    const running = S.boot.runtime?.state === 'starting';
    clear(body).append(...[
      power.full
        ? h('div', { class: 'card powerbanner', id: 'power-banner' }, h('span', { class: 'badge green' }, h('span', { class: 'dot' }), 'Full power'),
          h('span', {}, 'Every optional part of Palladion is on. The parts that guard authority are always on.'))
        : h('div', { class: 'card powerbanner reduced', id: 'power-banner' }, h('span', { class: 'badge amber' }, h('span', { class: 'dot' }), 'Reduced power'),
          h('span', { style: 'flex:1' }, power.reductions.join(', ') + '. Answers made this way are flagged.'),
          h('button', { class: 'btn small', id: 'reset-power', onclick: () => { draft = { ...DEFAULTS }; draw(); apply(); } }, 'Reset to full power')),
      running ? h('p', { class: 'hint' }, h('span', { class: 'spinner' }), ' Palladion is restarting…') : null,
      ...power.groups.map((g) => h('section', { class: `setgroup ${g.id}` },
        h('h2', {}, g.title), g.id === 'locked' ? h('p', { class: 'hint', style: 'margin-top:0' }, 'Palladion deliberately has no way to turn these off, so this screen has none either.') : null,
        h('div', { class: 'setlist' }, g.items.map(row))))].filter(Boolean));
    bar.hidden = !dirty();
    clear(bar).append(h('span', {}, 'You have unapplied changes. Applying restarts Palladion (about 10 to 20 seconds).'),
      h('button', { class: 'btn', onclick: () => { draft = { ...power.options }; draw(); } }, 'Discard'),
      h('button', { class: 'btn primary', id: 'apply-power', onclick: apply }, 'Apply changes'));
  }

  async function apply() {
    bar.hidden = true;
    try {
      S.boot.runtime = await api('/runtime/options', { method: 'POST', body: draft });
      toast('Restarting Palladion with your settings…');
      draw();
      const settled = await waitUntilSettled();
      power = await api('/power');
      draft = { ...power.options };
      draw();
      if (settled.state === 'ready') toast('Settings applied'); else toast(settled.error || 'Palladion did not restart cleanly', 'error');
    } catch (error) {
      toast(error.message, 'error'); draw();
    }
  }

  page.append(h('h1', {}, 'Settings'),
    h('p', { class: 'lead' }, 'Palladion’s power: what it does to find and check evidence, what you can turn down, and what each choice costs.'),
    settingsHelp(), body);
  draw();
}
