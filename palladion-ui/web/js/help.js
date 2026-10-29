// "How to" guides, one per screen. Open the first time, then remember if the person closed them.
import { h } from './dom.js';
import { policySentences } from './format.js';
import { recall, remember } from './state.js';

export function howTo(key, title, body, { open: openByDefault = true } = {}) {
  const open = (recall(`help.${key}`) || (openByDefault ? 'open' : 'closed')) !== 'closed';
  return h('details', { class: 'howto', id: `howto-${key}`, open, ontoggle: (e) => remember(`help.${key}`, e.target.open ? 'open' : 'closed') },
    h('summary', {}, h('b', {}, title)), h('div', { class: 'howto-body' }, body));
}

export const steps = (items) => h('ol', { class: 'howto-steps' }, items.map((i) => h('li', {}, i)));
export const terms = (pairs) => h('dl', { class: 'howto-terms' }, pairs.flatMap(([term, text]) => [h('dt', {}, term), h('dd', {}, text)]));
const para = (text) => h('p', { class: 'howto-p' }, text);
const badge = (tone, text) => h('span', { class: `badge ${tone}` }, text);

export function chatHelp(hasMessages) {
  return howTo('chat', 'How to read an answer', [
    para('An answer is not a paragraph to trust. It is a verdict, the claims behind it, and the evidence for each claim.'),
    terms([
      ['The badge', h('span', {}, badge('green', 'Supported'), ' everything stated is verified. ', badge('amber', 'Partly supported'),
        ' some facts are verified, so do not act on it alone. ', badge('red', 'Conflict'), ' approved sources disagree. ',
        badge('gray', 'Not established'), ' the searched documents do not say. ', badge('red', 'Could not verify'), ' a required check failed.')],
      ['What is verified', 'Each line passed Palladion’s checks against the original evidence. The blue chips (E1, E2) open that evidence in the side panel: select one to read the exact text, the time a reading was taken, or the policy decision.'],
      ['Before anyone acts', 'A checklist of what is still missing. A question about doing something (for example a reversal) always ends with “needs authorised human review”. Use “Copy summary for reviewer” to hand it on.'],
      ['A possibility, not a finding', 'An idea the system could not verify. Never treat it as a fact.'],
      ['Evidence cards', 'Documents show their exact words; live readings show the system and when it was read (readings go stale); policy decisions show which version applied and why.'],
      ['Orange and red notes', 'A system timed out or a check could not run. That is not the same as “no data”: the facts that depend on it are unverified.'],
      ['The grey note at the end', 'Only the documents supplied to Palladion were searched. “Not found” never means “does not exist”.'],
    ]),
    para('No answer here moves money or changes an account. It is decision support.'),
  ], { open: !hasMessages });
}

export function ingestHelp() {
  return howTo('ingest', 'How to add a document', [
    steps([
      'Sign in as an uploader (bottom left). Only uploaders can add documents.',
      'Drop files on the box, choose them, or paste text. Markdown, text, JSON, CSV, code and digital PDFs work (text up to 65,536 characters, PDFs up to 2 MB).',
      'Check the name and dates for each file. The name is its identity: a new file with the same name becomes a new version. “Applies from” and “Until” say when it counts; leave “Until” empty for no end.',
      'Press Upload. The file is now a draft: nobody can search it or cite it yet.',
      'A different person approves it. Press “Switch to admin-a to approve”, then Approve. If it replaces an older version, pick that version in the box beside the button.',
      'When the card shows “Searchable”, the document appears in search and in answers. Revoke removes it at once.',
    ]),
    terms([
      ['Why two people?', 'So nobody can approve their own upload. Words like “approved” or “official policy” inside a document mean nothing; only the approval record counts.'],
      ['Draft, approved, revoked', 'A draft is invisible. Approved and searchable is live. Revoked is gone from search and answers immediately, and the record is kept.'],
    ]),
  ]);
}

const EXAMPLE = {
  family_id: 'REVERSAL.CHECK', version_id: 'REVERSAL.CHECK-v1', time_basis: 'TRANSACTION_OCCURRED_AT', valid_from: '2026-07-01', valid_to: '',
  required_facts: [{ name: 'transaction_state', max_age_seconds: 300 }, { name: 'settlement_state', max_age_seconds: 300 }],
  rules: [{ outcome: 'FOLLOW_INVESTIGATION_SOP', match: 'all', conditions: [{ fact: 'transaction_state', operator: 'eq', value: 'FAILED' }, { fact: 'settlement_state', operator: 'eq', value: 'UNSETTLED' }] }],
  default_outcome: 'NO_DECISION_REQUIRES_REVIEW',
};

export function policyHelp() {
  return howTo('policy', 'What a policy is, and how to make one', [
    para('A policy is a rule Palladion applies in plain code, with no AI, to one case. It is always based on exact text from an approved document. The agent can run a policy and quote its result, but it can never write or change one, and it can never invent a fact for it.'),
    h('div', { class: 'example' },
      h('b', {}, 'Worked example'),
      h('p', { class: 'howto-p' }, 'The approved procedure says: “A reversal review may proceed only when the transaction is FAILED and the settlement is UNSETTLED.” As a policy that becomes:'),
      h('ul', { class: 'howto-list' }, policySentences(EXAMPLE).map((line) => h('li', {}, line))),
      h('p', { class: 'hint' }, 'The settlement reading is 10 minutes old but the limit is 5? The result is “could not verify” and the answer asks for a fresh reading. If it was never read, the result is “missing input”. It never guesses.')),
    terms([
      ['Source passage', 'The exact approved text the rules come from. Every rule points to one.'],
      ['The date that decides', 'Which date picks the version: when the transaction happened, when the case was opened, when the question is asked, or a named event. It is never taken from the customer or the agent.'],
      ['Facts', 'Live readings the rules compare, such as the settlement state. Each has a limit on how old a reading may be.'],
      ['Rules', '“If these facts hold, the outcome is this.” Outcomes are labels for people, such as FOLLOW_INVESTIGATION_SOP. They never authorise a payment.'],
      ['Result', 'Decided (a rule applied), Missing input, Could not verify, or Conflict (two valid versions with no recorded replacement).'],
    ]),
    h('div', {}, h('b', {}, 'To make one'), steps([
      'Fastest: press “Start from an example”, or “Load from a file” for one a colleague saved. Otherwise press “New policy”.',
      'Basics: name it, choose the date that decides, and set when it applies.',
      'Source: search for the clause in an approved document and press “Use as source”.',
      'Facts: add only the live readings your rules compare (skip if there are none).',
      'Rules: write each rule as conditions and an outcome, and say which source passage backs it. Set what happens when no rule matches.',
      'Review: read it back as sentences. “Ready to register” means it is valid. Save a copy if you want one, then Register (administrators only).',
    ])),
    para('When a new version replaces an old one, open the new version under “This version replaces another” and record why. Without it, both stay valid and answers show a conflict instead of choosing.'),
  ]);
}

export function settingsHelp() {
  return howTo('settings', 'How to read and change these settings', [
    para('Palladion checks an answer in layers. This screen shows each layer, whether it is on, and what happens if you turn it down. Full power is the default and what real use should keep.'),
    terms([
      ['On, Off', 'Whether the layer is running now. A switch you can flip is optional; the rest are not.'],
      ['Always on', 'The parts that guard authority: the final gate, access checks, canonical sources, trusted policy time, the safe rule interpreter and the read-only tools. Palladion has no switch for them, so neither does this screen.'],
      ['Changed, not applied', 'You moved a switch but have not applied it. Nothing changes until you press Apply, which restarts Palladion (10 to 20 seconds).'],
      ['Experiment mode', 'The independent critic can only be turned off in Palladion’s measurement mode, which it says is not a serving mode. Policy-based and operational claims are then withheld, and every answer says it was made that way.'],
      ['Reduced power', 'Shown in the top bar and on answers whenever anything is turned down, so a quieter setup is never mistaken for the real thing.'],
    ]),
    steps([
      'Read each switch’s “if you turn it down” line before you flip it.',
      'Flip what you want to compare, for example the reranker, then press Apply changes.',
      'Ask the same question again and compare. Chat answers show the review status and what could not be verified.',
      'Press “Reset to full power” when you are done.',
    ]),
  ], { open: false });
}
