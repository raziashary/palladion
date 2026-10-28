// Tiny DOM helpers. Everything is built with textContent, never innerHTML, because document text is untrusted.
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === false || value == null) continue;
    if (key === 'class') el.className = value;
    else if (key.startsWith('on')) el.addEventListener(key.slice(2), value);
    else if (key === 'value') el.value = value;
    else if (value === true) el.setAttribute(key, '');
    else el.setAttribute(key, value);
  }
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    el.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return el;
}

export const $ = (selector, root = document) => root.querySelector(selector);
export const clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); return el; };

const PATHS = {
  plus: 'M12 5v14M5 12h14', search: 'M11 4a7 7 0 105 12l4 4M11 4a7 7 0 010 14', upload: 'M12 16V4m0 0L7 9m5-5l5 5M5 20h14',
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z', book: 'M5 4h11a3 3 0 013 3v13H8a3 3 0 01-3-3zM5 17a3 3 0 013-3h11',
  sidebar: 'M4 5h16v14H4zM9 5v14', panel: 'M4 5h16v14H4zM15 5v14', send: 'M5 12l14-7-5 14-3-6z', stop: 'M7 7h10v10H7z',
  sun: 'M12 8a4 4 0 100 8 4 4 0 000-8M12 2v2M12 20v2M2 12h2M20 12h2', moon: 'M20 14a8 8 0 01-10-10 8 8 0 1010 10z',
  chevron: 'M6 9l6 6 6-6', check: 'M5 13l4 4L19 7', doc: 'M7 3h7l5 5v13H7zM14 3v5h5', file: 'M7 3h7l5 5v13H7z',
  bolt: 'M13 3L5 14h6l-1 7 8-11h-6z', lock: 'M6 11h12v9H6zM9 11V8a3 3 0 016 0v3', x: 'M6 6l12 12M18 6L6 18',
  clock: 'M12 7v5l3 2M12 3a9 9 0 100 18 9 9 0 000-18', cpu: 'M8 8h8v8H8zM4 10h2M4 14h2M18 10h2M18 14h2M10 4v2M14 4v2M10 18v2M14 18v2',
};
export function icon(name, size = 16) {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('width', size); svg.setAttribute('height', size);
  svg.setAttribute('fill', 'none'); svg.setAttribute('stroke', 'currentColor'); svg.setAttribute('stroke-width', '1.8');
  svg.setAttribute('stroke-linecap', 'round'); svg.setAttribute('stroke-linejoin', 'round'); svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS(ns, 'path'); path.setAttribute('d', PATHS[name] || PATHS.doc); svg.append(path);
  return svg;
}

export function toast(message, kind = '') {
  const el = h('div', { class: `toast ${kind}` }, message);
  document.getElementById('toasts').append(el);
  setTimeout(() => el.remove(), kind === 'error' ? 7000 : 3500);
}

// A small popup menu anchored to a button; closes on the next click anywhere else.
export function popup(anchor, content, { above = false, align = 'left' } = {}) {
  const menu = h('div', { class: 'menu', role: 'menu' }, content);
  const box = anchor.getBoundingClientRect();
  menu.style.position = 'fixed';
  menu.style[above ? 'bottom' : 'top'] = (above ? innerHeight - box.top + 6 : box.bottom + 6) + 'px';
  menu.style[align === 'right' ? 'right' : 'left'] = (align === 'right' ? innerWidth - box.right : box.left) + 'px';
  document.body.append(menu);
  const close = () => { menu.remove(); document.removeEventListener('mousedown', outside, true); document.removeEventListener('keydown', esc); };
  const outside = (e) => { if (!menu.contains(e.target)) close(); };
  const esc = (e) => { if (e.key === 'Escape') close(); };
  setTimeout(() => { document.addEventListener('mousedown', outside, true); document.addEventListener('keydown', esc); });
  return { menu, close };
}
